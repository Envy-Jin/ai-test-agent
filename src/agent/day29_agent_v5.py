"""
Day 29 练习 4：Agent v5 —— 多出口（ToolStrategy(Union[RequirementAnalysis, TestReport])）

升级链（对比 Day 27 的 v4，只改两处）：
  v4  = 5 工具 + ToolStrategy(TestReport)          ← 单一出口：接口测试
  v5  = 5 工具 + ToolStrategy(Union[RequirementAnalysis, TestReport])  ← 多出口：需求分析 / 接口测试
  → 模型按任务自动选 Schema（2026-08-26 联网确认：union 每个 arm 展开成独立
    artificial structured-output tool，见 langchain/agents/structured_output.py 的 _iter_variants）

⚠️ ToolStrategy 停机机制（Day 26 源码确认，Union 下依然成立）：
  模型每轮必须调工具、唯一停机 = 交【任意一个】bundle。
  → 验证问题必须落在"需求分析"或"接口测试"职责内；闲聊依然 GraphRecursionError。

⚠️ 教学点：Union 出口 = 灵活性，但要求 system_prompt 把"什么任务交什么出口"写清楚，
  否则模型可能选错出口（如接口测试任务交了 RequirementAnalysis）——LangSmith 观察点。

用法：
  python -c "from day29_agent_v5 import exp1_smoke_union; exp1_smoke_union()"  # 零 API
  python day29_agent_v5.py    # 真实 API：多出口演示（默认注释，取消注释跑）
"""

import os
import sys
from typing import Union

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()  # ⚠️ 必须在 langchain import 之前

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelFallbackMiddleware,
    ModelRetryMiddleware,
    ToolErrorMiddleware,
    ToolRetryMiddleware,
)
from langchain.agents.structured_output import ToolStrategy
from langchain_core.language_models.fake_chat_models import FakeChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from day25_error_handling import on_tool_error
from day25_test_agent_v2 import AGENT_TOOLS
from day27_multi_tool_agent import extract_report, llm, make_serde
from day27_report import TestReport, render_test_report
from day28_mock_api import start_mock, stop_mock
from day29_requirement_analysis import (
    RequirementAnalysis,
    analyze_requirement_file,
    render_analysis_markdown,
    validate_analysis,
)

here: str = os.path.dirname(os.path.abspath(__file__))
REQUIREMENT_DIR: str = os.path.join(here, "..", "..", "docs", "requirements")

# ═══════════════════════════════════════════════════════
# Agent v5：v4 底座 + 多出口（设计决策：出口参数化）
# ═══════════════════════════════════════════════════════

FALLBACK_MODEL: str = "google_genai:gemini-3.1-flash-lite"  # 必须带 provider 前缀（Day 25 教训）

# Union 出口：模型按任务自动选（2026-08-26 联网确认的官方特性）
V5_RESPONSE_FORMAT = ToolStrategy(Union[RequirementAnalysis, TestReport])


def build_agent_v5(checkpointer, response_format=V5_RESPONSE_FORMAT, system_prompt: str | None = None):
    """Agent v5 = v4 底座 + 出口参数化 + 双职责 system_prompt。

    ⚠️ 返回注解【留空】（Day 26 口诀 25）：让 pyright 推断 CompiledStateGraph。
    ⚠️ response_format 参数化：默认 Union 多出口；传单 Schema 就退化回 v4 单出口——
       "出口可换"是 v4 留的设计接口，今天用参数化把它显式化。
    """
    return create_agent(
        model=llm,  # 复用 Day 27 模块级 llm（3.5-flash-lite + thinking_level=medium）
        tools=AGENT_TOOLS,
        system_prompt=system_prompt or (
            "你是一名资深软件测试工程师的 AI 助手，能完成两类任务：\n"
            "【任务 A：需求分析】用户给需求文档 → 用 kb_search 查历史类似需求 →\n"
            "  输出 RequirementAnalysis（feature_name + summary + 分级 test_suites，P0 功能/P1 边界异常安全/P2 兼容）\n"
            "【任务 B：接口测试】用户给接口地址 → 用 kb_search 查测试账号 → 用 generate_test_cases 生成用例 →\n"
            "  用 run_api_test 逐条执行 → 执行失败用 analyze_bug_report 分析 → 输出 TestReport（status 如实填）\n"
            "⚠️ 根据用户任务类型选择正确出口：需求分析任务交 RequirementAnalysis，接口测试任务交 TestReport"
        ),
        response_format=response_format,
        middleware=[
            ToolErrorMiddleware(on_error=on_tool_error),           # 外层
            ToolRetryMiddleware(max_retries=2, on_failure="error"),  # 内层（Day 25 顺序陷阱）
            ModelFallbackMiddleware(FALLBACK_MODEL),               # 外层
            ModelRetryMiddleware(max_retries=2, on_failure="error"),  # 内层
        ],
        checkpointer=checkpointer,
    )


def extract_analysis(result: dict[str, object]) -> RequirementAnalysis | None:
    """从 invoke 结果提取 RequirementAnalysis（Union 出口的二分收窄）。"""
    sr: object = result.get("structured_response")
    return sr if isinstance(sr, RequirementAnalysis) else None

# ═══════════════════════════════════════════════════════
# 实验
# ═══════════════════════════════════════════════════════

def exp1_smoke_union() -> None:
    """实验 1：零 API 冒烟——Union 出口构建不炸（FakeChatModel）。

    ⚠️ 不含 ModelFallbackMiddleware（构建期实例化模型需要 key，Day 27 同规）。
    """
    print("=" * 60)
    print("实验 1：Agent v5 Union 出口无 API 冒烟构建")
    agent = create_agent(
        model=FakeChatModel(),
        tools=AGENT_TOOLS,
        middleware=[
            ToolErrorMiddleware(on_error=on_tool_error),
            ToolRetryMiddleware(max_retries=1, on_failure="error"),
            ModelRetryMiddleware(max_retries=1, on_failure="error"),
        ],
        response_format=V5_RESPONSE_FORMAT,
        checkpointer=InMemorySaver(serde=make_serde()),
    )
    # Union 展开验证：schema_specs 应该是 2 个（RequirementAnalysis + TestReport）
    specs = getattr(V5_RESPONSE_FORMAT, "schema_specs", [])
    print(f"  ✅ 构建成功；Union 展开出 {len(specs)} 个出口规格（预期 2）")
    assert len(specs) == 2, f"Union 应展开 2 个出口，实际 {len(specs)}"
    print(f"    出口列表: {[s.name for s in specs]}")


def exp2_dual_exit(port: int = 8766, req_path: str = os.path.join(REQUIREMENT_DIR, "login_requirement.md")) -> None:
    """实验 2：同一个 Agent 两种出口自动路由（真实 API）。

    任务 A：需求分析 → 交 RequirementAnalysis（先 kb_search 查历史）
    任务 B：接口测试 → 起 mock → 交 TestReport（复用 Day 27 流程）
    验证点：模型按任务选对出口（LangSmith 里能看到交的哪个 bundle）。
    """
    print("=" * 60)
    print("实验 2：Agent v5 多出口自动路由（需求分析 + 接口测试）")
    agent = build_agent_v5(InMemorySaver(serde=make_serde()))
    thread: str = "v5-dual-exit"
    config: RunnableConfig = {"configurable": {"thread_id": thread}, "recursion_limit": 50}

    # ── 任务 A：需求分析（先读文档；读不到直接 fail fast，不喂残缺输入给 Agent）──
    doc_text: str | None = None
    if os.path.isfile(req_path):
        with open(req_path, "r", encoding="utf-8", errors="replace") as f:
            doc_text = f.read()
    if not doc_text or not doc_text.strip():
        print(f"❌ 需求文档读取失败或为空: {req_path}（任务 A 中止——不携带残缺输入进 Agent 循环）")
        return
    instruction_a: str = (
        "请分析下面这份需求文档，先生成需求摘要，再按 P0 功能 / P1 边界+异常+安全 / P2 兼容"
        "生成分级测试用例，最后输出 RequirementAnalysis：\n\n"
        f"{doc_text}"  # 到这里 doc_text 一定非空（上方已 fail fast 收窄）
    )
    result_a: dict[str, object] = agent.invoke(
        {"messages": [HumanMessage(content=instruction_a)]}, config=config
    )
    analysis: RequirementAnalysis | None = extract_analysis(result_a)
    if analysis is None:
        print("❌ 任务 A 未拿到 RequirementAnalysis（模型可能选了 TestReport 出口，LangSmith 查证）")
        return
    report = validate_analysis(analysis)
    md_a: str = render_analysis_markdown(analysis, report)
    out_dir: str = os.path.join(os.path.dirname(__file__), "..", "..", "outputs")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "requirement_v5_analysis.md"), "w", encoding="utf-8") as f:
        f.write(md_a)
    print(f"  ✅ 任务 A（需求分析）出口正确：feature={analysis.feature_name!r}，{report.total_cases} 条用例")
    print(f"     产物: outputs/requirement_v5_analysis.md")

    # ── 任务 B：接口测试（同 thread 第二段，模型应切 TestReport 出口）──
    server = start_mock(port)
    try:
        instruction_b: str = (
            f"请为「用户登录」接口 http://127.0.0.1:{port}/api/login 做接口测试：\n"
            "1. 先用 kb_search 查测试账号\n"
            "2. 生成 3 条用例（正确登录期望200 / 短密码期望400 / 错误凭据期望401）\n"
            "3. 用 run_api_test 逐条执行（method=POST，payload 传 JSON 字符串）\n"
            "4. 最后输出 TestReport（status 如实填 PASS/FAIL/BLOCKED）"
        )
        result_b: dict[str, object] = agent.invoke(
            {"messages": [HumanMessage(content=instruction_b)]}, config=config
        )
        trep: TestReport | None = extract_report(result_b)
        if trep is None:
            print("❌ 任务 B 未拿到 TestReport（模型可能还在 RequirementAnalysis 出口，LangSmith 查证）")
            return
        print(f"  ✅ 任务 B（接口测试）出口正确：{len(trep.items)} 条用例，"
              f"PASS={sum(1 for it in trep.items if it.status == 'PASS')}")
        print(render_test_report(trep)[:600])
        print("  ✅ 多出口自动路由演示完成（同一 Agent，两种输出形状）")
    finally:
        stop_mock()




if __name__ == "__main__":
    # exp1_smoke_union()
    exp2_dual_exit()   # 真实 API + mock 靶场，默认注释；想跑就取消注释
    print("\n💡 要点回顾：")
    print("   ToolStrategy(Union[A, B]) = 一个 Agent 多副面孔，模型按任务自动选出口")
    print("   v5 = v4 底座 + 出口参数化（第 6 周综合项目的前置）")
    print("   停机机制不变：必须交某个 bundle，闲聊依然 GraphRecursionError")
