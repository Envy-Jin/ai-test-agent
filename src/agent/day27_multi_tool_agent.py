"""
Day 27 练习 2/3：多工具测试 Agent v4 —— 自然语言 → 规划 → 执行 → 测试报告

升级链：
  Day 24 Agent      = 5 工具 + ToolStrategy(TestCaseBundle)     ← 能生成用例
  Day 25 Agent v2   = + LangSmith + middleware 容错             ← 能看、能救
  Day 26 Agent v3   = + checkpointer 记忆（InMemorySaver/SqliteSaver）← 能记住
  Day 27 Agent v4   = 输出换 TestReport + 模型升级               ← 能执行、能汇报

v4 与 v3 的差异（只有三处）：
  1. response_format: ToolStrategy(TestCaseBundle) → ToolStrategy(TestReport)
  2. system_prompt:   增加"执行测试 + 如实填执行结果"职责
  3. 模型:            gemini-3.5-flash-lite（主）/ google_genai:gemini-3.1-flash-lite（备用）

⚠️ ToolStrategy 停机机制（Day 26 源码确认）：
  模型每轮必须调工具、唯一停机 = 交 TestReport（调用输出工具）。
  → 验证问题必须落在测试职责内；闲聊问题会 GraphRecursionError，别试。

用法：
  python -c "from day27_multi_tool_agent import build_smoke_v4; build_smoke_v4(); print('✅ 冒烟通过')"  # 零 API
  python day27_multi_tool_agent.py     # 端到端实战（真实 API + mock 靶场）
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()  # ⚠️ 必须在 langchain import 之前（LangSmith 静默失效的坑，Day 25 口诀）

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
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.memory import InMemorySaver

from day25_error_handling import on_tool_error
from day25_test_agent_v2 import AGENT_TOOLS
from day27_mock_api import start_mock_server, stop_mock_server
from day27_report import ReportItem, TestReport, render_test_report

# ═══════════════════════════════════════════════════════
# 常量 + 模型（Day 27 升级：主 3.5-flash-lite / 备 3.1-flash-lite）
# ═══════════════════════════════════════════════════════

llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", thinking_level="medium")  # 2026-07-21 GA，联网确认

FALLBACK_MODEL: str = "google_genai:gemini-3.1-flash-lite"  # ⚠️ 必须带 provider 前缀（Day 25 教训）

def make_serde():
    """msgpack 白名单序列化器：注册 TestReport / ReportItem（Day 26 机制）。"""
    from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer  # noqa: PLC0415

    return JsonPlusSerializer(allowed_msgpack_modules=[TestReport, ReportItem])



def build_agent_v4(checkpointer):
    """Agent v4 = v3 底座 + 输出换 TestReport + 模型升级。

    ⚠️ 返回注解【不要】写 -> object（Day 26 口诀 25）：
    让 pyright 推断 create_agent 的真实返回类型 CompiledStateGraph。
    """
    return create_agent(
        model=llm,
        tools=AGENT_TOOLS,
        system_prompt=(
            "你是一名资深软件测试工程师的 AI 助手，负责接口测试并输出测试报告。\n"
            "工作流程：\n"
            "1. 用户给出接口地址 → 先 kb_search 查知识库是否有相关用例或 Bug 可参考\n"
            "2. 用 generate_test_cases 生成覆盖正常/边界/异常的用例\n"
            "3. 用 run_api_test 逐条执行（url 用用户给的地址，method=POST，payload 传 JSON 字符串）\n"
            "4. 执行失败的用例 → 用 analyze_bug_report 分析根因\n"
            "5. 工具返回错误消息（如 404/超时）→ 修正参数重试；重试仍失败则标 BLOCKED\n"
            "最后：把全部用例与执行结果如实整理进 TestReport 输出——\n"
            "  status 只能填 PASS/FAIL/BLOCKED；actual 填接口实际返回摘要；不要编造结果"
        ),
        response_format=ToolStrategy(TestReport),
        middleware=[
            ToolErrorMiddleware(on_error=on_tool_error),      # 外层
            ToolRetryMiddleware(max_retries=2, on_failure="error"),  # 内层（Day 25 顺序陷阱）
            ModelFallbackMiddleware(FALLBACK_MODEL),          # 外层
            ModelRetryMiddleware(max_retries=2, on_failure="error"),  # 内层
        ],
        checkpointer=checkpointer,
    )


def build_smoke_v4():
    """零 API 冒烟：FakeChatModel + ToolStrategy(TestReport)（Day 24 确认构建期零 API）。

    ⚠️ 不含 ModelFallbackMiddleware（构建期即实例化模型、需要 key）。
    ⚠️ 同样不要 -> object（口诀 25）。
    """
    return create_agent(
        model=FakeChatModel(),
        tools=AGENT_TOOLS,
        middleware=[
            ToolErrorMiddleware(on_error=on_tool_error),
            ToolRetryMiddleware(max_retries=1, on_failure="error"),
            ModelRetryMiddleware(max_retries=1, on_failure="error"),
        ],
        response_format=ToolStrategy(TestReport),
        checkpointer=InMemorySaver(serde=make_serde()),
    )


def extract_report(result: dict[str, object]) -> TestReport | None:
    """从 invoke 结果提取 TestReport（structured_response 是 object → isinstance 收窄）。"""
    sr: object = result.get("structured_response")
    return sr if isinstance(sr, TestReport) else None

# ═══════════════════════════════════════════════════════
# 实验
# ═══════════════════════════════════════════════════════

def exp1_smoke() -> None:
    """实验 1：零 API 冒烟——v4 构建不炸（FakeChatModel + ToolStrategy(TestReport)）。"""
    print("=" * 60)
    print("实验 1：Agent v4 无 API 冒烟构建")
    agent = build_smoke_v4()
    print(f"✅ 构建成功: {type(agent).__name__}（response_format 换成 TestReport 后签名正确）")


def exp2_report_to_markdown() -> None:
    """实验 2：报告模块联动——手工构造 TestReport → 渲染 Markdown（零 API）。"""
    print("=" * 60)
    print("实验 2：TestReport → Markdown 渲染联动")
    report = TestReport(
        feature="用户登录",
        base_url="http://127.0.0.1:8765/api/login",
        items=[
            ReportItem(
                id="TC001", title="正确账号密码登录", priority="P0", case_type="功能",
                steps=["POST /api/login"], expected="code=0 与 token", actual="code=0 含 token", status="PASS",
            ),
            ReportItem(
                id="TC002", title="密码少于 8 位", priority="P1", case_type="边界",
                steps=["POST /api/login"], expected="400 错误码 40002", actual="400 code=40002", status="PASS",
            ),
        ],
        conclusion="通过",
    )
    md: str = render_test_report(report)
    first_lines: list[str] = md.splitlines()[:12]
    print("\n".join(first_lines))
    assert "通过: 2" in md and "失败: 0" in md
    print("✅ 渲染联动正常")


def exp3_end_to_end(port: int = 8765) -> str | None:
    """实验 3：端到端实战——起 mock API → Agent v4 全流程 → 报告落盘。

    完整链路：自然语言指令 → kb_search → generate_test_cases → run_api_test ×N
             → analyze_bug_report → 交 TestReport → render → outputs/login_test_report.md

    返回报告文件路径（未拿到 TestReport 返回 None）。
    """
    print("=" * 60)
    print("实验 3：端到端实战（gemini-3.5-flash-lite 跑完整工具链）")
    server = start_mock_server(port)
    try:
        agent = build_agent_v4(InMemorySaver(serde=make_serde()))
        config: RunnableConfig = {
            "configurable": {"thread_id": "e2e-login-demo"},
            "recursion_limit": 50,  # 工具多、轮次多 → 预算放宽（Day 25 预算保护）
        }
        instruction: str = (
            f"请为「用户登录」接口 http://127.0.0.1:{port}/api/login 做接口测试：\n"
            "1. 生成 3 条用例：正确账号密码登录（期望 200）/ 密码少于8位（期望 400）/ 错误凭据（期望 401）\n"
            "2. 用 run_api_test 逐条执行（method=POST，payload 传 JSON 字符串）\n"
            "3. 最后把结果整理成 TestReport 输出（status 如实填 PASS/FAIL/BLOCKED）"
        )
        result: dict[str, object] = agent.invoke(
            {"messages": [HumanMessage(content=instruction)]},
            config=config,
        )
        report: TestReport | None = extract_report(result)
        if report is None:
            print("❌ 未拿到 TestReport（打开 LangSmith 看最后几轮模型在做什么）")
            return None
        md: str = render_test_report(report)
        out_dir: str = os.path.join(os.path.dirname(__file__), "..", "..", "outputs")
        os.makedirs(out_dir, exist_ok=True)
        out_path: str = os.path.join(out_dir, "login_test_report.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"✅ 测试报告已保存: {out_path}")
        print(md[:900])
        return out_path
    finally:
        stop_mock_server()


#==================================================================
if __name__ == "__main__":
    # exp1_smoke()
    # exp2_report_to_markdown()
    exp3_end_to_end()  # 真实 API + mock 靶场，默认注释；想跑就取消注释（或在练习 3 跑）
    print("\n💡 要点回顾：")
    print("   Agent v4 = v3 + 输出换 TestReport（能执行、能汇报）")
    print("   模型只填 status/actual/conclusion，统计与渲染交给确定性代码")
    print("   报告落盘在 outputs/，可直接当交付物")