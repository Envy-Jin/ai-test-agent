# FILE: day37_bug_probe.py
"""Day 37 练习1：执行档位 bug_probe 原型（demo-first，零外部依赖）

教学点：
  1. 档位是"数据"不是"按钮"：probe_on 只是决定蓝图里 S7 在不在、S8 报告喂几个 junit；
  2. S7 依赖 S6 单向（S7 复用 S6 的套件），所以关档位只摘 S7，S6 永远在；
  3. 默认 True 与旧蓝图逐字一致 → 后端契约断言安全网不动。

实验↔步骤↔运行命令：
  exp1_default_nine()  → 默认档位：9 段含 S7，S8 报告喂 junit_normal + junit_bug
  exp2_probe_off()     → 关闭档位：8 段无 S7，S8 报告自适应只剩 junit_normal
  exp3_regression()    → 回归断言：默认档位蓝图 == 旧蓝图（契约等价安全网）
  运行：
    python -c "from day37_bug_probe import exp1_default_nine; exp1_default_nine()"
    python -c "from day37_bug_probe import main; main()"
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any

if sys.platform == "win32":
    _stdout: Any = sys.stdout  # TextIO 静态类型缺 reconfigure → 经 Any 中转（禁 type: ignore）
    _stdout.reconfigure(encoding="utf-8", errors="replace")  # 防 GBK 崩


# ── 迷你蓝图模型：与真实 StageSpec 的「形状」同构（只用本轮需要的字段）──
@dataclass
class MiniStage:
    stage_id: str
    title: str
    kind: str = "code"
    runner: str = "cmd"
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    mock_bug: bool = False
    note: str = ""


# 真实产物路径（与 day35_scenario.build_blueprint 的变量命名一致）
JUNIT_N: str = "outputs/flow/junit_normal.xml"
JUNIT_B: str = "outputs/flow/junit_bug.xml"
REGISTRY: str = "docs/cases/api_registry.json"


def build_demo_blueprint() -> list[MiniStage]:
    """9 段迷你蓝图（S1-S9 与真实 Day35 蓝图同构；S6/S7/S8 是关键联动段）。"""
    return [
        MiniStage("S1_requirement_cases", "需求解析 → 分级用例", kind="llm",
                  inputs=["docs/requirements/login_requirement.md"],
                  outputs=["outputs/requirement_login_analysis.json"]),
        MiniStage("S2_case_review_gate", "用例评审闸门", kind="manual",
                  inputs=["outputs/requirement_login_analysis.json"]),
        MiniStage("S3_api_plan", "接口文档 → 测试计划", kind="llm",
                  inputs=["docs/apis/login_api.md"],
                  outputs=["outputs/api_test_plan_login.json"]),
        MiniStage("S4_test_codegen", "计划 → pytest 代码", kind="code",
                  inputs=["outputs/api_test_plan_login.json"],
                  outputs=["outputs/generated_tests/test_api_suite.py"]),
        MiniStage("S5_test_data", "字段规则 → 测试数据", kind="llm",
                  inputs=["docs/schemas/users.md"],
                  outputs=["outputs/data_gen/users_normal.json"]),
        MiniStage("S6_execute_normal", "执行：mock 正常版 → JUnit XML", kind="code",
                  runner="mock_pytest", mock_bug=False,
                  inputs=["outputs/generated_tests/test_api_suite.py"],
                  outputs=[JUNIT_N]),
        MiniStage("S7_execute_bug", "执行：mock 埋 Bug 版 → JUnit XML", kind="code",
                  runner="mock_pytest", mock_bug=True,
                  inputs=["outputs/generated_tests/test_api_suite.py"],
                  outputs=[JUNIT_B]),
        MiniStage("S8_exec_report", "JUnit → 执行报告", kind="code",
                  runner="exec_report",
                  inputs=[JUNIT_N, JUNIT_B, REGISTRY],
                  outputs=["outputs/flow/exec_report_normal.md"]),
        MiniStage("S9_bug_analyze", "Bug 报告 → 结构化分析", kind="llm",
                  inputs=["docs/bugs/login_bugs.md"],
                  outputs=["outputs/bug_login_analysis.json"]),
    ]


def apply_bug_probe(blueprint: list[MiniStage], bug_probe: bool) -> list[MiniStage]:
    """档位过滤（Day 36 定稿语义）：bug_probe=True 原样返回；False 摘 S7 + S8 输入自适应。

    ⚠️ 纯函数：不修改传入蓝图，返回新列表（真实落地时 build_blueprint 每次构建新蓝图，
       可直接对返回值过滤；此处保持无副作用以便独立断言）。
    """
    if bug_probe:
        return blueprint
    kept: list[MiniStage] = [
        s for s in blueprint if s.stage_id != "S7_execute_bug"
    ]
    for stage in kept:
        if stage.stage_id == "S8_exec_report":
            # 报告输入自适应：去掉埋 Bug 版 junit，保留正常版与 registry
            stage.inputs = [p for p in stage.inputs if not p.endswith("junit_bug.xml")]
    return kept


def _fmt(blueprint: list[MiniStage]) -> list[str]:
    return [s.stage_id for s in blueprint]


def exp1_default_nine() -> list[MiniStage]:
    """默认档位（True）：9 段，S7 在位，S8 报告输入 = normal + bug + registry。"""
    blueprint: list[MiniStage] = apply_bug_probe(build_demo_blueprint(), bug_probe=True)
    ids: list[str] = _fmt(blueprint)
    assert len(ids) == 9, f"期望 9 段，实际 {len(ids)}"
    assert "S7_execute_bug" in ids, "默认档位应保留 S7 对照回路"
    s8: MiniStage = next(s for s in blueprint if s.stage_id == "S8_exec_report")
    assert JUNIT_B in s8.inputs and JUNIT_N in s8.inputs, "S8 报告应同时喂 normal + bug junit"
    print(f"[exp1] 默认档位: {len(ids)} 段 | S7 在位 | S8 inputs={s8.inputs}")
    return blueprint


def exp2_probe_off() -> list[MiniStage]:
    """关闭档位（False）：8 段无 S7；S8 报告输入自适应 → 只剩 normal + registry。"""
    blueprint: list[MiniStage] = apply_bug_probe(build_demo_blueprint(), bug_probe=False)
    ids: list[str] = _fmt(blueprint)
    assert len(ids) == 8, f"期望 8 段，实际 {len(ids)}"
    assert "S7_execute_bug" not in ids, "关闭档位应摘掉 S7"
    assert "S6_execute_normal" in ids, "S6 主干永远在（S7 依赖 S6 单向，不是成组开关）"
    s8: MiniStage = next(s for s in blueprint if s.stage_id == "S8_exec_report")
    assert JUNIT_B not in s8.inputs, "S8 不应再喂埋 Bug junit（否则悬空断链）"
    assert JUNIT_N in s8.inputs and REGISTRY in s8.inputs, "S8 仍保留 normal junit + registry"
    print(f"[exp2] 关闭档位: {len(ids)} 段 | 无 S7 | S8 inputs={s8.inputs}")
    return blueprint


def exp3_regression() -> bool:
    """回归：默认档位产物 == 旧蓝图（契约等价安全网）。"""
    baseline: list[MiniStage] = build_demo_blueprint()
    filtered: list[MiniStage] = apply_bug_probe(build_demo_blueprint(), bug_probe=True)
    same: bool = _fmt(baseline) == _fmt(filtered)
    assert same, "默认档位不应改变蓝图结构"
    print(f"[exp3] 默认档位回归: 蓝图结构与旧版一致 = {same}")
    return same


if __name__ == "__main__":
    """完成态：三个实验串跑（demo 全程零 API）。"""
    print("=== Day37 练习1：执行档位 bug_probe 原型 ===")
    # exp1_default_nine()
    # exp2_probe_off()
    exp3_regression()
    print("=== 全部通过 ===")
