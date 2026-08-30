"""
Day 25 练习 1：LangSmith 追踪 Day 24 测试用例生成 Agent

目标：
  1. 零侵入配置 LangSmith（环境变量 + load_dotenv，Agent 代码零改动自动追踪）
  2. 复用 day24_case_agent.build_case_agent（5 工具 + ToolStrategy(TestCaseBundle)）
  3. 在 LangSmith UI 观察完整调用树（用户输入 → 工具调用 → 结构化输出）
  4. 诊断演练：structured_response 缺失时，用追踪定位模型最后一步干了什么

⚠️ 2026 新 API 三个坑：
  - LANGCHAIN_TRACING_V2 必须是字符串 "true"，不是布尔 True
  - load_dotenv() 必须在 import langchain 之前（否则追踪静默失效）
  - langchain>=1.0 自动追踪，不要手动用 LangChainTracer 类

用法：
  python day25_langsmith_tracing.py
  （跑完去 https://smith.langchain.com 看 test-agent 项目的 trace）
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()  # ⚠️ 必须在 langchain import 之前！

# ── 追踪开关（字符串 "true" 判断，不是布尔 True）──
TRACING_ON: bool = os.getenv("LANGCHAIN_TRACING_V2", "").lower() == "true"
HAS_KEY: bool = bool(os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY"))

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig

from day24_case_agent import TestCaseBundle, build_case_agent, extract_bundle

# ═══════════════════════════════════════════════════════
# 环境自检（跑任何实验前先确认追踪就绪）
# ═══════════════════════════════════════════════════════


def check_tracing_env() -> None:
    """打印追踪配置状态：开关 / Key / 项目名。"""
    print("=" * 60)
    print("LangSmith 追踪配置自检")
    print(f"  LANGCHAIN_TRACING_V2 = {os.getenv('LANGCHAIN_TRACING_V2', '(未设置)')!r}")
    print(f"  追踪开关（TRACING_ON） = {TRACING_ON}")
    print(f"  API Key 是否设置      = {'✅ 是' if HAS_KEY else '❌ 否（去 smith.langchain.com 创建）'}")
    print(f"  Project              = {os.getenv('LANGSMITH_PROJECT') or os.getenv('LANGCHAIN_PROJECT') or '(未设置，默认 unassigned)'}")
    if not (TRACING_ON and HAS_KEY):
        print("  ⚠️ 配置不完整：本次运行不会产生追踪（或不会上报）")
        print("     检查：.env 是否追加了 LANGCHAIN_TRACING_V2=true 和 LANGSMITH_API_KEY")
    print("=" * 60)

def _invoke_case_agent(question: str) -> None:
    """公共调用：invoke → 提取结构化响应 → 提示去 LangSmith 查看。"""
    agent = build_case_agent()
    config: RunnableConfig = {"recursion_limit": 25}
    result: dict[str, object] = agent.invoke(
        {"messages": [HumanMessage(content=question)]}, config=config
    )
    bundle: TestCaseBundle | None = extract_bundle(result)
    if bundle is None:
        print("❌ 未拿到 structured_response —— 这就是 Day 24 的遗留问题")
        print("   🔍 诊断动作：去 LangSmith 打开本次 run，看模型最后一步输出：")
        print("      是调用输出工具（tool_call）还是直接输出文本（text）？")
        print("      文本结尾不标准 → system_prompt 加'最后必须输出 TestCaseBundle'")
        return
    print(f"✅ feature={bundle.feature}, 共 {len(bundle.test_cases)} 条用例")
    for tc in bundle.test_cases:
        print(f"   {tc.id} [{tc.priority}/{tc.case_type}] {tc.title}")
    print(f"   🔍 去 LangSmith 看本次 run：https://smith.langchain.com/project/test-agent")


def exp1_trace_direct() -> None:
    """实验 1：直接生成登录用例（不引导查知识库）→ 观察调用树。"""
    print("=" * 60)
    print("实验 1：直接生成登录功能测试用例（观察 LangSmith 调用树）")
    _invoke_case_agent("为登录功能生成测试用例：手机号+密码登录，密码不少于8位")


def exp2_trace_with_kb() -> None:
    """实验 2：引导参考知识库 → 观察 kb_search 工具调用轨迹。"""
    print("=" * 60)
    print("实验 2：参考知识库生成（观察 kb_search 工具轨迹）")
    _invoke_case_agent("为登录功能生成测试用例，注意先参考知识库里已有的登录相关 Bug 和需求")




if __name__ == "__main__":
    # check_tracing_env()
    # exp1_trace_direct()
    exp2_trace_with_kb()
    print("\n💡 要点回顾：")
    print("   追踪零侵入：只改环境变量，Agent 代码一行没动")
    print("   LangSmith 看到的是完整调用树：每次模型调用 + 每次工具调用（参数/结果/耗时/token）")
    print("   用它定位 structured_response 缺失：看模型最后一步是 tool_call 还是 text")
    print("   本地 stream(updates) 是探照灯；LangSmith 是行车记录仪")
