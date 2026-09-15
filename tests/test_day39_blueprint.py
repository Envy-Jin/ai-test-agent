# FILE: test_day39_blueprint.py —— 真实落地到 ai_test_agent/tests/test_day39_blueprint.py
"""Day 39：蓝图层核心单元测试（纯函数 / 零 API / 零执行）。

被测对象（全部来自 day34_flow_map + day35_scenario）：
  build_blueprint          蓝图工厂（9 段 / 档位 8 段 / 每次新建对象）
  scan_blueprint           盘点五态（用 monkeypatch 把"文件是否存在"换成受控替身）
  select_stages            依赖闭包（顺序守恒 / 边界 / 不改入参）
  find_blueprint_contract_violations  蓝图契约（输出唯一性 / 路径规范化）
  exp1_login_parity        与 Day 34 BLUEPRINT 的契约等价回归

⚠️ 为什么不依赖真实文件系统状态：`scan_blueprint` 靠 `_exists_nonempty` 判产物在不在，
   真实 outputs/ 会随执行变化 → 直接断言会"今天绿明天红"。用 monkeypatch 换成受控
   替身，把测试钉在**判定逻辑**上，而不是钉在**当前磁盘状态**上。

运行（ai_test_agent 项目根）：
    .venv/Scripts/python.exe -m pytest tests/test_day39_blueprint.py -q
"""
from __future__ import annotations

import pytest

import day35_scenario
from day34_flow_map import StageSpec
from day35_scenario import (
    LOGIN_SCENARIO,
    REGISTER_SCENARIO,
    ScenarioConfig,
    build_blueprint,
    exp1_login_parity,
    find_blueprint_contract_violations,
    scan_blueprint,
    select_stages,
)

EXPECTED_STAGE_IDS: list[str] = [
    "S1_requirement_cases",
    "S2_case_review_gate",
    "S3_api_plan",
    "S4_test_codegen",
    "S5_test_data",
    "S6_execute_normal",
    "S7_execute_bug",
    "S8_exec_report",
    "S9_bug_analyze",
]


# ═══════════════════════════════════════════════════════
# build_blueprint：蓝图工厂
# ═══════════════════════════════════════════════════════
def test_login_blueprint_has_nine_stages_in_order() -> None:
    """LOGIN 默认档位：9 段，且顺序与 Day 34 蓝图一致（顺序即拓扑序）。"""
    blueprint = build_blueprint(LOGIN_SCENARIO)
    assert [spec.stage_id for spec in blueprint] == EXPECTED_STAGE_IDS


def test_bug_probe_off_drops_s7_and_fixes_report_inputs() -> None:
    """档位关闭：摘 S7，且 S8 报告输入自适应（不再喂 junit_bug.xml，防悬空断链）。"""
    blueprint = build_blueprint(LOGIN_SCENARIO.model_copy(update={"bug_probe": False}))
    ids: list[str] = [spec.stage_id for spec in blueprint]
    assert ids == [sid for sid in EXPECTED_STAGE_IDS if sid != "S7_execute_bug"]
    report_spec: StageSpec = next(s for s in blueprint if s.stage_id == "S8_exec_report")
    assert not any(p.endswith("junit_bug.xml") for p in report_spec.inputs), report_spec.inputs


def test_bug_probe_off_also_trims_report_outputs() -> None:
    """档位关闭：S8 的 outputs 也必须只剩 normal 一份（Day 39 / 5.3b 的 P0 修复）。

    为什么必须单独钉 outputs：只修剪 inputs 是"半修"——执行器 `_run_exec_report`
    不看 inputs，它按 `outputs` 决定渲染几份。outputs 仍要两份时，干净环境会因缺
    `junit_bug.xml` 整段 run_failed（Day 38 文档 5.5.1 的实测缺陷）。
    """
    blueprint = build_blueprint(LOGIN_SCENARIO.model_copy(update={"bug_probe": False}))
    report_spec: StageSpec = next(s for s in blueprint if s.stage_id == "S8_exec_report")
    assert report_spec.outputs == ["outputs/flow/exec_report_normal.md"], report_spec.outputs


def test_bug_probe_on_keeps_both_report_outputs() -> None:
    """档位开启（默认）：S8 仍是两份报告 —— 修复不能顺手改掉默认行为。"""
    blueprint = build_blueprint(LOGIN_SCENARIO)
    report_spec: StageSpec = next(s for s in blueprint if s.stage_id == "S8_exec_report")
    assert report_spec.outputs == [
        "outputs/flow/exec_report_normal.md",
        "outputs/flow/exec_report_bug.md",
    ], report_spec.outputs


def test_build_blueprint_returns_fresh_objects_each_call() -> None:
    """每次调用都新建 StageSpec —— 防止"优化成 return list(BLUEPRINT)"引入共享副作用。

    `list(BLUEPRINT)` 只复制外层列表，内层 StageSpec 仍是同一批对象；
    而 `_apply_bug_probe` 会**就地**改 S8.inputs → 一次 --no-bug-probe 调用
    就会永久污染后续所有调用（Day 39 文档步骤 3 记录的隐患）。
    """
    first = build_blueprint(LOGIN_SCENARIO)
    second = build_blueprint(LOGIN_SCENARIO)
    assert first[0] is not second[0]

    first[0].inputs = ["outputs/被就地改过的文件.json"]  # 就地污染第一次调用
    third = build_blueprint(LOGIN_SCENARIO)
    assert third[0].inputs == [LOGIN_SCENARIO.requirement_doc], third[0].inputs


# ═══════════════════════════════════════════════════════
# scan_blueprint：盘点五态（受控文件系统替身）
# ═══════════════════════════════════════════════════════
def test_scan_status_matrix_when_nothing_on_disk(monkeypatch: pytest.MonkeyPatch) -> None:
    """磁盘全空：code 段 run_ready（上游是流内产物）、llm 段缺外部输入 missing_input。"""
    monkeypatch.setattr(day35_scenario, "_exists_nonempty", lambda path_rel: False)
    statuses: dict[str, str] = {
        spec.stage_id: status
        for spec, status, _ in scan_blueprint(build_blueprint(LOGIN_SCENARIO))
    }
    assert statuses == {
        "S1_requirement_cases": "missing_input",   # 缺需求文档（外部输入）
        "S2_case_review_gate": "manual_pending",   # manual 永远等人
        "S3_api_plan": "missing_input",            # 缺接口文档（外部输入）
        "S4_test_codegen": "run_ready",            # 输入是 S3 的产出 → 流内豁免
        "S5_test_data": "missing_input",           # 缺 schema 资产（外部输入）
        "S6_execute_normal": "run_ready",          # 输入是 S4 的产出
        "S7_execute_bug": "run_ready",             # 输入是 S4 的产出
        "S8_exec_report": "missing_input",         # 缺 api_registry.json（外部输入）
        "S9_bug_analyze": "missing_input",         # 缺 Bug 文档（外部输入）
    }


def test_scan_status_all_reused_when_everything_present(monkeypatch: pytest.MonkeyPatch) -> None:
    """磁盘齐全：除 manual 外全部 reused（产物在位 → 断点续跑）。"""
    monkeypatch.setattr(day35_scenario, "_exists_nonempty", lambda path_rel: True)
    rows = scan_blueprint(build_blueprint(LOGIN_SCENARIO))
    statuses: dict[str, str] = {spec.stage_id: status for spec, status, _ in rows}
    assert statuses["S2_case_review_gate"] == "manual_pending"
    assert set(statuses.values()) == {"reused", "manual_pending"}


def test_scan_register_reports_missing_input(monkeypatch: pytest.MonkeyPatch) -> None:
    """register 场景（缺 schemas / bugs 资产）：盘点把缺口精确到"外部输入缺失"。"""
    monkeypatch.setattr(day35_scenario, "_exists_nonempty", lambda path_rel: False)
    rows = scan_blueprint(build_blueprint(REGISTER_SCENARIO))
    statuses: dict[str, str] = {spec.stage_id: status for spec, status, _ in rows}
    assert statuses["S5_test_data"] == "missing_input"
    assert statuses["S9_bug_analyze"] == "missing_input"


def test_scan_status_values_are_within_contract() -> None:
    """真实文件系统下的盘点：状态取值必须落在约定五态内（不锁死具体状态，避免环境漂移）。"""
    allowed: set[str] = {"reused", "run_ready", "needs_api", "manual_pending", "missing_input"}
    rows = scan_blueprint(build_blueprint(LOGIN_SCENARIO))
    assert {status for _, status, _ in rows} <= allowed
    assert next(s for s, _, _ in rows if s.stage_id == "S2_case_review_gate").kind == "manual"


# ═══════════════════════════════════════════════════════
# select_stages：依赖闭包
# ═══════════════════════════════════════════════════════
def test_select_stages_closure_fills_upstream(login_blueprint: list[StageSpec]) -> None:
    """只点 S8 → 闭包自动补齐 S3/S4/S6/S7，且保持原蓝图顺序。

    `login_blueprint` 来自 tests/conftest.py 的共享夹具（pytest 按参数名注入）。
    """
    subset = select_stages(login_blueprint, {"S8_exec_report"})
    assert [spec.stage_id for spec in subset] == [
        "S3_api_plan",
        "S4_test_codegen",
        "S6_execute_normal",
        "S7_execute_bug",
        "S8_exec_report",
    ]


def test_select_stages_excludes_unrelated_stages(login_blueprint: list[StageSpec]) -> None:
    """闭包 ≠ 全集：S1（无人消费其产出）与 S9（输入是外部文档）不在 S8 上游链上。"""
    subset = select_stages(login_blueprint, {"S8_exec_report"})
    ids: list[str] = [spec.stage_id for spec in subset]
    assert "S1_requirement_cases" not in ids
    assert "S9_bug_analyze" not in ids
    assert "S2_case_review_gate" not in ids


def test_select_stages_single_external_input_stage_is_self_only() -> None:
    """S9 的输入全是外部文档 → 闭包只有它自己（最少段）。"""
    subset = select_stages(build_blueprint(LOGIN_SCENARIO), {"S9_bug_analyze"})
    assert [spec.stage_id for spec in subset] == ["S9_bug_analyze"]


def test_select_stages_preserves_original_order() -> None:
    """顺序不变量：结果必须等于"按原蓝图顺序过滤"，而不是 set 重新拼装。"""
    blueprint = build_blueprint(LOGIN_SCENARIO)
    subset = select_stages(blueprint, {"S6_execute_normal", "S1_requirement_cases"})
    ids: list[str] = [spec.stage_id for spec in subset]
    assert ids == [spec.stage_id for spec in blueprint if spec.stage_id in set(ids)]
    assert ids.index("S1_requirement_cases") < ids.index("S6_execute_normal")


def test_select_stages_producer_before_consumer() -> None:
    """拓扑序不变量：生产者必须排在消费者之前。"""
    ids: list[str] = [
        spec.stage_id
        for spec in select_stages(build_blueprint(LOGIN_SCENARIO), {"S8_exec_report"})
    ]
    assert ids.index("S3_api_plan") < ids.index("S4_test_codegen")
    assert ids.index("S4_test_codegen") < ids.index("S6_execute_normal")
    assert ids.index("S6_execute_normal") < ids.index("S8_exec_report")
    assert ids.index("S7_execute_bug") < ids.index("S8_exec_report")


def test_select_stages_empty_and_unknown_are_silent() -> None:
    """边界：空 wanted → []；全未知 id → []（纯函数静默，是否报错由入口层决定）。"""
    blueprint = build_blueprint(LOGIN_SCENARIO)
    assert select_stages(blueprint, set()) == []
    assert select_stages(blueprint, {"S99_not_exist"}) == []


def test_select_stages_does_not_mutate_input() -> None:
    """纯函数契约：不修改传入蓝图（返回新列表）。"""
    blueprint = build_blueprint(LOGIN_SCENARIO)
    before: list[str] = [spec.stage_id for spec in blueprint]
    select_stages(blueprint, {"S8_exec_report"})
    assert [spec.stage_id for spec in blueprint] == before


# ═══════════════════════════════════════════════════════
# 蓝图契约：输出唯一性 + 路径规范化（Day 39 新增）
# ═══════════════════════════════════════════════════════
@pytest.mark.parametrize(
    "scenario",
    [LOGIN_SCENARIO, REGISTER_SCENARIO],
    ids=["login", "register"],
)
def test_blueprint_contract_has_no_violations(scenario: ScenarioConfig) -> None:
    """真实蓝图零违规：输出路径全局唯一、路径写法规范。

    这条测试是 `select_stages.by_output` 的"护栏"——一旦将来有人给蓝图加了
    重复输出或 ./ 前缀，这里立刻红，而不是等到执行期 run_failed。
    """
    assert find_blueprint_contract_violations(build_blueprint(scenario)) == []


def test_contract_detects_duplicate_output() -> None:
    """负向：两个 stage 声明同一输出文件 → 必须被检出（否则 by_output 静默覆盖）。"""
    bad: list[StageSpec] = [
        StageSpec(stage_id="A_produce", title="a", source="test", kind="code",
                  outputs=["out/same.json"]),
        StageSpec(stage_id="B_produce", title="b", source="test", kind="code",
                  outputs=["out/same.json"]),
    ]
    violations: list[str] = find_blueprint_contract_violations(bad)
    assert any("输出重复" in v for v in violations), violations


@pytest.mark.parametrize("bad_path", ["./out/plan.json", "out\\plan.json"])
def test_contract_detects_unnormalized_path(bad_path: str) -> None:
    """负向：路径带 ./ 前缀或反斜杠 → 必须被检出（索引逐字匹配，写法不同=匹配不上）。"""
    bad: list[StageSpec] = [
        StageSpec(stage_id="A", title="a", source="test", kind="code", inputs=[bad_path]),
    ]
    assert any("路径未规范化" in v for v in find_blueprint_contract_violations(bad))


def test_contract_allows_manual_without_outputs() -> None:
    """manual 段本来就没有 outputs（S2 评审门）→ 不算违规。"""
    manual_only: list[StageSpec] = [
        StageSpec(stage_id="S2_gate", title="评审门", source="test", kind="manual",
                  inputs=["out/req.json"]),
    ]
    assert find_blueprint_contract_violations(manual_only) == []


# ═══════════════════════════════════════════════════════
# 契约等价回归：工厂产物 vs Day 34 BLUEPRINT
# ═══════════════════════════════════════════════════════
def test_factory_blueprint_parity_with_day34() -> None:
    """工厂蓝图与 Day 34 BLUEPRINT 契约全等（0 diffs）——重构不许悄悄改契约。"""
    assert exp1_login_parity() == 0
