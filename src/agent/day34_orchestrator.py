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

MOCK_PORT: int = 8766
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


def _run_cmd(cmd_body: str) -> int:
    """执行蓝图 cmd（python -c 语句体）：llm 段在 --with-llm 时由子进程跑真 API。"""
    print(f"  ▶ python -c {cmd_body[:70]}...")
    proc: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, "-c", cmd_body],
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
    suite_file: str = _abs(spec.inputs[0])
    pytest_dir: str = os.path.dirname(suite_file)
    argv: list[str] = [
        sys.executable, "-m", "pytest", pytest_dir,
        "-q", "--no-header", "--junitxml", junit_abs,
    ]
    mode: str = "埋 Bug 版(bug_mode=True)" if spec.mock_bug else "正常版(bug_mode=False)"
    print(f"  ▶ mock {MOCK_PORT} {mode} → pytest → {junit_rel}")
    start_mock(MOCK_PORT, bug_mode=spec.mock_bug)
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
        f"# 全流程执行报告：login · {label}",
        "",
        f"**日期**: {datetime.now():%Y-%m-%d %H:%M}",
        "**执行**: mock 靶场 + outputs/generated_tests（7 pytest node）",
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
    registry: list[CaseEntry] = load_case_registry(REGISTRY_PATH)
    rendered: list[str] = []
    skipped: list[str] = []
    for out_rel in spec.outputs:
        keyword: str = "normal" if "normal" in out_rel else "bug"
        junit_abs: str = _abs(f"outputs/flow/junit_{keyword}.xml")
        if not os.path.isfile(junit_abs):
            skipped.append(f"{out_rel}（{keyword} 版 junit 不存在）")
            print(f"  ⏭ 跳过 {out_rel}：{keyword} 版 junit 不存在")
            continue
        with open(junit_abs, "r", encoding="utf-8") as f:
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


# ═══════════════════════════════════════════════════════
# 执行器（练习 2：单段执行 + 全流程执行）
# ═══════════════════════════════════════════════════════
def _run_stage(
    spec: StageSpec,
    *,
    with_llm: bool,
    force: bool,
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
            ok = _run_cmd(spec.cmd) == 0
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
) -> FlowReport:
    """按蓝图顺序执行全流程：一段失败不中断（失败隔离），--fail-fast 才中断。"""
    records: list[StageRecord] = []
    plan: list[StageSpec] = BLUEPRINT if blueprint is None else blueprint
    for spec in plan:
        record = _run_stage(spec, with_llm=with_llm, force=force)
        records.append(record)
        if record.status == "run_failed" and fail_fast:
            print("  ⚠️ --fail-fast：遇到 run_failed 中断整链")
            break
    return FlowReport(
        started_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        note=f"with_llm={with_llm} force={force} fail_fast={fail_fast}",
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


def _persist_report(report: FlowReport) -> tuple[str, str]:
    """落盘 flow_report.json + .md，返回 (json_path, md_path)。"""
    os.makedirs(FLOW_DIR, exist_ok=True)
    json_path: str = os.path.join(FLOW_DIR, "flow_report.json")
    md_path: str = os.path.join(FLOW_DIR, "flow_report.md")
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
    json_path, md_path = _persist_report(report)
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

