"""
Day 28 练习 2/3：多工具测试 Agent 打磨 —— kb 播种 / 全 PASS / 多轮追问补测 / FAIL 分支

今天 0 行底座代码：build_agent_v4 / make_serde / extract_report 全从 day27 复用。

实验：
  exp_merge_demo()          零 API 冒烟：merge_reports 纯逻辑（去重 + 顺序 + 统计推导）
  exp_full_pass_followup()  端到端：kb 播种 → v4 全 PASS（凭据来自 kb）→ 追问补测 → 合并报告
  exp_fail_branch()         埋 Bug 靶场：错误凭据 → 500 → 1 FAIL → analyze_bug_report → 缺陷报告

⚠️ ToolStrategy 停机机制（Day 26/27）：追问/复述也必须落在测试职责内，闲聊会 GraphRecursionError。

用法：
  python -c "from day28_agent_followup import exp_merge_demo; exp_merge_demo(); print('✅ 冒烟通过')"  # 零 API
  python day28_agent_followup.py   # 默认只跑零 API 的 exp_merge_demo（真实端到端取消注释）
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()  # ⚠️ 必须在 langchain import 之前（LangSmith 静默失效的坑，Day 25 口诀）

from langchain_core.documents import Document
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from day24_case_agent import _get_kb_upserter
from day27_multi_tool_agent import build_agent_v4, extract_report, make_serde
from day27_report import ReportItem, TestReport, render_test_report
from day28_mock_api import start_mock, stop_mock

# ═══════════════════════════════════════════════════════
# 常量：测试账号凭据（Day 28 播种数据）
# ═══════════════════════════════════════════════════════

CREDENTIAL_SOURCE: str = "day28_credential.md"
CREDENTIAL_DOC: str = (
    "# 登录接口测试账号（接口测试前置条件）\n"
    "- 被测接口：POST /api/login\n"
    "- 测试手机号：13800138000\n"
    "- 测试密码：Test123456\n"
    "- 预期行为：使用上述账号调用接口，返回 HTTP 200，响应体 code=0 且包含 token 字段\n"
    "- 注意：该账号为测试专用，仅用于本地 mock 与测试环境，生产环境请勿使用"
)

def seed_kb() -> int:
    """把测试账号凭据写进知识库（幂等 upsert）。

    ⚠️ 设计决策 A：doc_type 必须用 "requirement"——kb_search 内部只用
    search_by_type(..., doc_type=requirement/bug) 两个白名单检索（day24_case_agent
    源码确认），标 test_case 会被静默漏掉，Agent 搜不到凭据又会瞎编密码。
    返回：本次写入片段数（重复播种 = 删旧加新，总数不变，Day 24 幂等）。
    """
    upserter = _get_kb_upserter()
    docs: list[Document] = [
        Document(
            page_content=CREDENTIAL_DOC,
            metadata={"source": CREDENTIAL_SOURCE, "doc_type": "requirement", "feature": "login"},
        )
    ]
    return upserter.upsert_documents(docs)


# ═══════════════════════════════════════════════════════
# merge_reports：多轮补测报告的确定性合并（零 API，可独立冒烟）
# ═══════════════════════════════════════════════════════

def merge_reports(*reports: TestReport) -> TestReport:
    """合并多份增量报告：items 按 id 去重拼接，同 id 后者覆盖。

    设计要点（口诀：模型只做增量，聚合归代码）：
      - feature/base_url 取第一份非空值（报告主体信息以首份为准）
      - items 用 dict 按 id 去重：首次出现的顺序保持，同 id 新执行结果覆盖旧的
      - conclusion 取最后一份（多轮补测后结论以最新为准）
      - total/passed/failed 不在这里算——交给 render_test_report 的 sum()（Day 27 铁律）
    """
    if not reports:
        return TestReport(feature="", base_url=None, items=[], conclusion="")
    items_by_id: dict[str, ReportItem] = {}
    feature: str = ""
    base_url: str | None = None
    for rep in reports:
        if feature == "" and rep.feature != "":
            feature = rep.feature
        if base_url is None and rep.base_url is not None:
            base_url = rep.base_url
        for item in rep.items:
            items_by_id[item.id] = item  # 同 id 后者覆盖（补测场景：新执行结果优先）
    return TestReport(
        feature=feature,
        base_url=base_url,
        items=list(items_by_id.values()),
        conclusion=reports[-1].conclusion,
    )

# ═══════════════════════════════════════════════════════
# 实验
# ═══════════════════════════════════════════════════════

def exp_merge_demo() -> None:
    """实验：merge_reports 纯逻辑冒烟（零 API）。

    推演：v1 有 TC001/TC002/TC003（2 PASS + 1 FAIL），v2 有 TC003（重新执行→PASS）+ TC004。
    TC003 同 id 后者覆盖 → 合并后 4 条：TC001 PASS / TC002 PASS / TC003 PASS(覆盖) / TC004 PASS。
    """
    print("=" * 60)
    print("实验：merge_reports 纯逻辑合并（零 API）")
    v1 = TestReport(
        feature="用户登录",
        base_url="http://127.0.0.1:8766/api/login",
        items=[
            ReportItem(id="TC001", title="正确账号密码登录", priority="P0", case_type="功能",
                       steps=["POST /api/login"], expected="200+token", actual="200 code=0 token", status="PASS"),
            ReportItem(id="TC002", title="密码少于8位", priority="P1", case_type="边界",
                       steps=["POST /api/login"], expected="400", actual="400 code=40002", status="PASS"),
            ReportItem(id="TC003", title="错误凭据", priority="P0", case_type="异常",
                       steps=["POST /api/login"], expected="401", actual="500 服务端异常", status="FAIL"),
        ],
        conclusion="TC003 暴露服务端异常，需修复后回归。",
    )
    v2 = TestReport(
        feature="用户登录-补充测试",
        base_url=None,
        items=[
            ReportItem(id="TC003", title="错误凭据（复测）", priority="P0", case_type="异常",
                       steps=["POST /api/login"], expected="401", actual="401 code=40101", status="PASS"),
            ReportItem(id="TC004", title="空手机号", priority="P1", case_type="边界",
                       steps=["POST /api/login"], expected="400", actual="400 code=40001", status="PASS"),
        ],
        conclusion="复测通过，缺陷已修复。",
    )
    merged: TestReport = merge_reports(v1, v2)
    # 推演：4 条 = TC001/TC002（v1 保留）+ TC003（v2 覆盖，status 从 FAIL 变 PASS）+ TC004（v2 新增）
    assert [it.id for it in merged.items] == ["TC001", "TC002", "TC003", "TC004"], "id 顺序应为首次出现顺序"
    assert merged.items[2].status == "PASS", "同 id 后者覆盖：TC003 应为 v2 的 PASS"
    assert merged.feature == "用户登录" and merged.base_url == "http://127.0.0.1:8766/api/login"
    assert merged.conclusion == "复测通过，缺陷已修复。"
    md: str = render_test_report(merged)
    assert "总用例数: 4" in md and "通过: 4" in md and "失败: 0" in md
    print(render_test_report(merged))
    print("✅ 断言通过：id 去重 + 后者覆盖 + 统计推导全部正确")


def exp_full_pass_followup(port: int = 8766) -> str | None:
    """端到端：kb 播种 → v4 全 PASS → 追问补测 → 合并报告落盘。

    完整链路：
      1. seed_kb() 幂等播种测试账号（真实 embedding API）
      2. 起正常 mock → Agent v4（复用 day27）→ 第一轮 3 条全 PASS → 报告 v1
      3. 同 thread 第二轮追问补 2 条边界 → 增量报告 v2
      4. merge_reports(v1, v2) → 合并报告 → outputs/login_test_report_merged.md
    返回：合并报告路径（未拿到 TestReport 返回 None）。
    """
    print("=" * 60)
    print("实验：exp_full_pass_followup —— kb 播种 + 全 PASS + 追问补测 + 合并")
    written: int = seed_kb()
    print(f"  ① 知识库已播种测试账号（写入 {written} 条片段，幂等）")
    server = start_mock(port)
    try:
        agent = build_agent_v4(InMemorySaver(serde=make_serde()))
        thread: str = "followup-login"
        config: RunnableConfig = {"configurable": {"thread_id": thread}, "recursion_limit": 50}

        # ── 第一轮：3 条用例全 PASS（凭据来自 kb_search）──
        instruction1: str = (
            f"请为「用户登录」接口 http://127.0.0.1:{port}/api/login 做接口测试：\n"
            "1. 先用 kb_search 查询知识库中该接口的测试账号与历史用例\n"
            "2. 生成 3 条用例：正确账号密码登录（期望 200）/ 密码少于8位（期望 400）/ 错误凭据（期望 401）\n"
            "3. 用 run_api_test 逐条执行（method=POST，payload 传 JSON 字符串，凭据用知识库里查到的测试账号）\n"
            "4. 把结果整理成 TestReport 输出（status 如实填 PASS/FAIL/BLOCKED）"
        )
        result1: dict[str, object] = agent.invoke(
            {"messages": [HumanMessage(content=instruction1)]}, config=config
        )
        report1: TestReport | None = extract_report(result1)
        if report1 is None:
            print("❌ 第一轮未拿到 TestReport（打开 LangSmith 看最后几轮）")
            return None
        md1: str = render_test_report(report1)
        out_dir: str = os.path.join(os.path.dirname(__file__), "..", "..", "outputs")
        os.makedirs(out_dir, exist_ok=True)
        v1_path: str = os.path.join(out_dir, "login_test_report.md")
        with open(v1_path, "w", encoding="utf-8") as f:
            f.write(md1)
        passed1: int = sum(1 for it in report1.items if it.status == "PASS")
        print(f"  ② 第一轮完成：{len(report1.items)} 条用例，PASS={passed1} → {v1_path}")
        print(f"     （若 PASS==3：kb 播种生效，Day 27 的 401 瞎编问题已解决）")

        # ── 第二轮：同 thread 追问补 2 条边界（增量报告）──
        instruction2: str = (
            "很好。请再补充 2 条边界用例：\n"
            "① 空手机号（期望 400）② 手机号格式错误，如 12345（期望 400）\n"
            "用 run_api_test 执行后，**只输出新增用例**的 TestReport（feature 填 '用户登录-补充测试'）"
        )
        result2: dict[str, object] = agent.invoke(
            {"messages": [HumanMessage(content=instruction2)]}, config=config
        )
        report2: TestReport | None = extract_report(result2)
        if report2 is None:
            print("❌ 第二轮未拿到增量 TestReport")
            return None
        md2: str = render_test_report(report2)
        v2_path: str = os.path.join(out_dir, "login_test_report_followup.md")
        with open(v2_path, "w", encoding="utf-8") as f:
            f.write(md2)
        print(f"  ③ 第二轮追问完成：增量 {len(report2.items)} 条 → {v2_path}")

        # ── 合并（确定性代码）：同 id 去重，统计由 render 推导 ──
        merged: TestReport = merge_reports(report1, report2)
        merged_md: str = render_test_report(merged)
        merged_path: str = os.path.join(out_dir, "login_test_report_merged.md")
        with open(merged_path, "w", encoding="utf-8") as f:
            f.write(merged_md)
        print(f"  ④ 合并报告：{len(merged.items)} 条（去重后）→ {merged_path}")
        print(merged_md[:700])
        return merged_path
    finally:
        stop_mock()


def exp_fail_branch(port: int = 8766) -> str | None:
    """埋 Bug 靶场：错误凭据 → 500 → 1 FAIL → analyze_bug_report → 缺陷报告落盘。

    与 exp_full_pass_followup 的唯一区别：start_mock(port, bug_mode=True)。
    预期：2 PASS（正常/短密码）+ 1 FAIL（错误凭据 → 500）→ 报告含缺陷列表
    → 结论"需修复后回归"。FAIL 让 analyze_bug_report 工具首次真正上岗。
    返回：缺陷报告路径（未拿到 TestReport 返回 None）。
    """
    print("=" * 60)
    print("实验：exp_fail_branch —— 埋 Bug 靶场（错误凭据 → 500 → FAIL）")
    written: int = seed_kb()
    print(f"  ① 知识库已播种测试账号（写入 {written} 条片段，幂等）")
    server = start_mock(port, bug_mode=True)
    try:
        agent = build_agent_v4(InMemorySaver(serde=make_serde()))
        config: RunnableConfig = {"configurable": {"thread_id": "fail-branch"}, "recursion_limit": 50}
        instruction: str = (
            f"请为「用户登录」接口 http://127.0.0.1:{port}/api/login 做接口测试：\n"
            "1. 先用 kb_search 查询知识库中该接口的测试账号与历史用例\n"
            "2. 生成 3 条用例：正确账号密码登录（期望 200）/ 密码少于8位（期望 400）/ 错误凭据（期望 401）\n"
            "3. 用 run_api_test 逐条执行（method=POST，payload 传 JSON 字符串，凭据用知识库里查到的测试账号）\n"
            "4. 执行失败的用例 → 用 analyze_bug_report 分析根因\n"
            "5. 把结果整理成 TestReport 输出（status 如实填 PASS/FAIL/BLOCKED）"
        )
        result: dict[str, object] = agent.invoke(
            {"messages": [HumanMessage(content=instruction)]}, config=config
        )
        report: TestReport | None = extract_report(result)
        if report is None:
            print("❌ 未拿到 TestReport（打开 LangSmith 看最后几轮）")
            return None
        md: str = render_test_report(report)
        out_dir: str = os.path.join(os.path.dirname(__file__), "..", "..", "outputs")
        os.makedirs(out_dir, exist_ok=True)
        out_path: str = os.path.join(out_dir, "login_test_report_fail.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(md)
        failed: int = sum(1 for it in report.items if it.status == "FAIL")
        print(f"  FAIL 数 = {failed}（埋 Bug 靶场预期 1）→ {out_path}")
        print(md[:900])
        return out_path
    finally:
        stop_mock()

#===========================================================================
if __name__ == "__main__":
    # exp_merge_demo()
    # exp_full_pass_followup()   # 真实 API + mock 靶场，默认注释；想跑就取消注释
    exp_fail_branch()          # 真实 API + 埋 Bug 靶场，默认注释；想跑就取消注释（步骤 4）
    print("\n💡 要点回顾：")
    print("   seed_kb：RAG 即插拔记忆——不改 Agent 代码，kb 加一条凭据文档就修好端到端")
    print("   merge_reports：多轮补测 = 增量报告 + 确定性合并（id 去重，统计归 render）")
    print("   exp_fail_branch：埋 Bug 靶场让 analyze_bug_report 首次真正上岗")