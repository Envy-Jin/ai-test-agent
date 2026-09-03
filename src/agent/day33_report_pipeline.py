"""Day 33 练习 4/5：执行结果（JUnit XML）→ 统计 → Markdown/JSON 回归报告。

练习 4（第一部分）：JUnit XML 解析 + 统计 + 报告渲染（纯工程，零 API）。
  执行结果走 CI 通用交换格式 JUnit XML（pytest --junitxml 内置能力，
  2026-09-02 联网核实：根节点 <testsuites>，testcase/failure 结构稳定）——
  比 Day 30"解析 pytest 输出文本尾部"稳：XML 是结构化数据，解析器以后
  接任何 CI 产物（Jenkins/GitLab）都能复用。
练习 5（第二部分，追加在文件末尾）：端到端回归闭环——mock 靶场跑
  变更前基线 vs 变更后（bug_mode），两份报告对比 = 回归的价值闭环。

分界（第五次落地，最完整一次）：
  变更解析 → 代码（day33_change_schema）
  影响判断 → 模型（day33_regression_analyzer）
  执行收集 → 代码（subprocess pytest --junitxml → xml 解析）
  统计汇总 → 代码（通过率可追溯到每一条 testcase）
  测试结论 → 规则模板（缺陷→风险→建议，确定性兜底；模型化是 Day 34-35 增强）

实验（cd src/agent）：
  练习 4：
    python -c "from day33_report_pipeline import exp6_report_from_sample; exp6_report_from_sample()"
  练习 5（见练习 5 步骤）：
    python -c "from day33_report_pipeline import exp7_end_to_end; exp7_end_to_end()"
    python day33_report_pipeline.py     # main 完成态
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

import xml.etree.ElementTree as ET
from datetime import datetime
from typing import Literal

from pydantic import BaseModel

# import 提前放：练习 5 才用到的也在这里（2026-09-02 规范，禁止"补 import"提示）
from day30_mock_api import start_mock, stop_mock  
from day33_change_schema import (  
    CASE_REGISTRY_PATH,
    CHANGE_DIFF_PATH,
    CaseEntry,
    ChangeInfo,
    load_case_registry,
    parse_git_diff,
    read_change_diff,
)
from day33_regression_analyzer import RegressionPlan  


# ── 路径（钉 __file__）──
_AGENT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT: str = os.path.dirname(os.path.dirname(_AGENT_DIR))
OUT_REGRESSION: str = os.path.join(_PROJECT_ROOT, "outputs", "regression")
SAMPLE_JUNIT: str = os.path.join(_PROJECT_ROOT, "docs", "samples", "regression_after_junit.xml")


# ═══════════════════════════════════════════════════════
# Schema：执行结果（练习 4）
# ═══════════════════════════════════════════════════════
TestStatus = Literal["passed", "failed", "skipped", "error"]


class TestCaseOutcome(BaseModel):
    """一条用例的执行结果（来自 JUnit XML 的确定性数据）。"""

    node_id: str          # classname::name（含 parametrize 变体）
    status: TestStatus
    duration: float = 0.0
    message: str = ""     # 失败/错误时的断言摘要（XML <failure message>）


class RunStats(BaseModel):
    """执行统计（纯代码计算，数字可审计）。"""

    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0

    @property
    def pass_rate(self) -> float:
        """通过率 = 除法，不许模型编（Day 31：模型不数数）。"""
        return round(self.passed / self.total * 100, 1) if self.total else 0.0


# ═══════════════════════════════════════════════════════
# JUnit XML 解析（练习 4 —— xml.etree 标准库，零新依赖）
# ═══════════════════════════════════════════════════════
def _status_of(testcase: ET.Element) -> TestStatus:
    """xunit2 判定：failure/error/skipped 是 testcase 的子元素（互斥）。"""
    if testcase.find("failure") is not None:
        return "failed"
    if testcase.find("error") is not None:
        return "error"
    if testcase.find("skipped") is not None:
        return "skipped"
    return "passed"


def _failure_message(testcase: ET.Element) -> str:
    """坑 1：ET find() 返回 Element | None → 判空后收窄；attrib.get 同理。"""
    for tag in ("failure", "error"):
        elem = testcase.find(tag)
        if elem is not None:
            msg = elem.attrib.get("message")
            if msg:
                return msg.strip()
            text = elem.text
            return (text or "").strip()
    return ""


def parse_junit_xml(xml_text: str) -> list[TestCaseOutcome]:
    """JUnit XML → 结构化结果。

    用 root.iter("testcase") 遍历，不依赖根节点名——pytest 新版根是
    <testsuites>（2026-09-02 联网核实），但旧版/其他工具可能是 <testsuite>。
    """
    root = ET.fromstring(xml_text)
    outcomes: list[TestCaseOutcome] = []
    for testcase in root.iter("testcase"):
        classname: str = testcase.attrib.get("classname", "")
        name: str = testcase.attrib.get("name", "")
        # 坑 2：attrib.get(key) 不传默认值才返回 str | None（typeshed 重载）；
        # "0" 或 0.0 都能喂 float()，空串用 0.0 兜底
        duration = float(testcase.attrib.get("time") or 0.0)
        outcomes.append(
            TestCaseOutcome(
                node_id=f"{classname}::{name}",
                status=_status_of(testcase),
                duration=duration,
                message=_failure_message(testcase),
            )
        )
    return outcomes


def summarize(outcomes: list[TestCaseOutcome]) -> RunStats:
    """统计：逐条数状态（确定性，纯代码）。"""
    stats = RunStats(total=len(outcomes))
    for o in outcomes:
        if o.status == "passed":
            stats.passed += 1
        elif o.status == "failed":
            stats.failed += 1
        elif o.status == "skipped":
            stats.skipped += 1
        else:
            stats.errors += 1
    return stats


def find_defects(outcomes: list[TestCaseOutcome]) -> list[TestCaseOutcome]:
    """坑 6：Literal 状态判定用显式 ==（in ("failed","error") 对 Literal 窄化不可靠）。"""
    return [o for o in outcomes if o.status == "failed" or o.status == "error"]


# ═══════════════════════════════════════════════════════
# node id ↔ 注册表 反查（练习 4 —— 尾缀匹配容错）
# ═══════════════════════════════════════════════════════
def lookup_case(node_id: str, registry: list[CaseEntry]) -> CaseEntry | None:
    """JUnit node_id → 注册表用例。

    pytest 的 classname 与注册表 pytest_ids 的文件前缀可能不一致（实测边界），
    用"类名::方法名[变体]"尾缀匹配容错——匹配不到返回 None，报告里显示 "?"。
    """
    for case in registry:
        for pid in case.pytest_ids:
            suffix: str = pid.split("::", 1)[1] if "::" in pid else pid
            if node_id.endswith(suffix):
                return case
    return None


# ═══════════════════════════════════════════════════════
# 报告渲染（练习 4 —— 学习计划 REPORT_TEMPLATE 原样落地）
# ═══════════════════════════════════════════════════════
def render_markdown_report(
    scenario: str,
    change: ChangeInfo,
    plan: RegressionPlan,
    registry: list[CaseEntry],
    outcomes: list[TestCaseOutcome],
    stats: RunStats,
    defects: list[TestCaseOutcome],
    conclusion: str,
) -> str:
    """回归测试报告 Markdown。

    统计/明细/缺陷 = 代码（从 outcomes 推导）；conclusion 由调用方传入
    （练习 4/5 用规则结论 rule_conclusion 兜底）。表格用列表拼接 + join，
    不碰 f-string 花括号（Day 30 坑 1）。
    """
    changed = ", ".join(f.path for f in change.changed_files)
    lines: list[str] = [
        f"# 回归测试报告：{scenario}",
        "",
        f"**日期**: {datetime.now():%Y-%m-%d %H:%M}",
        "**执行人**: AI Agent（mock 靶场）",
        f"**变更文件**: {changed}",
        f"**变更摘要**: {plan.change_summary}",
        f"**回归范围**: 必回归 {plan.case_ids('must')} / 建议 {plan.case_ids('should')} / 跳过 {plan.case_ids('skip')}",
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
        module = case.module if case is not None else "?"
        note = (o.message[:80]).replace("|", "/") if o.message else ""
        lines.append(f"| {o.status} | {o.node_id.split('::')[-1]} | {module} | {o.duration:.3f} | {note} |")
    lines.append("")
    lines.append("## 缺陷列表（疑似回归缺陷）")
    if not defects:
        lines.append("- 无")
    for idx, d in enumerate(defects, start=1):
        case = lookup_case(d.node_id, registry)
        head = f"{case.case_id} {case.title}" if case is not None else d.node_id
        lines.append(f"{idx}. **{head}** —— {d.message[:120]}")
    lines.append("")
    lines.append("## 测试结论")
    lines.append(conclusion)
    return "\n".join(lines)


def rule_conclusion(stats: RunStats, defects: list[TestCaseOutcome], registry: list[CaseEntry]) -> str:
    """规则结论（确定性兜底）：全绿 → 可上线；有缺陷 → 点名并建议修复后重跑。

    扩展路径（笔记待办）：结论交给模型写——只喂 stats + defects 文本，
    不许它数数（Day 34-35 综合项目可选增强）。
    """
    if not defects:
        return "未发现回归缺陷：本次变更范围内的用例全部通过，建议补充 need_add 用例后放行上线。"
    names: list[str] = []
    for d in defects:
        case = lookup_case(d.node_id, registry)
        names.append(f"{case.case_id}({case.title})" if case is not None else d.node_id)
    joined = ", ".join(names)
    return (
        f"检出 {len(defects)} 个疑似回归缺陷：{joined}。"
        "这些用例在变更前基线是通过的——本次变更极可能引入了回归，"
        "建议修复后重跑 affected 范围（Day 31 Bug 分析流程可接续分析）再上线。"
    )


# ═══════════════════════════════════════════════════════
# 第二部分（练习 5）：回归执行（mock 靶场 + pytest 子集）+ 端到端 main
# ═══════════════════════════════════════════════════════
def expand_nodes(case_ids: list[str], registry: list[CaseEntry]) -> list[str]:
    """用例 id 列表 → pytest node id 展开（保持注册表内顺序；找不到的 id 跳过）。"""
    by_id: dict[str, CaseEntry] = {c.case_id: c for c in registry}
    nodes: list[str] = []
    for cid in case_ids:
        case = by_id.get(cid)
        if case is not None:
            nodes.extend(case.pytest_ids)
    return nodes


def run_regression_subset(gen_dir: str, junit_path: str, skip_nodes: list[str]) -> int:
    """subprocess 跑 pytest（隔离，不污染当前进程 import）：全量 - deselect 跳过档。

    返回退出码（0=全过 / 1=有用例失败 / 其他=执行错误）；JUnit XML 落盘 junit_path。
    """
    argv: list[str] = [
        sys.executable, "-m", "pytest", gen_dir,
        "-q", "--no-header", "--junitxml", junit_path,
    ]
    for node in skip_nodes:
        argv.append(f"--deselect={node}")
    print("执行（子集 = 全量 -", len(skip_nodes), "跳过）...")
    proc = subprocess.run(argv, capture_output=True, timeout=120)
    # 坑 5：capture_output 的 stdout 是 bytes | None → or b"" 后 decode
    tail = (proc.stdout or b"").decode("utf-8", errors="replace")
    print(tail[-300:])
    return int(proc.returncode)


# ═══════════════════════════════════════════════════════
# 实验（练习 4：exp6 零 API；练习 5 的 exp7/main 见第二部分）
# ═══════════════════════════════════════════════════════
def exp6_report_from_sample() -> None:
    """零 API：读样本 JUnit XML（练习 4.2 创建）→ 解析 → 统计 → 报告落盘。"""
    if not os.path.exists(SAMPLE_JUNIT):
        print("⚠️ 未找到样本 JUnit，请先按练习 4.2 创建 docs/samples/regression_after_junit.xml")
        return
    with open(SAMPLE_JUNIT, "r", encoding="utf-8") as f:
        outcomes = parse_junit_xml(f.read())
    stats = summarize(outcomes)
    defects = find_defects(outcomes)
    registry = load_case_registry(CASE_REGISTRY_PATH)
    diff_text = read_change_diff(CHANGE_DIFF_PATH)
    change = parse_git_diff(diff_text)
    # 报告层与计划层解耦：这里手工构造一个空档位计划只演示渲染（练习 5 会喂真计划）
    plan = RegressionPlan(
        change_summary="（样本报告）变更后执行结果",
        impacted_modules=["login", "orders"],
        must_regression=[], should_regression=[], can_skip=[], need_add=[],
    )
    os.makedirs(OUT_REGRESSION, exist_ok=True)
    md = render_markdown_report(
        "变更后（样本）", change, plan, registry,
        outcomes, stats, defects, rule_conclusion(stats, defects, registry),
    )
    report_path = os.path.join(OUT_REGRESSION, "report_sample.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"✅ 样本报告已落盘: {report_path}")
    print(f"   统计: total={stats.total} passed={stats.passed} failed={stats.failed} 通过率={stats.pass_rate}%")



def exp7_end_to_end() -> None:
    """端到端回归闭环：变更前基线 vs 变更后（bug_mode 模拟重构缺陷）。

    数据流：regression_plan.json（练习 3 落盘）→ 圈出执行子集
    （全量 7 node - can_skip）→ mock 靶场（day30_mock_api）→ junit 解析 →
    统计 → 规则结论 → Markdown + JSON 报告落盘。
    场景闭环：start_mock → run → stop_mock（mock 全局单例，每场景必须成对）。
    """
    plan_json = os.path.join(OUT_REGRESSION, "regression_plan.json")
    if not os.path.exists(plan_json):
        print("⚠️ 未找到 regression_plan.json，请先跑练习 3（day33_regression_analyzer.py）")
        return
    gen_dir = os.path.join(_PROJECT_ROOT, "outputs", "generated_tests")
    if not os.path.exists(gen_dir):
        print("⚠️ 未找到 outputs/generated_tests/，请先跑 day30_run_pipeline.py 生成测试套件")
        return
    with open(plan_json, "r", encoding="utf-8") as f:
        plan = RegressionPlan.model_validate(json.load(f))
    registry = load_case_registry(CASE_REGISTRY_PATH)
    diff_text = read_change_diff(CHANGE_DIFF_PATH)
    change = parse_git_diff(diff_text)
    skip_nodes = expand_nodes(plan.case_ids("skip"), registry)
    os.makedirs(OUT_REGRESSION, exist_ok=True)

    scenarios: list[tuple[str, bool]] = [
        ("变更前基线", False),
        ("变更后（重构缺陷模拟）", True),
    ]
    for scenario, bug_mode in scenarios:
        tag = "before" if not bug_mode else "after"
        junit_path = os.path.join(OUT_REGRESSION, f"junit_{tag}.xml")
        server = start_mock(port=8766, bug_mode=bug_mode)
        try:
            code = run_regression_subset(gen_dir, junit_path, skip_nodes)
            with open(junit_path, "r", encoding="utf-8") as f:
                outcomes = parse_junit_xml(f.read())
        except Exception as exc:
            print(f"[exp7] 场景「{scenario}」执行失败: {exc}")
            continue
        finally:
            stop_mock()
        stats = summarize(outcomes)
        defects = find_defects(outcomes)
        conclusion = rule_conclusion(stats, defects, registry)
        md = render_markdown_report(
            scenario, change, plan, registry,
            outcomes, stats, defects, conclusion,
        )
        md_path = os.path.join(OUT_REGRESSION, f"report_{tag}.md")
        json_path = os.path.join(OUT_REGRESSION, f"report_{tag}.json")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md)
        report_json: dict[str, object] = {
            "scenario": scenario,
            "bug_mode": bug_mode,
            "exit_code": code,
            "stats": stats.model_dump(),
            "defects": [d.model_dump() for d in defects],
            "conclusion": conclusion,
        }
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(report_json, f, ensure_ascii=False, indent=2)
        print(f"✅ [{scenario}] exit={code} total={stats.total} passed={stats.passed} "
              f"failed={stats.failed} 通过率={stats.pass_rate}%")
        print(f"   报告: {md_path}")







if __name__ == "__main__":
    """完成态（练习 5 末尾才出现）：端到端回归闭环（mock + pytest，零外网）。"""
    # exp6_report_from_sample()
    exp7_end_to_end()