"""Day 36 练习 3：蓝图 v2 扩展原型 —— 缺陷生命周期闭环 + 变更驱动回归 + Go/No-Go 收口。

背景（2026-09-08 资深评审收敛 → Day36 重构并入）：
  Day 34 的 BLUEPRINT（S1-S9）是「最小可运行教学闭环」，评审确认 4 个方向性缺口要补：
    P0-1 缺陷生命周期断头：S6/S7 抓到的缺陷进 S9 分析后没有 修复→验证修复→关闭 回路
         （S9 只是「历史 Bug 知识化」，不是本次缺陷的生命周期）→ 新增 S10 triage / S11 fix /
          S12 verify（验证修复复用 S6/S7 mock 双回路，mock_bug=False 跑修复版）
    P0-2 变更驱动回归缺位：day33 回归分析器游离在流程外 → 新增 change_regression 阶段
          （diff → 影响面 → 回归集 → 基线对比，day33 现成资产直接承接）
    P0-4 无收口决策层：S8 是执行快照，没有质量结论/放行决策 → 新增 go_nogo_gate 阶段
          （读前序报告汇总，输出 Go/No-Go；day33 conclusion 字段语义复用）
    S7 语义重定位（立即，成本≈0）：S7 埋 Bug mock = 测试资产自验证（变异测试轻量近似），
          不是「被测系统的环境维度」——v2 里给 S7 阶段打语义标注，不改执行。
  核心设计红线 = Day 34 黑盒红利：v2 只改「蓝图数据」（插阶段/打标注），执行器零改动。

  本脚本 = v2 扩展原型（纯 stdlib，零 API）：
    1. StageLike Protocol：对任何「长成蓝图阶段样子的对象」工作（day34 StageSpec / 内置 demo）
    2. NEW_STAGE_LIBRARY：v2 增补阶段库（含注入锚点 inject_after）
    3. build_v2(stages, include)：v1 阶段序列 → v2 序列（锚点后插段 + @{prev_outputs} 产物桥接
       + S7 语义补丁），插段不改执行器，只改数据
    4. validate_chain(entries)：产物链闭包校验（input 必须能被上游产出或属外部资产 docs/）
    5. gate_for(kind)：分级闸门策略表（非确定性产物人审 / 确定性产物机检）→ 打印策略行
  demo-first：内置 demo v1 蓝图（6 段，产物命名真实）；真实 day34 BLUEPRINT 可选 attach（importlib
  探测，找不到不报错）。

实验↔步骤↔运行命令 映射：
  exp1_demo()       步骤4(教学演示)  python -c "from day36_blueprint_v2 import exp1_demo; exp1_demo()"
  exp2_attach_real() 步骤4(真实蓝图) python -c "from day36_blueprint_v2 import exp2_attach_real; exp2_attach_real()"
  main()            步骤4(全流程)    python day36_blueprint_v2.py [--real]
"""
from __future__ import annotations

import importlib
import sys
from dataclasses import dataclass, field
from typing import Iterable, Literal, Protocol

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]


# ═══════════════════════════════════════════════════════════════
# 1. 蓝图阶段「形状」协议（黑盒契约最小面）
# ═══════════════════════════════════════════════════════════════

class StageLike(Protocol):
    """任何蓝图阶段对象必须提供的最小字段集（Day35 断言边界的子集）。

    day34 的 pydantic StageSpec 与内置 demo 阶段都满足该形状 —— v2 工具对两者透明。
    """

    stage_id: str
    kind: str
    runner: str
    inputs: list[str]
    outputs: list[str]
    mock_bug: bool


# ═══════════════════════════════════════════════════════════════
# 2. 蓝图 v2 数据模型
# ═══════════════════════════════════════════════════════════════

@dataclass
class V2Entry:
    """蓝图 v2 里的一个阶段（v1 原样搬入或 v2 注入新增）。gate 为分级闸门判定。"""

    stage_id: str
    kind: str
    runner: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    mock_bug: bool = False
    origin: Literal["v1", "v2"] = "v1"
    semantics: str = ""  # 语义标注（S7 重定位落在这里）
    gate: Literal["human", "machine", "review"] = "review"


@dataclass
class V2StageSpec:
    """v2 增补阶段库的一条定义。inject_after 前缀匹配 v1 stage_id；找不到 → 追加尾部并告警。"""

    code: str
    title: str
    kind: str
    runner: str
    inputs: list[str] = field(default_factory=list)     # 支持 "@{prev_outputs}" 产物桥接 token
    outputs: list[str] = field(default_factory=list)
    mock_bug: bool = False
    inject_after: str = ""                              # v1 stage_id 前缀锚
    semantics: str = ""


NEW_STAGE_LIBRARY: dict[str, V2StageSpec] = {
    # ── P0-2 变更驱动回归：插在 S4 代码生成之后（day33 现成资产承接）──
    "change_regression": V2StageSpec(
        code="S4.5_change_regression",
        title="变更驱动回归（diff → 影响面 → 回归集 → 基线对比）",
        kind="regression",
        runner="cmd",
        inputs=["docs/changes/auth_refactor.diff", "@{prev_outputs}"],
        outputs=["outputs/regression/regression_plan.json", "outputs/regression/report_after.md"],
        inject_after="S4",
        semantics="复用 day33 回归分析器/registry：变更范围 → 受影响用例 → 基线对比，游离资产并入主干",
    ),
    # ── 实验 ──
    "add_experiment_stage": V2StageSpec(
        code="S7.5_experiment_stage",
        title="尝试新加一个阶段",
        kind="regression",
        runner="cmd",
        inputs=["docs/changes/new_stage.txt"],
        outputs=["outputs/regression/new_stage.json", "outputs/regression/new_stage.md"],
        inject_after="S7",
        semantics="实验，手动新加一个阶段，观察是否可以正常进入蓝图",
    ),

    # ── P0-1 缺陷生命周期闭环：插在 S9 缺陷分析之后（S9 = 缺陷知识化入库，本次缺陷从这里接管）──
    "defect_triage": V2StageSpec(
        code="S10_defect_triage",
        title="缺陷分诊（triaged：定级/定模块/责任人）",
        kind="bug_triage",
        runner="cmd",
        inputs=["@{prev_outputs}"],
        outputs=["outputs/defect_triage.json"],
        inject_after="S9",
        semantics="本次执行缺陷从 S9 分析产物接管，进入状态机 triaged→fixed→verified→closed",
    ),
    "defect_fix": V2StageSpec(
        code="S11_defect_fix",
        title="缺陷修复（fixed：修复说明 + 提交）",
        kind="bug_fix",
        runner="cmd",
        inputs=["outputs/defect_triage.json"],
        outputs=["outputs/defect_fix_commit.json"],
        inject_after="S9",
        semantics="fix 产物 = 修复后的被测资产版本（mock 靶场开关位），非 AI 生成",
    ),
    "defect_verify": V2StageSpec(
        code="S12_defect_verify",
        title="修复验证（verified：mock 双回路跑修复版，mock_bug=False）",
        kind="execute",
        runner="mock_pytest",
        inputs=["outputs/defect_fix_commit.json", "@{prev_outputs}"],
        outputs=["outputs/junit_verify.xml", "outputs/bug_verify_report.md"],
        inject_after="S9",
        mock_bug=False,
        semantics="验证修复复用 S6/S7 双回路：同一套件跑修复版 → junit_verify 对比 S7 junit_bug 基线",
    ),
    # ── P0-4 收口决策层：Go/No-Go（读前序报告汇总；day33 conclusion 字段语义复用）──
    "go_nogo_gate": V2StageSpec(
        code="S13_go_nogo",
        title="收口决策（Go / No-Go：质量结论 + 遗留风险）",
        kind="decision",
        runner="cmd",
        inputs=[],
        outputs=["outputs/go_nogo_decision.md"],
        inject_after="S9",
        semantics="汇总前序报告 + defect_verify 结果 → conclusion 字段（day33 语义复用）→ 放行决策",
    ),
}

# 插入顺序：change_regression（锚 S4）→ defect_*（锚 S9）→ go_nogo（锚 S9，排在 defect 后）
_INJECT_ORDER: tuple[str, ...] = ("add_experiment_stage", "change_regression", "defect_triage", "defect_fix", "defect_verify", "go_nogo_gate")
_EXTERNAL_PREFIXES: tuple[str, ...] = ("docs/",)  # 外部资产放行前缀（需求/接口/schema 文档等）


# ═══════════════════════════════════════════════════════════════
# 3. 分级闸门策略（2026-09-08 评审：#3 的落法 = 分级，不是到处人审）
# ═══════════════════════════════════════════════════════════════

def gate_for(kind: str) -> Literal["human", "machine", "review"]:
    """按阶段 kind 判定闸门模式。

    非确定性产物（AI 生成/分析/评审类，每次输出不同）→ human（人审，对应 day35 评审门）；
    确定性产物（执行/编译/报告汇总/回归对比，同输入同输出）→ machine（机检：day35 断言 +
    py_compile/junit 自动比对），不重复人审。
    """
    k = kind.lower()
    if any(t in k for t in ("llm", "manual", "analysis", "generate", "parse", "review", "plan", "triage", "decision")):
        return "human"
    if any(t in k for t in ("code", "execute", "mock", "report", "codegen", "regression", "fix", "datagen")):
        return "machine"
    return "review"


# ═══════════════════════════════════════════════════════════════
# 4. v2 构建：v1 搬入 + 锚点插段 + 产物桥接 + S7 语义补丁
# ═══════════════════════════════════════════════════════════════

def _entry_from_v1(stage: StageLike) -> V2Entry:
    return V2Entry(
        stage_id=stage.stage_id,
        kind=stage.kind,
        runner=stage.runner,
        inputs=list(stage.inputs),
        outputs=list(stage.outputs),
        mock_bug=bool(stage.mock_bug),
        origin="v1",
        gate=gate_for(stage.kind),
    )


def _patch_s7_semantics(entries: list[V2Entry]) -> None:
    """S7 语义重定位（成本≈0，只加标注不改执行）：埋 Bug mock = 测试资产自验证。

    只对【v1 原蓝图】中以 S7 开头的阶段打补丁（origin == "v1"）——若对 v2 新注入的
    S7.x 也套用前缀匹配，会覆盖用户自写的 semantics（2026-09-09 手动加 stage 实验抓到的
    前缀误伤 bug：S7.5_experiment_stage 的 semantics 曾被强制覆盖成 S7 标注）。
    """
    for e in entries:
        if e.origin == "v1" and e.stage_id.startswith("S7") and "自验证" not in e.semantics:
            e.semantics = "测试资产自验证（变异测试轻量近似）——非被测系统环境维度；生产对应物 = 缺陷构建/回归基线"



def _expand_token(entries: list[V2Entry], anchor_idx: int, token: str) -> list[str]:
    """@{prev_outputs} → 锚点阶段（插入点前一 v1 阶段）的全部 outputs（产物桥接）。"""
    if token != "@{prev_outputs}":
        return [token]
    if anchor_idx >= 0 and anchor_idx < len(entries):
        return list(entries[anchor_idx].outputs)
    return []


def build_v2(
    stages: Iterable[StageLike],
    include: Iterable[str] = ("add_experiment_stage", "change_regression", "defect_triage", "defect_fix", "defect_verify", "go_nogo_gate"),
) -> tuple[list[V2Entry], list[str]]:
    """v1 阶段序列 → v2 序列。返回 (entries, warnings)。

    插段只改蓝图数据（黑盒红利：执行器零改动）；每次插段在锚点后追加，
    锚点 = 首个 stage_id 以 inject_after 开头的阶段。@ 前缀 inputs 做产物桥接。
    """
    entries: list[V2Entry] = [_entry_from_v1(s) for s in stages]
    warnings: list[str] = []
    include_set = set(include)
    inserted_at_anchor: dict[str, int] = {}  # 同一锚点已插入条数 → 保证同锚点按注入顺序排列

    def _anchor_pos(prefix: str) -> int:
        for i, e in enumerate(entries):
            if e.stage_id.startswith(prefix):
                return i
        return -1

    # 依次注入（同锚点的先后顺序由 _INJECT_ORDER 保证）
    for code in _INJECT_ORDER:
        if code not in include_set:
            continue
        spec = NEW_STAGE_LIBRARY[code]
        anchor = _anchor_pos(spec.inject_after)
        if anchor < 0:
            warnings.append(f"{spec.code} 找不到锚点前缀「{spec.inject_after}」→ 追加尾部")
            insert_at = len(entries)
            anchor_idx = insert_at - 1
        else:
            offset = inserted_at_anchor.get(spec.inject_after, 0)
            insert_at = anchor + 1 + offset
            anchor_idx = anchor
            inserted_at_anchor[spec.inject_after] = offset + 1
        new_inputs: list[str] = []
        for i in spec.inputs:
            new_inputs.extend(_expand_token(entries, anchor_idx, i))
        new_outputs: list[str] = []
        for o in spec.outputs:
            new_outputs.extend(_expand_token(entries, anchor_idx, o))
        entries.insert(
            insert_at,
            V2Entry(
                stage_id=spec.code,
                kind=spec.kind,
                runner=spec.runner,
                inputs=new_inputs,
                outputs=new_outputs,
                mock_bug=spec.mock_bug,
                origin="v2",
                semantics=spec.semantics,
                gate=gate_for(spec.kind),
            ),
        )
    _patch_s7_semantics(entries)
    return entries, warnings


# ═══════════════════════════════════════════════════════════════
# 5. 产物链闭包校验
# ═══════════════════════════════════════════════════════════════

def validate_chain(entries: list[V2Entry]) -> list[str]:
    """逐阶段校验 inputs 是否可被上游产出（或属 docs/ 外部资产）。返回问题清单（空 = 闭包完整）。"""
    produced: set[str] = set()
    errors: list[str] = []
    for e in entries:
        missing = [i for i in e.inputs if i not in produced and not i.startswith(_EXTERNAL_PREFIXES)]
        if missing:
            errors.append(f"{e.stage_id} 引用未产出资源：{missing}")
        produced.update(e.outputs)
    return errors


# ═══════════════════════════════════════════════════════════════
# 6. 内置 demo v1 蓝图（6 段迷你版，产物命名与真实形态同构）
# ═══════════════════════════════════════════════════════════════

@dataclass
class DemoStage:
    stage_id: str
    kind: str
    runner: str = "cmd"
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    mock_bug: bool = False


def demo_v1() -> list[DemoStage]:
    return [
        DemoStage("S1_requirement_cases", "analysis", "cmd",
                  ["docs/requirements/login_requirement.md"],
                  ["outputs/requirement_login_analysis.json", "outputs/cases_login.json"]),
        DemoStage("S2_case_review_gate", "review", "cmd",
                  ["outputs/cases_login.json"], ["outputs/cases_login_reviewed.json"]),
        DemoStage("S3_api_plan", "analysis", "cmd",
                  ["docs/apis/login_api.md"], ["outputs/api_plan_login.json"]),
        DemoStage("S4_test_codegen", "codegen", "cmd",
                  ["outputs/api_plan_login.json", "outputs/cases_login_reviewed.json"],
                  ["outputs/generated_tests/test_api_suite.py"]),
        DemoStage("S5_test_data", "datagen", "cmd",
                  ["docs/schemas/users.md"], ["outputs/data/users_mock.json"]),
        DemoStage("S6_execute_normal", "execute", "mock_pytest",
                  ["outputs/generated_tests/test_api_suite.py", "outputs/data/users_mock.json"],
                  ["outputs/junit_normal.xml"]),
        DemoStage("S7_execute_bug", "execute", "mock_pytest",
                  ["outputs/generated_tests/test_api_suite.py", "outputs/data/users_mock.json"],
                  ["outputs/junit_bug.xml"], mock_bug=True),
        DemoStage("S8_exec_report", "report", "exec_report",
                  ["outputs/junit_normal.xml", "outputs/junit_bug.xml"],
                  ["outputs/exec_report.md"]),
        DemoStage("S9_bug_analyze", "analysis", "cmd",
                  ["outputs/exec_report.md", "outputs/junit_bug.xml"],
                  ["outputs/bug_analysis.json"]),
    ]


# ═══════════════════════════════════════════════════════════════
# 7. 实验入口
# ═══════════════════════════════════════════════════════════════

def _render(entries: list[V2Entry], warnings: list[str], title: str) -> None:
    print(f"=== {title} ===")
    if warnings:
        for w in warnings:
            print(f"  ⚠️ {w}")
    print(f"{'stage_id':<26}{'origin':<7}{'kind':<12}{'gate':<7}{'mock_bug':<9}semantics")
    for e in entries:
        sm = (e.semantics[:38] + "…") if len(e.semantics) > 38 else e.semantics
        print(f"{e.stage_id:<26}{e.origin:<7}{e.kind:<12}{e.gate:<7}{str(e.mock_bug):<9}{sm}")
    print(f"  （共 {len(entries)} 段；分级闸门 human={sum(1 for e in entries if e.gate == 'human')}  "
          f"machine={sum(1 for e in entries if e.gate == 'machine')}）")
    chain_errs = validate_chain(entries)
    if chain_errs:
        print("  ❌ 产物链校验失败：")
        for err in chain_errs:
            print(f"    - {err}")
    else:
        print("  ✅ 产物链闭包完整：每个阶段的输入都能被上游产出或 docs/ 外部资产满足")
    print()


def exp1_demo() -> None:
    """内置 demo：v1 → v2（全量 include）→ 标注/策略/链校验观察。"""
    entries, warnings = build_v2(demo_v1())
    _render(entries, warnings, "demo：蓝图 v2（v1 9 段 + 注入 5 段 = 14 段）")
    print("教学观察：")
    print("  ① v1 全部原样搬入（stage_id/kind/inputs/outputs 不变）——插段只是「改蓝图数据」")
    print("  ② S4.5 锚 S4 后；S10-S13 锚 S9 后；顺序由 _INJECT_ORDER 保证")
    print("  ③ S7_execute_bug 被补语义标注（origin=v1 但 semantics 变了）——S7 语义重定位零执行成本")
    print("  ④ S12_defect_verify runner=mock_pytest、mock_bug=False = 复用 S6/S7 双回路验证修复")


def _load_real_blueprint() -> list[object] | None:
    """尝试 import day34_flow_map.BLUEPRINT（零 API；失败返回 None 不报错）。"""
    try:
        mod = importlib.import_module("day34_flow_map")
    except Exception:
        return None
    blp = getattr(mod, "BLUEPRINT", None)
    if isinstance(blp, list):
        return blp
    return None


def exp2_attach_real() -> None:
    """真实 day34 BLUEPRINT attach：把 pydantic StageSpec 当 StageLike 用（鸭子类型红利）。"""
    blp = _load_real_blueprint()
    if blp is None:
        print("未找到 day34_flow_map.BLUEPRINT（当前目录无 day34 蓝图）→ 用 exp1_demo 或"
              "在 ai_test_agent/src/agent/ 下运行本命令")
        return
    typed: list[StageLike] = []
    for spec in blp:
        sid: str = str(getattr(spec, "stage_id", ""))
        kind: str = str(getattr(spec, "kind", ""))
        runner: str = str(getattr(spec, "runner", "cmd"))
        inputs: list[str] = list(getattr(spec, "inputs", []) or [])
        outputs: list[str] = list(getattr(spec, "outputs", []) or [])
        mock_bug: bool = bool(getattr(spec, "mock_bug", False))
        typed.append(
            DemoStage(sid, kind, runner, [str(i) for i in inputs], [str(o) for o in outputs], mock_bug)
        )
    entries, warnings = build_v2(typed)
    _render(entries, warnings, "真实 day34 BLUEPRINT → 蓝图 v2（v1 原样 + v2 注入，零执行器改动）")
    print("说明：真实蓝图 v1 阶段的 inputs/outputs 是 day34 实际产物名，v2 注入阶段的产物")
    print("桥接 token 会展开为锚点阶段真实 outputs —— 链校验结果反映 day34 蓝图本身的真实闭合度")


def main() -> None:
    """完成态：默认 demo；--real 尝试 attach day34 真实蓝图。"""
    import argparse

    parser = argparse.ArgumentParser(description="Day36 练习3：蓝图 v2 扩展原型")
    parser.add_argument("--real", action="store_true", help="attach day34_flow_map.BLUEPRINT 真实蓝图")
    args = parser.parse_args()
    if args.real:
        exp2_attach_real()
        return
    exp1_demo()
    print("=" * 72)
    print("💡 要点回顾：")
    print("   黑盒红利 = 蓝图是数据：v2 增补（插段/打标注/桥接产物）全部发生在数据层，执行器零改动")
    print("   分级闸门：非确定性产物人审（analysis/review…→ human），确定性产物机检")
    print("           （execute/report/regression…→ machine），不是到处人审")
    print("   缺陷生命周期：S10 triage → S11 fix → S12 verify（双回路验证修复）→ 收口 Go/No-Go")


if __name__ == "__main__":
    main()
