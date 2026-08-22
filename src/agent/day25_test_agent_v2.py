"""
Day 25 练习 3：完整测试用例生成 Agent v2（可观测 + 容错 + 结构化输出）

对比 Day 24：
  Day 24 build_case_agent：5 工具 + ToolStrategy(TestCaseBundle)          ← 能干活
  Day 25 v2：+ LangSmith 追踪 + ModelRetry + ModelFallback + ToolRetry
             + ToolErrorMiddleware + recursion_limit                      ← 能看、能救

能力矩阵：
  可观测：环境变量（LANGSMITH_*）→ LangSmith UI 看完整调用树
  容错：模型重试 / 模型回退 / 工具重试 / 工具异常转消息
  预算：recursion_limit（RunnableConfig 传入，防死循环）
  结构化：result["structured_response"] 直接是 TestCaseBundle（Pydantic）

⚠️ 坑位提醒（venv 实测）：
  - fallback 字符串必须带 provider 前缀 "google_genai:..."
  - ModelFallbackMiddleware 构建期要 API key → 无 API 冒烟用 build_smoke_agent_v2()
  - recursion_limit 在 config 里，不在 create_agent 参数里

用法：
  python day25_test_agent_v2.py
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()  # ⚠️ 必须在 langchain import 之前（LangSmith 静默失效的坑）

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelFallbackMiddleware,
    ModelRetryMiddleware,
    ToolCallRequest,
    ToolErrorMiddleware,
    ToolRetryMiddleware,
)
from langchain.agents.structured_output import ToolStrategy
from langchain_core.language_models.fake_chat_models import FakeChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI

from day23_case_tools import analyze_bug_report, generate_test_cases, run_api_test
from day24_case_agent import TestCaseBundle, extract_bundle, kb_search
from day24_kb_upsert import kb_import
from day25_error_handling import on_tool_error  # 复用练习 2 的错误处理器

# ═══════════════════════════════════════════════════════
# 常量 + 资源
# ═══════════════════════════════════════════════════════

MAIN_MODEL: str = "gemini-3.1-flash-lite"
FALLBACK_MODEL: str = "google_genai:gemini-3.5-flash"  # ⚠️ 必须带 provider 前缀

llm = ChatGoogleGenerativeAI(model=MAIN_MODEL, temperature=0.2)

# ═══════════════════════════════════════════════════════
# Agent v2 构建
# ═══════════════════════════════════════════════════════

# 工具集抽成模块级常量：构建函数与 exp1 打印共用（避免 magic list）
AGENT_TOOLS = [generate_test_cases, analyze_bug_report, run_api_test, kb_search, kb_import]


def build_agent_v2():
    """Agent v2：5 工具 + ToolStrategy + 全 middleware（模型重试/回退 + 工具重试/错误转消息）。

    ⚠️ 含 ModelFallbackMiddleware → 构建期需要 API key（.env 已有）。
    """
    return create_agent(
        model=llm,
        tools=AGENT_TOOLS,
        system_prompt=(
            "你是一名资深软件测试工程师的 AI 助手，负责生成结构化的测试用例。\n"
            "工作流程：\n"
            "1. 需求涉及本项目历史知识 → 先 kb_search 查询参考\n"
            "2. 用 generate_test_cases 生成用例（需求较长时）\n"
            "3. 用户提到 Bug → analyze_bug_report 分析\n"
            "4. 用户给了接口地址 → run_api_test 实测\n"
            "5. 用户提供新文档需要入库 → kb_import\n"
            "6. 工具返回错误消息 → 修正参数后重试，不要编造\n"
            "最后：把完整用例整理进 TestCaseBundle 输出（feature 用需求的功能名）"
        ),
        response_format=ToolStrategy(TestCaseBundle),  # Day 24：最终输出被 Schema 约束
        middleware=[
            ToolErrorMiddleware(on_error=on_tool_error),
            ToolRetryMiddleware(max_retries=2, on_failure="error"),
            ModelFallbackMiddleware(FALLBACK_MODEL),
            ModelRetryMiddleware(max_retries=2, on_failure="error"),
        ],
    )

def build_smoke_agent_v2():
    """零 API 冒烟：FakeChatModel + 除 Fallback 外的 middleware + 工具注册（不 invoke）。"""
    return create_agent(
        model=FakeChatModel(),
        tools=AGENT_TOOLS,
        middleware=[
            # 与 build_agent_v2 保持一致：ToolError 外层 / ToolRetry 内层
            ToolErrorMiddleware(on_error=on_tool_error),
            ToolRetryMiddleware(max_retries=1, on_failure="error"),
            ModelRetryMiddleware(max_retries=1, on_failure="error"),
        ],
    )


# ═══════════════════════════════════════════════════════
# 实验
# ═══════════════════════════════════════════════════════


def exp1_smoke_build() -> None:
    """实验 1：无 API 冒烟 —— 5 工具 + 3 middleware 构建不炸。"""
    print("=" * 60)
    print("实验 1：无 API 冒烟构建 Agent v2（工具集 + middleware 组合）")
    agent = build_smoke_agent_v2()
    print(f"✅ 构建成功: {type(agent).__name__}")
    print("   工具箱:", [t.name for t in AGENT_TOOLS])


def exp2_full_flow() -> None:
    """实验 2：完整流程（真实 API）—— 参考知识库生成用例 + 结构化输出。"""
    print("=" * 60)
    print("实验 2：完整流程（kb_search → 生成用例 → TestCaseBundle）")
    agent = build_agent_v2()
    config: RunnableConfig = {"recursion_limit": 25}
    result: dict[str, object] = agent.invoke(
        {"messages": [HumanMessage(content="为登录功能生成测试用例，先参考知识库里的登录相关 Bug")]},
        config=config,
    )
    bundle: TestCaseBundle | None = extract_bundle(result)
    if bundle is None:
        print("❌ 未拿到 structured_response → 去 LangSmith 看最后一步是 tool_call 还是 text")
        return
    print(f"✅ feature={bundle.feature}, summary={bundle.summary[:60]}...")
    for tc in bundle.test_cases:
        print(f"   {tc.id} [{tc.priority}/{tc.case_type}] {tc.title}")
    print("   🔍 LangSmith 看本次 run：完整调用树（kb_search → generate_test_cases → 结构化输出）")



if __name__ == "__main__":
    exp1_smoke_build()
    exp2_full_flow()
    print("\n💡 要点回顾：")
    print("   Agent v2 = Day 24 的能力 + LangSmith 可观测 + 模型/工具容错 + 预算保护")
    print("   这就是 Day 27-28 周末项目'多工具测试 Agent'的正式底座")