"""
Day 30 练习 4：端到端执行闭环 —— plan json → pytest 代码 → mock 靶场 → 真实执行 → 报告

流程（设计决策 D：生成/评审/执行分段）：
  1. 从已落盘 plan json 读回 ApiDoc（不重跑 LLM，评审门思想）
  2. 确定性再生成 plan → 渲染 pytest 代码 → ast 校验 → 落盘 outputs/generated_tests/
  3. 起 mock（正常版）→ subprocess 运行 pytest（隔离，不污染当前进程 import）→ 解析结果 → 报告
  4. 起 mock（埋 Bug 版）→ 重跑 → 报告（演示生成代码抓到 2 个缺陷）

教学点：
  - subprocess 而非 pytest.main：生成的测试模块 import 副作用不污染主流程；
    且 capture_output + text=True 直接拿 str（不用 bytes.decode）
  - pytest -q 输出末尾 "N passed, M failed" → 正则解析（确定性代码算统计）

用法：
  python day30_run_pipeline.py    # 端到端（真实 API + mock，零外网）
"""
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from day30_mock_api import start_mock, stop_mock
from day30_pytest_generator import generate_api_tests_from_plan


@dataclass
class RunResult:
    """一次 pytest 执行的结果（统计由代码解析，不让模型算）。"""

    exit_code: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    failed_tests: list[str] = field(default_factory=list)
    output: str = ""


def run_pytest_on(test_dir: str) -> RunResult:
    """subprocess 运行 pytest（隔离 + 拿 str 输出）。

    ⚠️ text=True + encoding/errors：stdout 直接是 str（pyright 友好，无需 bytes.decode）。
    """
    proc: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, "-m", "pytest", test_dir, "-q", "--tb=short", "--no-header"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=180,
    )
    output: str = (proc.stdout or "") + (proc.stderr or "")
    result = RunResult(exit_code=proc.returncode, output=output)

    # 统计：pytest -q 末尾 "N passed" / "N failed" / "N errors"（正则逐个搜，缺省 0）
    passed_match: re.Match[str] | None = re.search(r"(\d+) passed", output)
    failed_match: re.Match[str] | None = re.search(r"(\d+) failed", output)
    error_match: re.Match[str] | None = re.search(r"(\d+) error", output)
    result.passed = int(passed_match.group(1)) if passed_match else 0
    result.failed = int(failed_match.group(1)) if failed_match else 0
    result.errors = int(error_match.group(1)) if error_match else 0

    # 失败用例名：pytest -q 输出 "FAILED test_x.py::TestY::test_z - AssertionError: ..."
    result.failed_tests = re.findall(r"FAILED ([\w./$$$$:-]+)", output)
    return result


def render_run_report(result: RunResult, mode: str, plan_md: str, test_paths: tuple[str, str]) -> str:
    """执行报告渲染（确定性代码；模式：正常版/埋Bug版）。"""
    lines: list[str] = [
        "# pytest 执行报告（生成代码）",
        "",
        f"**场景**: {mode}",
        f"**退出码**: {result.exit_code}（0=全部通过，1=有用例失败）",
        "",
        "## 执行摘要（由代码解析 pytest 输出）",
        "",
        f"- 通过: {result.passed}",
        f"- 失败: {result.failed}",
        f"- 错误: {result.errors}",
        "",
        "## 产物",
        "",
        f"- conftest: `{test_paths[0]}`",
        f"- 测试代码: `{test_paths[1]}`",
        f"- 接口测试计划: `{plan_md}`",
        "",
    ]
    if result.failed_tests:
        lines.append("## 失败用例（= 生成的代码发现的缺陷）")
        lines.append("")
        for name in result.failed_tests:
            lines.append(f"- `{name}`")
        lines.append("")
    lines.append("## pytest 输出尾部")
    lines.append("")
    lines.append("```")
    lines.append(result.output[-600:])
    lines.append("```")
    return "\n".join(lines) + "\n"


def exp4_full_pipeline(plan_json: str, name: str, bug_mode: bool = False) -> str | None:
    """端到端：plan json → 生成代码 → mock → pytest 执行 → 报告落盘。

    返回报告路径（任一步失败返回 None）。
    """
    here: str = os.path.dirname(os.path.abspath(__file__))
    out_dir: str = os.path.join(here, "..", "..", "outputs")
    gen_dir: str = os.path.join(out_dir, "generated_tests")
    os.makedirs(gen_dir, exist_ok=True)

    # 1. 从已落盘 plan json 读回 → 生成 pytest 代码（零 LLM）
    print("=" * 60)
    print(f"实验：exp4_full_pipeline —— 端到端执行闭环（{'埋Bug版' if bug_mode else '正常版'}）")
    paths = generate_api_tests_from_plan(plan_json, gen_dir)
    if paths is None:
        print("❌ 生成代码失败（plan json 读回失败）")
        return None
    print(f"  ✅ 生成代码: {paths[0]}")
    print(f"                {paths[1]}")

    # 2. 起 mock + subprocess 跑 pytest
    server = start_mock(port=8766, bug_mode=bug_mode)
    try:
        result: RunResult = run_pytest_on(gen_dir)
    finally:
        stop_mock()

    print(f"  ✅ pytest 执行: 通过={result.passed} 失败={result.failed} 错误={result.errors}（exit={result.exit_code}）")
    for t in result.failed_tests:
        print(f"     FAILED: {t}")

    # 3. 报告落盘
    plan_md: str = os.path.join(out_dir, f"api_test_plan_{name}.md")
    mode_label: str = "埋Bug版" if bug_mode else "正常版"
    report_md: str = render_run_report(result, mode_label, plan_md, paths)
    report_path: str = os.path.join(out_dir, f"pytest_run_report{'_bug' if bug_mode else ''}.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report_md)
    print(f"  ✅ 报告落盘: {report_path}")
    return report_path




if __name__ == "__main__":
    here: str = os.path.dirname(os.path.abspath(__file__))
    plan_json: str = os.path.join(here, "..", "..", "outputs", "api_test_plan_login.json")
    if not os.path.isfile(plan_json):
        print("❌ 未找到 api_test_plan_login.json——先跑练习 2 的 exp2_analyze_file 生成")
        exit(1)
    # 正常版：生成代码与接口契约一致 → 全绿
    exp4_full_pipeline(plan_json, name="login", bug_mode=False)
    print()
    # 埋 Bug 版：生成代码抓到 2 个缺陷（错误凭据 500 + 越权 200）
    exp4_full_pipeline(plan_json, name="login", bug_mode=True)
    print("\n💡 要点回顾：")
    print("   生成代码能跑（正常版全绿）+ 能抓 Bug（埋 Bug 版 2 个 FAIL）= 可执行资产成立")
    print("   subprocess 隔离运行 pytest：生成模块 import 副作用不污染主流程")

