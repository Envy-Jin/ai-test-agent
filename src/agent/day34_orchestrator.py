"""Day 34 练习 2/3：编排器 —— 蓝图执行 + 三态记录 + 断点续跑 + 指纹审计。

设计（步骤 1 决策落地）：
  A. 三层分离：蓝图（day34_flow_map.BLUEPRINT）/ 实现（day29-33 模块）/
     执行器（本脚本，只调度不实现业务）
  C. 三态执行：reused（产物在 → 断点续跑，指纹入库）/ run（code 自动、
     llm 需 --with-llm）/ manual_pending（评审门占位）
  D. 审计：每段状态/耗时/产物 sha256 指纹 → flow_report.json + .md
  E. 执行回路：mock_pytest 处理器（正常版 vs 埋 Bug 版双回路，同一套用例）
  F. 报告回路：exec_report 处理器（JUnit → 统计/缺陷 → 轻量执行报告；
     完整"回归报告"模板在 day33，不复制）

实验（cd src/agent）：
  练习 2（第一部分）：
    python -c "from day34_orchestrator import exp2_replay_and_exec; exp2_replay_and_exec()"
      # 零 API / 零外网：回放 reused 段 + 现场跑 S6/S7(mock+pytest) + S8(报告)
  练习 3（第二部分，追加在文件末尾）：
    python -c "from day34_orchestrator import exp3_regen_fingerprint_stable; exp3_regen_fingerprint_stable()"
      # 零 API：--force 重跑 S4 两次，断言产物指纹不变（确定性可复现）
    python day34_orchestrator.py [--with-llm] [--force] [--fail-fast]
      # main 完成态：默认 = exp2；--with-llm 补跑 llm 缺口段（真 API）
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()  # ⚠️ 必须在 langchain import 之前（Day 25 口诀）
# 假 key 兜底：仅构造期校验、零 API（冒烟规范）；真实环境 .env 会先被 load_dotenv 读到
os.environ.setdefault("GEMINI_API_KEY", "smoke-fake-key")

# import 提前放（2026-09-02 规范）：练习 3 才用到的也在这里
from day30_mock_api import start_mock, stop_mock  # noqa: E402
from day33_change_schema import CaseEntry, load_case_registry  # noqa: E402
from day33_report_pipeline import (  # noqa: E402
    find_defects,
    lookup_case,
    parse_junit_xml,
    summarize,
)
from day34_flow_map import (  # noqa: E402
    BLUEPRINT,
    FLOW_DIR,
    StageSpec,
    _abs,
    _exists_nonempty,
)

# ── 路径（钉 __file__，与 day34_flow_map 同构）──
_AGENT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_ROOT: str = os.path.dirname(os.path.dirname(_AGENT_DIR))
REGISTRY_PATH: str = os.path.join(_ROOT, "docs", "cases", "api_registry.json")

RUN_TIMEOUT: int = 300  # 子进程/测试超时（秒）


# ═══════════════════════════════════════════════════════
# Schema：执行记录（练习 2 —— flow_report 的每一行）
# ═══════════════════════════════════════════════════════
ExecStatus = Literal[
    "reused", "run_ok", "run_failed", "skipped_needs_api", "manual_pending",
]


class StageRecord(BaseModel):
    """一个 stage 本次执行的审计记录。"""

    stage_id: str
    status: ExecStatus
    duration_s: float = 0.0
    fingerprints: list[str] = Field(default_factory=list)  # "path_rel#sha12"
    detail: str = ""


class FlowReport(BaseModel):
    """一次全流程执行的完整审计（落盘 outputs/flow/flow_report.json）。"""

    started_at: str
    note: str
    stages: list[StageRecord]


# ═══════════════════════════════════════════════════════
# 工具（练习 2：指纹 / 子进程 / 状态判断）
# ═══════════════════════════════════════════════════════
def _sha12(path_abs: str) -> str:
    """文件 sha256 前缀 12 位（产物身份证）。
    ⚠️ 二进制读（rb）：文本模式 read() 返回 str，hash.update 只收 bytes。
    """
    digest = hashlib.sha256()
    with open(path_abs, "rb") as f:
        while True:
            chunk: bytes = f.read(8192)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()[:12]


def _fingerprints_of(spec: StageSpec) -> list[str]:
    """输出产物指纹列表（只算存在且非空的文件）。"""
    return [
        f"{p}#{_sha12(_abs(p))}"
        for p in spec.outputs
        if _exists_nonempty(p)
    ]

# ── Day 41：把"路径从哪来"抽成纯函数（可测性 = 设计的产物）──
def pytest_suite_target(spec: StageSpec) -> str:
    """执行段要跑的 **套件文件**（不是目录）绝对路径。

    ⚠️ Day 41 修正：原来把 `os.path.dirname(suite)` 整个目录喂给 pytest。
       产物加场景命名空间后 `outputs/generated_tests/` 下会同时存在 login 的
       套件和 `register/` 子目录 → 跑 login 的 S6 会**连带收集 register 的用例**
       （并发跑两个场景时更糟）。改成点名文件：pytest 仍会加载同目录的
       conftest.py（fixture 不丢），但不再越界收集。
    """
    return _abs(spec.inputs[0])


def find_junit_input(spec: StageSpec, keyword: str) -> str | None:
    """按 keyword（normal/bug）从 **spec.inputs** 里找出对应的 junit 相对路径。

    ⚠️ Day 41 去掉的硬编码：`_run_exec_report` 原来写死
       `outputs/flow/junit_{keyword}.xml` —— Day 39 已经把 outputs 改成按
       `spec.outputs` 驱动了，inputs 侧的路径却还是死的，所以产物一进
       `outputs/flow/register/` 就找不到 junit（`--no-bug-probe` 那次踩的是同一个坑）。
       现在：声明里有什么就用什么，路径永生跟随蓝图。
    """
    suffix: str = f"junit_{keyword}.xml"
    for path in spec.inputs:
        if path.endswith(suffix):
            return path
    return None


def _llm_cache_prefix() -> str:
    """llm 段的缓存注入前缀（延迟 import：执行器冷启动不必拖 langchain）。"""
    from day41_cache_wiring import cache_prefix  # noqa: PLC0415

    return cache_prefix()

def _run_cmd(cmd_body: str, *, use_cache: bool) -> int:
    """执行蓝图 cmd（python -c 语句体）。

    Day 41：`use_cache=True` 时在语句体前面拼一段"装全局缓存"的前缀 ——
    ⚠️ 必须注入**子进程**：执行器是 `subprocess.run([sys.executable, "-c", ...])`，
    父进程 set 过的全局变量子进程看不见（进程级状态不跨 exec）。
    """
    body: str = f"{_llm_cache_prefix()}{cmd_body}" if use_cache else cmd_body
    print(f"  ▶ python -c {body[:70]}...")
    proc: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, "-c", body],
        cwd=_AGENT_DIR,               # 子进程在 src/agent 跑：dayXX 模块可 import
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=RUN_TIMEOUT,
    )
    tail: list[str] = (proc.stdout or "").strip().splitlines()[-5:]
    for line in tail:
        print(f"    | {line}")
    if proc.stderr:
        for line in (proc.stderr or "").strip().splitlines()[-3:]:
            print(f"    ! {line}")
    return int(proc.returncode)


def _run_mock_pytest(spec: StageSpec) -> tuple[bool, str]:
    """内置处理器：mock 靶场 + pytest 生成套件 → JUnit XML（执行回路）。

    pytest 的退出码 1 = 有用例失败——对执行段来说这是"发现了缺陷"的合法
    结果，不算 stage 失败（stage 失败 = 起不来/超时/收集错误）。
    """
    junit_rel: str = spec.outputs[0]
    junit_abs: str = _abs(junit_rel)
    os.makedirs(os.path.dirname(junit_abs), exist_ok=True)
    suite_file: str = pytest_suite_target(spec)   # Day 41：点名文件，不喂目录
    argv: list[str] = [
        sys.executable, "-m", "pytest", suite_file,
        "-q", "--no-header", "--junitxml", junit_abs,
    ]
    mode: str = "埋 Bug 版(bug_mode=True)" if spec.mock_bug else "正常版(bug_mode=False)"
    print(f"  ▶ mock {spec.mock_port}/{spec.mock_scenario} {mode} → pytest "
          f"{os.path.basename(suite_file)} → {junit_rel}")
    start_mock(spec.mock_port, bug_mode=spec.mock_bug, scenario=spec.mock_scenario)
    try:
        proc: subprocess.CompletedProcess[str] = subprocess.run(
            argv, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=RUN_TIMEOUT,
        )
        tail: list[str] = (proc.stdout or "").strip().splitlines()[-4:]
        for line in tail:
            print(f"    | {line}")
    finally:
        stop_mock()
    code: int = int(proc.returncode)
    if code <= 1:
        # 0=全过；1=有用例失败（=抓到缺陷，正是执行段的目的）
        return True, f"pytest exit={code}，JUnit 已落盘 {junit_rel}"
    return False, f"pytest 执行异常 exit={code}（收集错误/崩溃/超时），见输出"


def render_exec_report(
    keyword: str,
    junit_text: str,
    registry: list[CaseEntry],
) -> str:
    """JUnit XML → 轻量执行报告 Markdown（统计/缺陷全归代码）。

    keyword ∈ {"normal", "bug"}：决定标题与结论措辞。
    完整"回归测试报告"模板在 day33（render_markdown_report），这里不复制。
    """
    label: str = "正常版（基线）" if keyword == "normal" else "埋 Bug 版（对照）"
    outcomes = parse_junit_xml(junit_text)
    stats = summarize(outcomes)
    defects = find_defects(outcomes)
    lines: list[str] = [
        f"# 全流程执行报告：{scenario_label_of(registry)} · {label}",
        "",
        f"**日期**: {datetime.now():%Y-%m-%d %H:%M}",
        f"**执行**: mock 靶场 + 生成套件（{len(outcomes)} 个 pytest node）",
        "",
        "## 执行摘要",
        f"- 用例总数: {stats.total}",
        f"- 通过: {stats.passed}",
        f"- 失败: {stats.failed}",
        f"- 跳过: {stats.skipped}",
        f"- 错误: {stats.errors}",
        f"- 通过率: {stats.pass_rate}%",
        "",
        "## 详细结果",
        "| 状态 | 用例 | 模块 | 耗时(s) | 说明 |",
        "|------|------|------|---------|------|",
    ]
    for o in outcomes:
        case = lookup_case(o.node_id, registry)
        module: str = case.module if case is not None else "?"
        note: str = (o.message[:80]).replace("|", "/") if o.message else ""
        lines.append(f"| {o.status} | {o.node_id.split('::')[-1]} | {module} | {o.duration:.3f} | {note} |")
    lines.append("")
    lines.append("## 失败用例（疑似缺陷）")
    if not defects:
        lines.append("- 无")
    for idx, d in enumerate(defects, start=1):
        case = lookup_case(d.node_id, registry)
        head: str = f"{case.case_id} {case.title}" if case is not None else d.node_id
        lines.append(f"{idx}. **{head}** —— {d.message[:120]}")
    lines.append("")
    lines.append("## 结论")
    if not defects:
        lines.append(f"全部通过（{stats.passed}/{stats.total}）：当前版本行为符合用例预期。")
    else:
        lines.append(
            f"检出 {len(defects)} 个失败用例（疑似缺陷），建议接入 Day 31 Bug 分析（蓝图 S9）"
            "做根因与测试加固建议；本报告为轻量执行汇总，完整回归报告模板见 day33。"
        )
    return "\n".join(lines)


def _run_exec_report(spec: StageSpec) -> tuple[bool, str]:
    """内置处理器：读 junit → 注册表 → 渲染执行报告（报告回路）。

    Day 39 修复：**按 spec.outputs 驱动**，不再硬编码 ("normal", "bug")。
    写死版本让 --no-bug-probe（摘掉 S7）只做了一半：
      · 干净环境 junit_bug.xml 不在 → open() 抛 FileNotFoundError → 整段 run_failed；
      · 有旧产物时 → 拿【陈旧】junit_bug 再渲染一份 bug 报告（产出与档位不符）。
    现在：outputs 里有几份就渲染几份；对应 junit 不在则跳过并打印原因。
    """
    registry_rel: str | None = next((p for p in spec.inputs if p.endswith(".json")), None)
    registry: list[CaseEntry] = load_case_registry(
        _abs(registry_rel) if registry_rel is not None else REGISTRY_PATH
    )
    rendered: list[str] = []
    skipped: list[str] = []
    for out_rel in spec.outputs:
        keyword: str = "normal" if "normal" in out_rel else "bug"
        junit_rel: str | None = find_junit_input(spec, keyword)   # Day 41：从 spec.inputs 派生
        if junit_rel is None:
            skipped.append(f"{out_rel}（蓝图 inputs 未声明 {keyword} 版 junit）")
            print(f"  ⏭ 跳过 {out_rel}：inputs 里没有 junit_{keyword}.xml")
            continue
        with open(junit_rel, "r", encoding="utf-8") as f:
            junit_text: str = f.read()
        md: str = render_exec_report(keyword, junit_text, registry)
        with open(_abs(out_rel), "w", encoding="utf-8") as f:
            f.write(md)
        rendered.append(out_rel)
        print(f"  ▶ {out_rel} 已渲染")
    if not rendered:
        return False, "没有可渲染的报告（对应 junit 均不存在）：" + "、".join(skipped)
    detail: str = f"{len(rendered)} 份执行报告已落盘"
    if skipped:
        detail += "；跳过：" + "、".join(skipped)
    return True, detail

def scenario_label_of(registry: list[CaseEntry]) -> str:
    """从用例注册表推场景名（报告标题用）。注册表是**按场景切**的
    （`docs/cases/api_registry.json` → login，`api_registry_register.json` → register），
    取第一条的 module 即场景名。

    ⚠️ Day 41 端到端实测踩到的坑：报告标题原来写死
       `# 全流程执行报告：login · …`。login 场景下它**恰好是对的**，所以任何单测
       都抓不到；只有真跑第二个场景才现形（register 的报告标题写着 login）。
       硬编码的"对"是运气，不是正确 —— 端到端测试的价值正在于此。
    """
    return registry[0].module if registry else "unknown"

# ═══════════════════════════════════════════════════════
# 执行器（练习 2：单段执行 + 全流程执行）
# ═══════════════════════════════════════════════════════
def _run_stage(
    spec: StageSpec,
    *,
    with_llm: bool,
    force: bool,
    use_cache: bool = True,
) -> StageRecord:
    """跑一个 stage：manual 占位 → 断点续跑 → llm 跳过/执行 → code 执行。"""
    print(f"── {spec.stage_id} {spec.title}（{spec.kind} / {spec.source}）")
    if spec.kind == "manual":
        return StageRecord(
            stage_id=spec.stage_id, status="manual_pending", detail=spec.note,
        )
    outputs_ready: bool = bool(spec.outputs) and all(_exists_nonempty(p) for p in spec.outputs)
    if outputs_ready and not force:
        return StageRecord(
            stage_id=spec.stage_id, status="reused",
            fingerprints=_fingerprints_of(spec),
            detail="产物在位且非空 → 断点续跑（--force 可强制重跑）",
        )
    if spec.kind == "llm" and not with_llm:
        return StageRecord(
            stage_id=spec.stage_id, status="skipped_needs_api",
            detail="模型段需要真实 API：python day34_orchestrator.py --with-llm 补跑",
        )
    t0: float = time.perf_counter()
    ok: bool = True
    detail: str = ""
    try:
        if spec.runner == "mock_pytest":
            ok, detail = _run_mock_pytest(spec)
        elif spec.runner == "exec_report":
            ok, detail = _run_exec_report(spec)
        elif spec.cmd:
            # 缓存只注入 **llm 段**（code 段不调模型，多一次 import 纯属浪费）
            ok = _run_cmd(spec.cmd, use_cache=use_cache and spec.kind == "llm") == 0
            detail = "cmd 子进程完成（exit=0）" if ok else "cmd 子进程非零退出"
        else:
            ok = False
            detail = "未配置执行方式：runner=cmd 但 cmd 为空"
    except Exception as exc:  # 失败隔离：内置处理器异常 → run_failed，不中断整链
        ok = False
        detail = f"执行异常: {exc}"
    duration_s: float = round(time.perf_counter() - t0, 2)
    if ok:
        return StageRecord(
            stage_id=spec.stage_id, status="run_ok", duration_s=duration_s,
            fingerprints=_fingerprints_of(spec), detail=detail,
        )
    return StageRecord(
        stage_id=spec.stage_id, status="run_failed",
        duration_s=duration_s, detail=detail,
    )


def run_flow(
    blueprint: list[StageSpec] | None = None,
    *,
    with_llm: bool = False,
    force: bool = False,
    fail_fast: bool = False,
    use_cache: bool = True,
) -> FlowReport:
    """
    按蓝图顺序执行全流程：一段失败不中断（失败隔离），--fail-fast 才中断。
    Day 41 新增 `use_cache`：llm 段是否注入全局缓存（默认开）。
    关它的场景：① 想量"冷启动"真实耗时；② 怀疑缓存串味时要一份干净基线。
    """
    records: list[StageRecord] = []
    plan: list[StageSpec] = BLUEPRINT if blueprint is None else blueprint
    for spec in plan:
        record = _run_stage(spec, with_llm=with_llm, force=force, use_cache=use_cache)
        records.append(record)
        if record.status == "run_failed" and fail_fast:
            print("  ⚠️ --fail-fast：遇到 run_failed 中断整链")
            break
    return FlowReport(
        started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        note=f"with_llm={with_llm} force={force} fail_fast={fail_fast} use_cache={use_cache}",
        stages=records,
    )


def _count_statuses(report: FlowReport) -> dict[str, int]:
    counts: dict[str, int] = {}
    for r in report.stages:
        counts[r.status] = counts.get(r.status, 0) + 1
    return counts


def render_flow_report_markdown(report: FlowReport) -> str:
    """flow_report → Markdown（每段一行：状态/耗时/指纹/说明）。"""
    lines: list[str] = [
        "# 全流程执行记录（flow_report）",
        "",
        f"**开始时间**: {report.started_at}",
        f"**运行参数**: {report.note}",
        "",
        "| 阶段 | 状态 | 耗时(s) | 产物指纹 | 说明 |",
        "|------|------|---------|----------|------|",
    ]
    for r in report.stages:
        fps: str = ", ".join(r.fingerprints) or "-"
        lines.append(f"| {r.stage_id} | {r.status} | {r.duration_s} | {fps} | {r.detail} |")
    lines.append("")
    counts: dict[str, int] = _count_statuses(report)
    lines.append("## 汇总")
    lines.append("、".join(f"{k}={v}" for k, v in sorted(counts.items())))
    lines.append("")
    lines.append("> 缺口提示：状态含 `skipped_needs_api` → `python day34_orchestrator.py --with-llm` 补跑；")
    lines.append("> 含 `manual_pending` → 等 Day 35 两段式评审门；`run_failed` → 看对应 stage 输出。")
    return "\n".join(lines)


def flow_report_dir(ns: str = "") -> str:
    """flow_report 的落盘目录：'' → `outputs/flow`；'register' → `outputs/flow/register`。

    为什么跟随场景：一份 flow_report 只描述**一次**执行；两场景共用一份就互相
    覆盖，审计记录直接丢一半。
    """
    return os.path.join(FLOW_DIR, ns) if ns else FLOW_DIR


def persist_flow_report(report: FlowReport, ns: str = "") -> tuple[str, str]:
    """落盘 flow_report.json + .md，返回 (json_path, md_path)。

    Day 41：从私有的 `_persist_report` 提升为**公开入口**——因为
    `cli.py run` 也必须在跑完后留下审计记录（原来只有练习脚本会落盘，
    命令行跑完什么都不留，出了问题无从复盘）。
    """
    target_dir: str = flow_report_dir(ns)
    os.makedirs(target_dir, exist_ok=True)
    json_path: str = os.path.join(target_dir, "flow_report.json")
    md_path: str = os.path.join(target_dir, "flow_report.md")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(report.model_dump(), ensure_ascii=False, indent=2))
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_flow_report_markdown(report))
    return json_path, md_path


def _parse_flags(argv: list[str]) -> tuple[bool, bool, bool]:
    """手写 flag 解析（教学点：不用 argparse）。

    argparse.Namespace 的属性访问对 pyright 是 Any/未知——拼错 flag 名不报错，
    运行时才炸；手写返回显式 bool 三元组，pyright 全量检查（练习 4 坑 4）。
    """
    with_llm: bool = "--with-llm" in argv
    force: bool = "--force" in argv
    fail_fast: bool = "--fail-fast" in argv
    return with_llm, force, fail_fast


# ═══════════════════════════════════════════════════════
# 实验（练习 2：exp2 零 API 回放 + 双回路；练习 3 的 exp3/main 见第二部分）
# ═══════════════════════════════════════════════════════
def exp2_replay_and_exec() -> FlowReport:
    """默认演示：回放 reused 段 + 现场跑 S6/S7（mock+pytest）+ S8（报告）（零 API 零外网）。"""
    print("=" * 72)
    print("exp2_replay_and_exec：全流程执行（模型段跳过，code 段自动）")
    report = run_flow(with_llm=False, force=False)
    json_path, md_path = persist_flow_report(report)
    counts: dict[str, int] = _count_statuses(report)
    print("=" * 72)
    print(f"✅ flow_report 落盘: {json_path} / {md_path}")
    print(f"   状态汇总: {counts}")
    print("   → 打开 outputs/flow/exec_report_normal.md 看正常版报告（应 7/7 全绿）")
    print("   → 打开 outputs/flow/exec_report_bug.md 看埋 Bug 版报告（应抓到缺陷）")
    return report


# ═══════════════════════════════════════════════════════
# 第二部分（练习 3）：确定性复现验证 + flag 解析 + main 完成态
# ═══════════════════════════════════════════════════════
def exp3_regen_fingerprint_stable() -> None:
    """--force 重跑 S4（确定性代码渲染）两次，断言产物指纹不变（零 API）。

    教学点：代码段"同输入同输出"——重跑不产生漂移，指纹是它的证据；
    模型段做不到（非确定性），所以 Day 35 要用评审门把模型产物"锁住"。
    """
    spec: StageSpec = next(s for s in BLUEPRINT if s.stage_id == "S4_test_codegen")
    print("第一次 --force 重生成 S4 ...")
    _run_stage(spec, with_llm=False, force=True)
    fp1: list[str] = _fingerprints_of(spec)
    print("第二次 --force 再生成 S4 ...")
    _run_stage(spec, with_llm=False, force=True)
    fp2: list[str] = _fingerprints_of(spec)
    same: bool = fp1 == fp2
    print(f"指纹一致: {same}")
    for entry in fp1:
        print(f"   {entry}")
    if not same:
        raise SystemExit("❌ 确定性段重跑指纹变化——检查是否误触了模型/随机源（Day 30 模板渲染应纯确定）")
    print("✅ 确定性可复现：同输入同输出（day30 渲染器 + 蓝图契约的双保险）")



if __name__ == "__main__":
    # exp2_replay_and_exec()
    exp3_regen_fingerprint_stable()


    # """一键全流程：
    #    python day34_orchestrator.py              # 默认：回放 + 自动跑 code 段（零 API）
    #    python day34_orchestrator.py --with-llm   # 补跑 llm 缺口段（真 API）
    #    python day34_orchestrator.py --force      # 全部重跑（含 reused 段）
    #    python day34_orchestrator.py --fail-fast  # 遇 run_failed 中断
    # """
    # with_llm, force, fail_fast = _parse_flags(sys.argv[1:])
    # print("=" * 72)
    # print(f"main：with_llm={with_llm} force={force} fail_fast={fail_fast}")
    # report: FlowReport = run_flow(with_llm=with_llm, force=force, fail_fast=fail_fast)
    # json_path, md_path = _persist_report(report)
    # counts: dict[str, int] = _count_statuses(report)
    # print("=" * 72)
    # print(f"✅ flow_report 落盘: {json_path} / {md_path}")
    # print(f"   状态汇总: {counts}")
    # if any(r.status == "skipped_needs_api" for r in report.stages):
    #     print("   → 仍有 skipped_needs_api 段：python day34_orchestrator.py --with-llm 补跑")
    # if any(r.status == "manual_pending" for r in report.stages):
    #     print("   → manual_pending = S2 评审门占位，Day 35 两段式评审门落地后收口")

