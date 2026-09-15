"""Day 35 练习 2/3：场景参数化 —— BLUEPRINT 从"写死 login"变成"场景即参数"的工厂。

背景（为什么做——2026-09-07 用户追问）：
  Day 34 的 BLUEPRINT 每段 inputs/outputs/cmd 写死 login（教学取舍：先证明流程跑通）。
  真正拦"多场景并行"的不是输入写死，而是【蓝图没有场景维度】——今天先把蓝图工厂化：
    ScenarioConfig（场景是什么）+ build_blueprint(sc)（蓝图怎么长）→ 任意场景一张图。
  BLUEPRINT = build_blueprint(LOGIN_SCENARIO) 的"契约等价"版本（练习 2 用断言证明），
  执行器/实现层零改动（黑盒红利：执行器只认 输入文件→输出文件，不认识"login"）。

分界线（哪些参数化、哪些不）：
  ✔ 参数化：文件路径 / 产物名前缀 / mock 端口（蓝图层的事）
  ✘ 不参数化：mock 行为与用例语义 = 场景资产 + 各专项 Chain（day29-33 的事，蓝图黑盒不管）
  产物目录的"场景维度"（outputs/<scenario>/…）是真跑多场景时的下一步，见文档延伸区。

练习 2（第一部分，本文件到 exp1）：
  ScenarioConfig + 双场景常量 + build_blueprint 工厂 + 按蓝图派生盘点的 scan_blueprint
  教学点 A：契约 = stage_id/kind/runner/inputs/outputs/mock_bug——title/note/cmd 是提示文本不进断言
  教学点 B：盘点用的"流内产物豁免集"必须从【传入的蓝图】派生，不能是全局集（Day 34 全局 PRODUCED_OUTPUTS 的工厂化）
练习 3（第二部分，追加在文件末尾）：
  exp2 双场景盘点矩阵 + exp3 工厂蓝图过执行器（S4 确定性重生成，指纹不变）+ exp4 缺口补齐计划

实验↔步骤↔运行命令 映射：
  exp1_login_parity()    步骤3  python -c "from day35_scenario import exp1_login_parity; exp1_login_parity()"
  exp2_scan_matrix()     步骤4  python -c "from day35_scenario import exp2_scan_matrix; exp2_scan_matrix()"
  exp3_factory_rerun()   步骤4  python -c "from day35_scenario import exp3_factory_rerun; exp3_factory_rerun()"
  exp4_gap_report()      步骤4  python -c "from day35_scenario import exp4_gap_report; exp4_gap_report()"
  main()                 步骤4  python day35_scenario.py（完成态：exp1→exp2→exp3→exp4）
"""

from __future__ import annotations

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from pydantic import BaseModel, Field

from day34_flow_map import (  # noqa: E402
    BLUEPRINT,
    StageKind,
    StageSpec,
    ScanStatus,
    _abs,
    _exists_nonempty,
)
from day35_common import ROOT, output_dir, write_text  # noqa: E402  # 抽好的公共底座（练习 1 复用）


# ═══════════════════════════════════════════════════════
# 场景契约（练习 2：场景 = 一组资产路径 + 一个 mock 端口）
# ═══════════════════════════════════════════════════════
class ScenarioConfig(BaseModel):
    """一个被测功能的完整资产描述（蓝图的"入参"）。

    requirement_doc / api_doc / schema_docs / bug_doc 都是【相对项目根】路径；
    mock_port 决定 S6/S7 mock_pytest runner 的端口（分界线：mock 行为是场景资产，端口是蓝图层）。
    bug_probe 是执行档位（Day 37 新增）：是否跑 S7「埋 Bug 变异自验证」对照回路。
      默认 True = 向后兼容（与 Day 35 蓝图逐字一致，契约断言不破）；
      False = 摘掉 S7，且 S8 报告输入自适应（不再喂 junit_bug.xml，防悬空断链）。
    """

    name: str                                    # 场景名（同时是产物名前缀：requirement_{name}_analysis.*）
    title: str                                   # 人类可读标题（流程图展示用）
    requirement_doc: str
    api_doc: str
    schema_docs: list[str] = Field(default_factory=list)
    bug_doc: str
    mock_port: int
    bug_probe: bool = True                       # 执行档位：S7 变异自验证（默认开）


LOGIN_SCENARIO = ScenarioConfig(
    name="login",
    title="用户登录",
    requirement_doc="docs/requirements/login_requirement.md",
    api_doc="docs/apis/login_api.md",
    schema_docs=["docs/schemas/users.md", "docs/schemas/orders.json"],
    bug_doc="docs/bugs/login_bugs.md",
    mock_port=8766,
)

# 第二场景：register 已有需求文档(.txt) + 接口文档(.json) 资产；缺 schemas/bugs 资产
# → 练习 2/3 正好演示：同一工厂产出的 register 蓝图，盘点时精准报出 missing_input 缺口。
REGISTER_SCENARIO = ScenarioConfig(
    name="register",
    title="用户注册",
    requirement_doc="docs/requirements/register_requirement.txt",
    api_doc="docs/apis/register_api.json",
    schema_docs=["docs/schemas/register.json"],   # 缺 → S5 missing_input（教学点）
    bug_doc="docs/bugs/register_bugs.md",         # 缺 → S9 missing_input（教学点）
    mock_port=8767,
)


# ═══════════════════════════════════════════════════════
# 蓝图工厂（练习 2：把 Day 34 写死的 9 段 StageSpec 模板化成 f-string）
# ═══════════════════════════════════════════════════════
def build_blueprint(sc: ScenarioConfig) -> list[StageSpec]:
    """按场景生成 9 段蓝图（与 Day 34 BLUEPRINT 契约等价的模板实例）。

    ⚠️ 为什么用结构化构造而不是字符串模板：StageSpec 字段有 Literal 类型约束，
       pyright 在构建期就能抓住 kind/runner 拼错；字符串模板要到运行期才炸。
    """
    plan_json: str = f"outputs/api_test_plan_{sc.name}.json"
    plan_md: str = f"outputs/api_test_plan_{sc.name}.md"
    req_json: str = f"outputs/requirement_{sc.name}_analysis.json"
    req_md: str = f"outputs/requirement_{sc.name}_analysis.md"
    bug_json: str = f"outputs/bug_{sc.name}_analysis.json"
    bug_md: str = f"outputs/bug_{sc.name}_analysis.md"
    bug_batch: str = f"outputs/bug_{sc.name}_batch_report.md"
    conftest: str = "outputs/generated_tests/conftest.py"
    suite: str = "outputs/generated_tests/test_api_suite.py"
    junit_n: str = "outputs/flow/junit_normal.xml"
    junit_b: str = "outputs/flow/junit_bug.xml"
    report_n: str = "outputs/flow/exec_report_normal.md"
    report_b: str = "outputs/flow/exec_report_bug.md"

    stages: list[StageSpec] = [
        StageSpec(
            stage_id="S1_requirement_cases",
            title="需求解析 → 分级用例",
            source="day29",
            kind="llm",
            inputs=[sc.requirement_doc],
            outputs=[req_json, req_md],
            cmd=f"from day29_requirement_analysis import exp2_analyze_file; "
                f"exp2_analyze_file('../../{sc.requirement_doc}', '{sc.name}')",
            note=f"真 API：分析 Chain 生成分级用例 → 质检 → 落盘（name='{sc.name}'）",
        ),
        StageSpec(
            stage_id="S2_case_review_gate",
            title="用例评审闸门（两段式评审门）",
            source="day35",
            kind="manual",
            inputs=[req_json],
            note="day35_review_gate：exp1 生成待评审种子 → 人工审阅 → exp2 盖章(reviewed) → "
                 "upsert 硬门禁（reviewed=False 拒绝入库）；manual 永远等人",
        ),
        StageSpec(
            stage_id="S3_api_plan",
            title="接口文档 → 接口测试计划",
            source="day30",
            kind="llm",
            inputs=[sc.api_doc],
            outputs=[plan_json, plan_md],
            cmd=f"from day30_api_schema import exp2_analyze_file; "
                f"exp2_analyze_file('../../{sc.api_doc}', '{sc.name}')",
            note=f"真 API：文档 → ApiDoc（.md 走模型 / .json 走代码直读）→ 三件套计划 → 落盘",
        ),
        StageSpec(
            stage_id="S4_test_codegen",
            title="计划 → pytest 代码（确定性渲染）",
            source="day30",
            kind="code",
            runner="cmd",
            inputs=[plan_json],
            outputs=[conftest, suite],
            cmd=f"from day30_pytest_generator import generate_api_tests_from_plan; "
                f"print(generate_api_tests_from_plan('../../{plan_json}', '../../outputs/generated_tests'))",
            note="确定性段：同输入同输出（练习 3 --force 重跑验证指纹不变）",
        ),
        StageSpec(
            stage_id="S5_test_data",
            title="字段规则 → 测试数据",
            source="day32",
            kind="llm",
            inputs=sc.schema_docs,
            outputs=["outputs/data_gen/users_normal.json", "outputs/data_gen/orders_normal.json"],
            cmd="from day32_run_pipeline import exp6_pipeline; exp6_pipeline()",
            note="双输入分派：.md 走模型解析、.json 走代码直读（确定性段内置）",
        ),
        StageSpec(
            stage_id="S6_execute_normal",
            title="执行：mock 正常版 → JUnit XML",
            source="day30/综合",
            kind="code",
            runner="mock_pytest",
            mock_bug=False,
            inputs=[suite],
            outputs=[junit_n],
            note=f"执行器内置：start_mock({sc.mock_port}, False) → pytest 生成套件 --junitxml → stop",
        ),
        StageSpec(
            stage_id="S7_execute_bug",
            title="执行：mock 埋 Bug 版 → JUnit XML（对照回路）",
            source="day30/综合",
            kind="code",
            runner="mock_pytest",
            mock_bug=True,
            inputs=[suite],
            outputs=[junit_b],
            note=f"同一套用例只切 bug_mode=True → 抓「埋 Bug」缺陷（错误凭据 500 / 越权 200）",
        ),
        StageSpec(
            stage_id="S8_exec_report",
            title="JUnit → 执行报告（缺陷反查注册表）",
            source="day33/综合",
            kind="code",
            runner="exec_report",
            inputs=[junit_n, junit_b, "docs/cases/api_registry.json"],
            outputs=[report_n, report_b],
            note="统计归代码（day33 summarize/find_defects）；node id → 注册表 TC 反查",
        ),
        StageSpec(
            stage_id="S9_bug_analyze",
            title="Bug 报告 → 结构化分析（批量+聚合）",
            source="day31",
            kind="llm",
            inputs=[sc.bug_doc],
            outputs=[bug_json, bug_md, bug_batch],
            cmd=f"from day31_bug_analyzer import exp4_batch_pipeline; "
                f"exp4_batch_pipeline('../../{sc.bug_doc}', '{sc.name}', False)",
            note="真 API：分割 → 逐条分析 → 聚合统计 → 报表落盘（入库前先过 day35 评审门）",
        ),
    ]

    return _apply_bug_probe(stages, sc.bug_probe)

# ═══════════════════════════════════════════════════════
# 按蓝图派生的盘点（练习 2：盘点逻辑工厂化 —— 豁免集从传入蓝图派生）
# ═══════════════════════════════════════════════════════
def scan_blueprint(
    blueprint: list[StageSpec],
) -> list[tuple[StageSpec, ScanStatus, str]]:
    """盘点任意蓝图（不依赖全局 BLUEPRINT/PRODUCED_OUTPUTS）。

    教学点：Day 34 的 scan_stage 读全局 PRODUCED_OUTPUTS——蓝图一旦参数化，
    "哪些文件是流内依赖（上游产出，不阻塞盘点）"必须从【当前蓝图】派生。
    """
    produced: frozenset[str] = frozenset(p for spec in blueprint for p in spec.outputs)

    def status_of(spec: StageSpec) -> tuple[ScanStatus, str]:
        if spec.kind == "manual":
            return "manual_pending", spec.note
        if all(_exists_nonempty(p) for p in spec.outputs):
            return "reused", "产物在位且非空，可回放（指纹由执行器算）"
        missing: list[str] = [
            p for p in spec.inputs
            if p not in produced and not _exists_nonempty(p)
        ]
        if missing:
            return "missing_input", "外部输入缺失：" + missing[0]
        if spec.kind == "llm":
            return "needs_api", "输入齐、产物缺 → --with-llm 补跑（真 API）"
        return "run_ready", "code 段：执行器现场自动跑"

    rows: list[tuple[StageSpec, ScanStatus, str]] = []
    for spec in blueprint:
        status, reason = status_of(spec)
        rows.append((spec, status, reason))
    return rows


def select_stages(blueprint: list[StageSpec], wanted: set[str]) -> list[StageSpec]:
    """按阶段 id 取子集，并自动补齐依赖闭包（Day 38：CLI --stage / 未来 UI 阶段多选）。

    为什么需要：裸过滤 `[s for s in bp if s.stage_id in wanted]` 只保证"想要的段在"，
    不保证它们的输入有产出者——子集里缺上游 → 执行期 run_failed（假失败）。
    算法：从 wanted 出发，沿 outputs→inputs 反向上溯 producer 直到不动点；
          最后按【原蓝图顺序】取子序列（原序 = 拓扑序 → 子序列天然拓扑正确）。
    返回：新列表（原顺序）；wanted 里不存在的 stage_id 静默忽略（是否报错由入口层决定）。
    """
    by_id: dict[str, StageSpec] = {spec.stage_id: spec for spec in blueprint}
    by_output: dict[str, StageSpec] = {out: spec for spec in blueprint for out in spec.outputs}
    keep: set[str] = set()
    stack: list[str] = [sid for sid in wanted if sid in by_id]
    while stack:
        sid: str = stack.pop()
        if sid in keep:
            continue
        keep.add(sid)
        for inp in by_id[sid].inputs:
            producer: StageSpec | None = by_output.get(inp)
            if producer is not None:
                stack.append(producer.stage_id)
    return [spec for spec in blueprint if spec.stage_id in keep]

def find_blueprint_contract_violations(blueprint: list[StageSpec]) -> list[str]:
    """检查蓝图的「反向索引」契约，返回违规描述列表（空 = 合规）。

    为什么需要（Day 39）：select_stages 的 `by_output` 用输出路径字符串**逐字相等**做键，
    两个隐含前提一旦破了**不报错、只静默出错**：
      ① 输出路径全局唯一 —— 两个 stage 声明同一输出文件时，字典推导**后者覆盖前者**，
         于是"某段的上游生产者"被认错/丢失 → 闭包少补上游 → 执行期才 run_failed；
      ② 路径写法规范 —— 索引靠逐字匹配，`./outputs/x` 与 `outputs/x` 是两个键，
         写法不规范就会被误判为"外部输入" → 同样静默不补齐。

    本函数把它们从"隐含约定"提升为**可断言契约**（纯函数：不改入参、不读文件系统、
    不改 build_blueprint 行为）。消费端 = tests/test_day39_blueprint.py 的契约测试。
    """
    violations: list[str] = []
    owners: dict[str, str] = {}
    for spec in blueprint:
        if spec.kind != "manual" and not spec.outputs:
            violations.append(f"{spec.stage_id}：非 manual 段却无 outputs")
        for out in spec.outputs:
            owner: str | None = owners.get(out)
            if owner is not None and owner != spec.stage_id:
                violations.append(f"输出重复：{out!r} 同时由 {owner} 与 {spec.stage_id} 声明")
            else:
                owners[out] = spec.stage_id
        for path in (*spec.inputs, *spec.outputs):
            if path.startswith("./") or path.startswith(".\\") or "\\" in path:
                violations.append(f"{spec.stage_id}：路径未规范化 {path!r}（禁 ./ 前缀与反斜杠）")
    return violations

def _apply_bug_probe(stages: list[StageSpec], bug_probe: bool) -> list[StageSpec]:
    """执行档位过滤（Day 37，Day 39 修补）：bug_probe=False → 摘 S7 + S8 输入/输出双自适应。

    语义（与 day37_bug_probe.apply_bug_probe 同构，此处直接操作真实 StageSpec）：
      - S6 主干永远在（S7 依赖 S6 单向，不是成组开关）；
      - S8 报告段 inputs 去掉 junit_bug.xml（不再等一个不会产出的文件）；
      - S8 报告段 outputs 同步去掉 exec_report_bug.md（Day 39 补：原版只改 inputs，
        outputs 仍要两份 → 与 _run_exec_report 的硬编码叠加后，干净环境 S8 run_failed）；
      - 默认 True 时原样返回 → Day35 契约等价断言 exp1_login_parity 不破。
    ⚠️ 就地修改：本函数直接改传入 spec 的字段（依赖 build_blueprint 每次新建对象）。
       禁止把 build_blueprint 改成 `return list(BLUEPRINT)`——浅拷贝共享内层对象，
       一次 --no-bug-probe 就会永久污染模块级 BLUEPRINT。
    """
    if bug_probe:
        return stages
    kept: list[StageSpec] = [s for s in stages if s.stage_id != "S7_execute_bug"]
    for spec in kept:
        if spec.stage_id == "S8_exec_report":
            spec.inputs = [p for p in spec.inputs if not p.endswith("junit_bug.xml")]
            spec.outputs = [p for p in spec.outputs if not p.endswith("exec_report_bug.md")]
    return kept


# ═══════════════════════════════════════════════════════
# 实验（练习 2：契约等价回归 —— 工厂产物 vs Day 34 蓝图）
# ═══════════════════════════════════════════════════════
def exp1_login_parity() -> int:
    """契约等价回归：build_blueprint(LOGIN_SCENARIO) 与 Day 34 BLUEPRINT 必须契约全等。

    比较字段（黑盒契约）：stage_id / kind / runner / inputs / outputs / mock_bug
    不比较字段（提示/实现文本）：title / note / cmd（cmd 由场景名模板化生成，执行语义等价）
    额外验证：两套盘点（day34 全局式 vs day35 蓝图派生式）状态一致。
    返回不一致计数（0 = 全等）。
    """
    built: list[StageSpec] = build_blueprint(LOGIN_SCENARIO)
    diffs: int = 0
    if len(built) != len(BLUEPRINT):
        print(f"  ❌ 蓝图段数不一致: {len(built)} != {len(BLUEPRINT)}")
        return len(built) - len(BLUEPRINT)

    fields: tuple[str, ...] = ("stage_id", "kind", "runner", "inputs", "outputs", "mock_bug")
    print(f"  契约字段对比（{len(fields)} 项 × {len(built)} 段）：")
    for idx, (a, b) in enumerate(zip(built, BLUEPRINT, strict=True)):
        bad: list[str] = []
        for f in fields:
            if getattr(a, f) != getattr(b, f):
                bad.append(f"{f}: {getattr(a, f)!r} != {getattr(b, f)!r}")
        if bad:
            diffs += 1
            print(f"    [{idx}] {a.stage_id} ❌ " + " | ".join(bad))
    if diffs == 0:
        print("  ✅ 契约全等：工厂产物与 Day 34 BLUEPRINT 黑盒契约逐项一致")

    # 盘点状态一致性（同一文件系统，两套盘点逻辑必须给同一答案）
    ours: list[tuple[str, str]] = [(s.stage_id, st) for s, st, _ in scan_blueprint(built)]
    theirs: list[tuple[str, str]] = [(s.stage_id, st) for s, st, _ in scan_assets_legacy()]
    if ours != theirs:
        diffs += 1
        for (i1, s1), (i2, s2) in zip(ours, theirs, strict=True):
            if (i1, s1) != (i2, s2):
                print(f"  ❌ 盘点不一致: {i1} {s1} (day35) vs {s2} (day34 全局式)")
    else:
        print("  ✅ 盘点一致：蓝图派生豁免集 == 全局豁免集（login 场景下两套盘点同答案）")
    return diffs


def scan_assets_legacy() -> list[tuple[StageSpec, ScanStatus, str]]:
    """Day 34 全局式盘点（对照用，内部委托 day34_flow_map）。"""
    from day34_flow_map import scan_assets  # noqa: PLC0415  # 延迟 import 保持对照清晰

    return scan_assets()


# ═══════════════════════════════════════════════════════
# 第二部分（练习 3）：双场景矩阵 + 执行器回归 + 缺口报告
# ═══════════════════════════════════════════════════════
def exp2_scan_matrix() -> dict[str, list[tuple[str, str]]]:
    """双场景盘点矩阵：同一工厂 → login 与 register 两张蓝图 → 状态一览。

    返回 {场景名: [(stage_id, status), ...]}；同时打印缺口清单（needs_api=补跑，missing_input=补资产）。
    教学点：register 缺 schemas/register.json 与 bugs/register_bugs.md——不是蓝图写错，
    是资产没到位；盘点把"哪里缺"精确到文件名（缺口清单 = 任务清单）。
    """
    matrix: dict[str, list[tuple[str, str]]] = {}
    for sc in (LOGIN_SCENARIO, REGISTER_SCENARIO):
        rows: list[tuple[StageSpec, ScanStatus, str]] = scan_blueprint(build_blueprint(sc))
        matrix[sc.name] = [(s.stage_id, st) for s, st, _ in rows]
        print(f"── 场景 [{sc.name}] {sc.title}（{sc.requirement_doc}）──")
        for spec, status, reason in rows:
            print(f"  [{status:<14}] {spec.stage_id:<22} {reason}")
        counts: dict[str, int] = {}
        for _, status in matrix[sc.name]:
            counts[status] = counts.get(status, 0) + 1
        print(f"  汇总: {counts}")
    return matrix


def exp3_factory_rerun() -> bool:
    """工厂蓝图过执行器：把 LOGIN 蓝图塞进 Day 34 执行器机制，--force 重生成 S4 两次。

    断言：两次重生成指纹一致（确定性不漂移），且与既有产物指纹一致（与 Day 34 同源）。
    教学点：执行器不认识"login"——它只认契约；工厂蓝图 = 合法输入（黑盒红利）。
    """
    from day34_orchestrator import _fingerprints_of, _run_stage  # noqa: E402  # 执行器机制（练习 3）

    spec: StageSpec = next(s for s in build_blueprint(LOGIN_SCENARIO) if s.stage_id == "S4_test_codegen")
    before: list[str] = _fingerprints_of(spec)
    print(f"  ▶ 既有 S4 产物指纹: {before}")
    _run_stage(spec, with_llm=False, force=True)
    fp1: list[str] = _fingerprints_of(spec)
    _run_stage(spec, with_llm=False, force=True)
    fp2: list[str] = _fingerprints_of(spec)
    stable: bool = fp1 == fp2 and fp1 == before
    print(f"  重生成两次指纹一致且与既有一致: {stable}")
    for entry in fp1:
        print(f"    {entry}")
    if not stable:
        print("  ❌ 指纹漂移——工厂蓝图执行结果与 Day 34 不一致，先排查模板化引入的差异")
    else:
        print("  ✅ 工厂蓝图确定性成立：同输入同输出，且与 Day 34 蓝图产物同指纹（契约等价的执行证据）")
    return stable


def exp4_gap_report() -> str:
    """register 场景缺口报告：把盘点出的 needs_api/missing_input/manual_pending 落成补齐计划。

    产物：outputs/flow/register_fill_plan.md（缺口清单 = 任务清单，register 全跑通的前置作业）。
    返回 md 绝对路径。
    """
    rows: list[tuple[StageSpec, ScanStatus, str]] = scan_blueprint(build_blueprint(REGISTER_SCENARIO))
    lines: list[str] = [
        "# register 场景补齐计划（Day 35 exp4）",
        "",
        "由场景工厂盘点自动生成：同一 9 段蓝图，register 缺资产 → 状态见下。",
        "",
        "| 阶段 | 状态 | 需要补什么 |",
        "|------|------|-----------|",
    ]
    for spec, status, reason in rows:
        if status in ("needs_api", "missing_input", "manual_pending"):
            lines.append(f"| {spec.stage_id} | {status} | {reason} |")
    lines.extend([
        "",
        "## 补齐指引（对应文档步骤 4 延伸练习）",
        "- S1/S3：资产在位，跑 `python day34_orchestrator.py --with-llm` 由实现层补产物",
        "- S5：缺 docs/schemas/register.json —— 抄 register_api.json 字段规则生成（.json 走代码直读）",
        "- S9：缺 docs/bugs/register_bugs.md —— 按 login_bugs.md 格式补一份（至少 2 条 ## BUG-xx）",
        "- S4/S6/S7/S8：code 段资产到齐后由执行器自动跑（mock 端口已按场景隔离为 8767）",
    ])
    out_dir: str = output_dir("flow")
    md_path: str = os.path.join(out_dir, "register_fill_plan.md")
    write_text(md_path, "\n".join(lines))
    print(f"  ✅ register 补齐计划落盘: {md_path}")
    return md_path


if __name__ == "__main__":
    """完成态：exp1（契约回归）→ exp2（矩阵）→ exp3（执行器确定性）→ exp4（缺口报告）。"""
    diffs = exp1_login_parity()
    if diffs:
        raise SystemExit(f"❌ 契约等价回归未通过（{diffs} 处），先修再继续")
    matrix = exp2_scan_matrix()
    ok = exp3_factory_rerun()
    if not ok:
        raise SystemExit("❌ 确定性回归未通过，先排查")
    md_path = exp4_gap_report()
    print("=" * 60)
    print("💡 要点回顾：")
    print("   场景即参数：BLUEPRINT = build_blueprint(LOGIN_SCENARIO) 的契约等价——换场景不重写蓝图")
    print("   盘点工厂化：流内豁免集从传入蓝图派生，不再依赖全局常量（全局只适合单蓝图时代）")
    print(f"   缺口清单 = 任务清单：register 差什么，看 {md_path}")
    print("   下一步（Day 36 或延伸）：产物目录加场景维度 outputs/<scenario>/…，多场景真并行")