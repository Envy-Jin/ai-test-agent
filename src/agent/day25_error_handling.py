"""
Day 25 练习 2：错误处理 middleware 强化（模型级 + 组合编排）

学习计划旧 API（已弃用）：handle_parsing_errors / max_iterations / early_stopping_method
新 API（langchain 1.3.14 venv 实测）：
  - ModelRetryMiddleware：模型调用失败自动重试（指数退避 + jitter）
  - ModelFallbackMiddleware：主模型失败切换备用模型
  - ToolRetryMiddleware / ToolErrorMiddleware：Day 23 已学，今天补组合
  - recursion_limit：防死循环烧钱，通过 RunnableConfig 传入（create_agent 没有该参数！）

⚠️ 三个坑（venv 实测）：
  - ModelFallbackMiddleware 传字符串必须带 provider 前缀："google_genai:gemini-3.1-flash"
    （裸 "gemini-3.1-flash" 会被 init_chat_model 误判 provider → 试图 import vertexai 缺包报错）
  - ModelFallbackMiddleware 构建期就会实例化模型 → 无 API 冒烟必须排除它
  - 组合顺序：retry 放内层（on_failure="error"），error 放外层（重试耗尽后异常才到达 on_error）

用法：
  python day25_error_handling.py                 # 全部实验（真实 API）
  python -c "from day25_error_handling import build_smoke_agent; build_smoke_agent()"  # 零 API 冒烟
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()  # ⚠️ 必须在 langchain import 之前（LangSmith 追踪静默失效的坑）

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelFallbackMiddleware,
    ModelRetryMiddleware,
    ToolCallRequest,
    ToolErrorMiddleware,
    ToolRetryMiddleware,
)
from langchain_core.language_models.fake_chat_models import FakeChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

from day23_case_tools import analyze_bug_report, generate_test_cases

# ═══════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════
MAIN_MODEL: str = "gemini-3.1-flash-typo"
# ⚠️ 备用模型字符串必须带 provider 前缀（裸名会被误判为 vertexai 导致缺包报错）
FALLBACK_MODEL: str = "google_genai:gemini-3.1-flash-lite"

llm = ChatGoogleGenerativeAI(model=MAIN_MODEL, temperature=0.2)

# ═══════════════════════════════════════════════════════
# on_error 处理器（ToolErrorMiddleware 必须提供）
# ═══════════════════════════════════════════════════════


def on_tool_error(exc: Exception, request: ToolCallRequest) -> str | None:
    """把可预期的工具异常转成错误消息（给模型看，让它修正重试）；其余异常继续抛出。

    官方建议：错误消息只提异常类型名，不要带原始异常消息（可能含敏感信息）。
    """
    if isinstance(exc, ValueError):
        name: str = str(request.tool_call.get("name", "unknown"))
        return f"工具 {name} 失败（{type(exc).__name__}）：输入不合法，请修正参数后重试。"
    return None  # 其余异常原样抛出（中断运行，不掩盖问题）

# ═══════════════════════════════════════════════════════
# 演示工具（观察 middleware 用）
# ═══════════════════════════════════════════════════════


@tool
def strict_tool(requirement: str) -> str:
    """严格的用例工具：需求文本太短时抛 ValueError（演示 ToolErrorMiddleware）。

    Args:
        requirement: 需求描述，必须至少 10 个字符。
    """
    if len(requirement.strip()) < 10:
        raise ValueError("需求描述过短（<10 字符），无法生成有意义的用例")
    return f"已为「{requirement}」生成 5 条用例"


# ═══════════════════════════════════════════════════════
# Agent 构建
# ═══════════════════════════════════════════════════════


def build_robust_agent():
    """完整容错 Agent：模型重试 + 模型回退 + 工具重试 + 工具错误转消息。

    ⚠️ 含 ModelFallbackMiddleware → 构建期需要 API key（.env 已有，OK）。
    """
    return create_agent(
        model=llm,
        tools=[generate_test_cases, analyze_bug_report, strict_tool],
        system_prompt=(
            "你是一名资深测试工程师的 AI 助手。\n"
            "1. 用户要求生成测试用例 → generate_test_cases\n"
            "2. 用户要求分析 Bug → analyze_bug_report\n"
            "3. 工具返回错误消息时，修正输入后重试，不要编造结果"
        ),
        middleware=[
            # 内层：先重试（耗尽后异常继续向外抛）
            ToolRetryMiddleware(max_retries=2, on_failure="error", retry_on=(ValueError,)),
            # 外层：兜住重试后仍失败的工具异常，转成错误消息给模型
            ToolErrorMiddleware(on_error=on_tool_error),
            # 模型级：调用失败自动重试
            ModelRetryMiddleware(max_retries=2, backoff_factor=2.0, initial_delay=1.0),
            # 模型级：主模型挂了切备用模型（字符串必须带 provider 前缀）
            ModelFallbackMiddleware(FALLBACK_MODEL),
        ],
    )

def build_smoke_agent():
    """零 API 冒烟：FakeChatModel + 除 Fallback 外的全部 middleware。

    ⚠️ ModelFallbackMiddleware 构建期就会实例化模型（需要 key），冒烟必须排除。
    """
    return create_agent(
        model=FakeChatModel(),
        tools=[strict_tool],
        middleware=[
            ToolRetryMiddleware(max_retries=1, on_failure="error", retry_on=(ValueError,)),
            ToolErrorMiddleware(on_error=on_tool_error),
            ModelRetryMiddleware(max_retries=1),
        ],
    )

# ═══════════════════════════════════════════════════════
# 实验
# ═══════════════════════════════════════════════════════


def exp1_smoke_build() -> None:
    """实验 1：零 API 冒烟 —— middleware 组合构建期不炸（不调 LLM/不调工具）。"""
    print("=" * 60)
    print("实验 1：无 API 冒烟构建（FakeChatModel + 3 middleware）")
    agent = build_smoke_agent()
    print(f"✅ 构建成功: {type(agent).__name__}")
    print("   冒烟通过 = 组合顺序和参数签名正确（ModelFallback 已排除，见 docstring）")


def exp2_normal_run() -> None:
    """实验 2：真实 API 正常路径 —— middleware 不干扰正常执行。"""
    print("=" * 60)
    print("实验 2：正常路径（middleware 应全程旁观，不触发）")
    agent = build_robust_agent()
    config: RunnableConfig = {"recursion_limit": 25}
    result: dict[str, object] = agent.invoke(
        {"messages": [HumanMessage(content="分析这个 Bug：登录页白屏，刷新恢复，概率 30%")]},
        config=config,
    )
    msgs_obj: object = result.get("messages", [])
    if isinstance(msgs_obj, list) and msgs_obj:
        last = msgs_obj[-1]
        content: object = getattr(last, "content", "")
        print(f"✅ Agent 返回（末尾 200 字）：{str(content)[:200]}")
    print("   🔍 LangSmith 里应看到：1 次模型调用 + 1 次 analyze_bug_report，无重试节点")


def exp3_recursion_limit() -> None:
    """实验 3：recursion_limit 预算保护 —— 演示 config 传参 + 超限报错。

    ⚠️ 关键认知：create_agent 签名里【没有】recursion_limit 参数（venv 实测），
    必须通过 config 传入。超限时 LangGraph 抛 GraphRecursionError（run 直接失败），
    这正是"防死循环烧钱"的机制：宁可失败，也不无限迭代。
    """
    print("=" * 60)
    print("实验 3：recursion_limit 预算保护（故意给很小值）")
    agent = build_robust_agent()
    config: RunnableConfig = {"recursion_limit": 3}  # 正常 25，这里故意给 3
    try:
        result: dict[str, object] = agent.invoke(
            {"messages": [HumanMessage(content="生成测试用例，并逐步分析每个用例的覆盖点")]},
            config=config,
        )
        msgs_obj: object = result.get("messages", [])
        print(f"✅ 3 轮内完成了（模型很听话）: {len(msgs_obj) if isinstance(msgs_obj, list) else 0} 条消息")
    except Exception as exc:
        print(f"❌ 触发保护: {type(exc).__name__}")
        print(f"   {str(exc)[:150]}")
        print("   → 这就是预算保护：超限即失败，不会无限循环烧 API 额度")
    print("   平时用 25（Day 23 的值），只有怀疑死循环时才调小观察")


def exp4_trigger_tool_error() -> None:
    """实验 4（进阶）：真正触发 ToolRetry + ToolError 的故障分支。"""
    agent = build_robust_agent()
    result: dict[str, object] = agent.invoke(
        {"messages": [HumanMessage(content="用 strict_tool 生成用例，输入 'abc'")]},
        config=RunnableConfig(recursion_limit=25),
    )
    # 🔍 去 LangSmith 展开 run：应该看到 错误 → 重试 → 错误消息 → 模型修正 → 成功


if __name__ == "__main__":
    # exp1_smoke_build()
    # exp2_normal_run()
    # exp3_recursion_limit()
    exp4_trigger_tool_error()
    print("\n💡 要点回顾：")
    print("   ModelRetryMiddleware = 模型调用失败自动重试（指数退避）")
    print("   ModelFallbackMiddleware = 主模型挂了切备用（字符串必须带 provider 前缀！）")
    print("   组合顺序：ToolRetry(on_failure='error') 内层 → ToolErrorMiddleware 外层")
    print("   recursion_limit 走 config（create_agent 没这参数），防死循环烧钱")
