"""Day 34 练习 1：五专项资产盘点 + 全流程蓝图（StageSpec 契约表）。

周末综合项目的"蓝图层"：把 Day 29-33 五个专项抽象成 9 个 stage，每个
stage 只声明契约（输入文件 / 输出文件 / 性质 / 来源），不包含任何业务实现。
业务实现留在五专项模块里；本脚本只回答一个问题：
"哪些段的产物已经在（可回放），哪些缺（要补）？"

性质三态（分界线思想在流程层的落地）：
  llm     模型段：语义判断（分析链），真 API，产物缺时需 --with-llm 补跑
  code    代码段：确定性工程（渲染/造数/统计/执行），执行器全自动跑
  manual  人工段：评审/决策（S2 两段式评审门占位，Day 35 落地），永远等人

资产盘点四态（scan_assets 的判定，全零 API）：
  reused        输出产物在位且非空 → 断点续跑（回放）
  run_ready     code 段输入齐、产物缺 → 执行器现场跑
  needs_api     llm 段输入齐、产物缺 → --with-llm 补跑（真 API）
  manual_pending manual 段 → 永远等人
  missing_input 外部输入缺失 → 先补（蓝图内无任何 stage 产出的文件，如需求文档/注册表；
                 由上游 stage 产出的"流内依赖"（如 S6→S8 的 junit）不算缺失）

实验（cd src/agent，零 API）：
  python -c "from day34_flow_map import exp1_scan_assets; exp1_scan_assets()"
  python day34_flow_map.py       # main 完成态：exp1 + 落盘 outputs/flow/flow_map.md
"""
from __future__ import annotations

import os
import sys

from pydantic import BaseModel, Field
from typing import Literal

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

# ── 路径基准钉 __file__（2026-08-28 规范：蓝图相对项目根，这里统一解析）──
_AGENT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_ROOT: str = os.path.dirname(os.path.dirname(_AGENT_DIR))  # src/agent → 项目根
FLOW_DIR: str = os.path.join(_ROOT, "outputs", "flow")

# ═══════════════════════════════════════════════════════
# Schema：stage 契约（练习 1 —— 黑盒：只有输入/输出/性质，没有实现）
# ═══════════════════════════════════════════════════════
StageKind = Literal["llm", "code", "manual"]
RunnerKind = Literal["cmd", "mock_pytest", "exec_report"]
ScanStatus = Literal["reused", "run_ready", "needs_api", "manual_pending", "missing_input"]


class StageSpec(BaseModel):
    """全流程蓝图中的一个阶段（黑盒契约）。

    inputs/outputs 一律写【相对项目根】的路径；执行器基于 __file__ 统一解析。
    runner 决定执行器怎么跑这一段：
      cmd          执行 cmd 字段的 python -c 语句（llm 段仅 --with-llm 时执行）
      mock_pytest 内置：start_mock(port, mock_bug) → pytest 套件 --junitxml → stop
      exec_report  内置：读 junit + 注册表 → 渲染执行报告
    """

    stage_id: str
    title: str
    source: str                     # 实现归属：day29 / day30 / day32 / day33 / Day35 / 综合
    kind: StageKind
    runner: RunnerKind = "cmd"
    inputs: list[str] = Field(default_factory=list)      # 相对项目根
    outputs: list[str] = Field(default_factory=list)     # 相对项目根
    cmd: str = ""                                        # python -c 语句体（cmd runner）
    mock_bug: bool = False                               # mock_pytest runner：埋 Bug 开关
    # Day 41 新增：mock 监听端口 + 实现哪套接口（mock_pytest runner 用）。
    # 为什么必须进契约：执行器原来用模块常量 `MOCK_PORT` 起 mock、用的还是写死的
    # login handler，蓝图里写的端口**只是个注释**——声明与执行不同源，第二个场景
    # （register，8767 + /api/register）一上就打到空气（一片 404 却仍判 run_ok）。
    # 契约：mock_port 必须与接口文档 base_url 的端口一致、mock_scenario 必须等于场景名
    #       （见 day35_scenario 的 find_scenario_contract_violations）。
    mock_port: int = 8766
    mock_scenario: str = "login"
    note: str = ""


# ═══════════════════════════════════════════════════════
# 全流程蓝图（练习 1 —— 测试全流程 Agent 的设计图，9 段）
# ═══════════════════════════════════════════════════════
BLUEPRINT: list[StageSpec] = [
    StageSpec(
        stage_id="S1_requirement_cases",
        title="需求解析 → 分级用例",
        source="day29",
        kind="llm",
        inputs=["docs/requirements/login_requirement.md"],
        outputs=["outputs/requirement_login_analysis.json", "outputs/requirement_login_analysis.md"],
        cmd="from day29_requirement_analysis import exp2_analyze_file; "
            "exp2_analyze_file('../../docs/requirements/login_requirement.md', 'login')",
        note="真 API：分析 Chain 生成分级用例 → 质检 → 落盘（name='login'）",
    ),
    StageSpec(
        stage_id="S2_case_review_gate",
        title="用例评审闸门（占位）",
        source="day35",
        kind="manual",
        inputs=["outputs/requirement_login_analysis.json"],
        note="两段式评审门（Day 35）：exp_generate 落盘止 → exp_seed_approved 读回打 reviewed → "
             "upsert 硬门禁。今天只占位，永远 manual_pending",
    ),
    StageSpec(
        stage_id="S3_api_plan",
        title="接口文档 → 接口测试计划",
        source="day30",
        kind="llm",
        inputs=["docs/apis/login_api.md"],
        outputs=["outputs/api_test_plan_login.json", "outputs/api_test_plan_login.md"],
        cmd="from day30_api_schema import exp2_analyze_file; "
            "exp2_analyze_file('../../docs/apis/login_api.md', 'login')",
        note="真 API：.md 人写文档 → ApiDoc（模型）→ 三件套计划（代码）→ 落盘",
    ),
    StageSpec(
        stage_id="S4_test_codegen",
        title="计划 → pytest 代码（确定性渲染）",
        source="day30",
        kind="code",
        runner="cmd",
        inputs=["outputs/api_test_plan_login.json"],
        outputs=["outputs/generated_tests/conftest.py", "outputs/generated_tests/test_api_suite.py"],
        cmd="from day30_pytest_generator import generate_api_tests_from_plan; "
            "print(generate_api_tests_from_plan('../../outputs/api_test_plan_login.json', "
            "'../../outputs/generated_tests'))",
        note="确定性段：同输入同输出（练习 3 --force 重跑验证指纹不变）；ast.parse 校验后落盘",
    ),
    StageSpec(
        stage_id="S5_test_data",
        title="字段规则 → 测试数据",
        source="day32",
        kind="llm",
        inputs=["docs/schemas/users.md", "docs/schemas/orders.json"],
        outputs=["outputs/data_gen/users_normal.json", "outputs/data_gen/orders_normal.json"],
        cmd="from day32_run_pipeline import exp6_pipeline; exp6_pipeline()",
        note="双输入分派：users.md 走模型解析、orders.json 走 json.loads（确定性段内置）",
    ),
    StageSpec(
        stage_id="S6_execute_normal",
        title="执行：mock 正常版 → JUnit XML",
        source="day30/综合",
        kind="code",
        runner="mock_pytest",
        mock_bug=False,
        inputs=["outputs/generated_tests/test_api_suite.py"],
        outputs=["outputs/flow/junit_normal.xml"],
        note="执行器内置：start_mock(8766, False) → pytest 生成套件(7 node) --junitxml → stop",
    ),
    StageSpec(
        stage_id="S7_execute_bug",
        title="执行：mock 埋 Bug 版 → JUnit XML（对照回路）",
        source="day30/综合",
        kind="code",
        runner="mock_pytest",
        mock_bug=True,
        inputs=["outputs/generated_tests/test_api_suite.py"],
        outputs=["outputs/flow/junit_bug.xml"],
        note="同一套用例只切 bug_mode=True → 抓「埋 Bug」缺陷（错误凭据 500 / 越权 200）",
    ),
    StageSpec(
        stage_id="S8_exec_report",
        title="JUnit → 执行报告（缺陷反查注册表）",
        source="day33/综合",
        kind="code",
        runner="exec_report",
        inputs=[
            "outputs/flow/junit_normal.xml",
            "outputs/flow/junit_bug.xml",
            "docs/cases/api_registry.json",
        ],
        outputs=["outputs/flow/exec_report_normal.md", "outputs/flow/exec_report_bug.md"],
        note="统计归代码（day33 summarize/find_defects）；node id → 注册表 TC 反查",
    ),
    StageSpec(
        stage_id="S9_bug_analyze",
        title="Bug 报告 → 结构化分析（批量+聚合）",
        source="day31",
        kind="llm",
        inputs=["docs/bugs/login_bugs.md"],
        outputs=[
            "outputs/bug_login_analysis.json",
            "outputs/bug_login_analysis.md",
            "outputs/bug_login_batch_report.md",
        ],
        cmd="from day31_bug_analyzer import exp4_batch_pipeline; "
            "exp4_batch_pipeline('../../docs/bugs/login_bugs.md', 'login', False)",
        note="真 API：分割 → 逐条分析 → 聚合统计 → 报表落盘（入库 reviewed=False 走提示）",
    ),
]


# ═══════════════════════════════════════════════════════
# 资产盘点（练习 1 —— 零 API 判定）
# ═══════════════════════════════════════════════════════
# 蓝图内"上游产出"的集合：S8 的输入 junit_normal.xml 由 S6 产出——
# 流内依赖在盘点时可能还没生成，不阻塞判定；只有"外部输入"（任何
# stage 都不产出的文件）缺失才算 missing_input。
PRODUCED_OUTPUTS: frozenset[str] = frozenset(
    p for spec in BLUEPRINT for p in spec.outputs
)


def _abs(path_rel: str) -> str:
    """相对项目根的路径 → 绝对路径（钉 __file__）。"""
    return os.path.join(_ROOT, path_rel)


def _exists_nonempty(path_rel: str) -> bool:
    """文件存在且非空（空文件 = 失败产物，不算数）。"""
    abs_path: str = _abs(path_rel)
    return os.path.isfile(abs_path) and os.path.getsize(abs_path) > 0


def scan_stage(spec: StageSpec) -> tuple[ScanStatus, str]:
    """盘点单个 stage：产物在 → reused；缺产物按性质分派（零 API）。

    输入缺失只检查"外部输入"——蓝图内其他 stage 会产出的文件（如 S6 → S8
    的 junit XML）是流内依赖，本轮执行会按顺序生成，盘点时不视为缺失。
    """
    if spec.kind == "manual":
        return "manual_pending", spec.note
    if all(_exists_nonempty(p) for p in spec.outputs):
        return "reused", "产物在位且非空，可回放（指纹由执行器算）"
    missing: list[str] = [
        p for p in spec.inputs
        if p not in PRODUCED_OUTPUTS and not _exists_nonempty(p)
    ]
    if missing:
        return "missing_input", "外部输入缺失：" + missing[0]
    if spec.kind == "llm":
        return "needs_api", "输入齐、产物缺 → --with-llm 补跑（真 API）"
    return "run_ready", "code 段：执行器现场自动跑"


def scan_assets() -> list[tuple[StageSpec, ScanStatus, str]]:
    """按蓝图顺序盘点全部 stage。"""
    rows: list[tuple[StageSpec, ScanStatus, str]] = []
    for spec in BLUEPRINT:
        status, reason = scan_stage(spec)
        rows.append((spec, status, reason))
    return rows


def render_flow_map_markdown(rows: list[tuple[StageSpec, ScanStatus, str]]) -> str:
    """蓝图盘点表 → Markdown（列表拼接 + join，不碰 f-string 花括号）。"""
    lines: list[str] = [
        "# 测试全流程 Agent：蓝图 + 资产盘点",
        "",
        f"**项目根**: `{_ROOT}`",
        "",
        "| # | 阶段 | 来源 | 性质 | 执行器 | 状态 | 说明 |",
        "|---|------|------|------|--------|------|------|",
    ]
    for spec, status, reason in rows:
        runner_label: str = {
            "cmd": "cmd",
            "mock_pytest": "mock+pytest",
            "exec_report": "报告渲染",
        }[spec.runner]
        lines.append(
            f"| {spec.stage_id} | {spec.title} | {spec.source} | {spec.kind} | {runner_label} "
            f"| {status} | {reason} |"
        )
    lines.append("")
    lines.append("## 状态汇总")
    counts: dict[str, int] = {}
    for _, status, _ in rows:
        counts[status] = counts.get(status, 0) + 1
    lines.append("、".join(f"{k}={v}" for k, v in sorted(counts.items())))
    lines.append("")
    lines.append("> 缺口清单 = 周末训练任务：`needs_api` 段用 `--with-llm` 补跑；`run_ready` 段由执行器自动跑；`manual_pending` 段等 Day 35 评审门。")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════
# 实验（练习 1：零 API 盘点 + 落盘蓝图）
# ═══════════════════════════════════════════════════════
def exp1_scan_assets() -> None:
    """盘点全流程资产 → 打印状态表 + 落盘 outputs/flow/flow_map.md（零 API）。"""
    rows = scan_assets()
    print("=" * 72)
    print("全流程蓝图资产盘点（零 API）：")
    for spec, status, reason in rows:
        print(f"  [{status:<14}] {spec.stage_id:<22} {spec.title}  <- {spec.source}")
    os.makedirs(FLOW_DIR, exist_ok=True)
    md_path: str = os.path.join(FLOW_DIR, "flow_map.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_flow_map_markdown(rows))
    print(f"✅ 蓝图落盘: {md_path}")
    reused = sum(1 for _, s, _ in rows if s == "reused")
    print(f"✅ 汇总：reused={reused} / run_ready+needs_api+manual 见上表（缺口=待补）")



if __name__ == "__main__":
    exp1_scan_assets()
