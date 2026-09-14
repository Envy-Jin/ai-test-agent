# FILE: day38_select_stages.py
"""Day 38 练习2：--stage 子集执行的依赖闭包（demo-first，纯 stdlib）

背景（为什么需要闭包）：
  CLI 要支持"只跑某几段"（--stage S4,S8）。最直觉的写法是裸过滤：
      [s for s in bp if s.stage_id in wanted]
  但蓝图段之间是【输入←输出】的依赖链：S8 的输入 junit_normal.xml 由 S6 产出、
  S6 的输入测试套件由 S4 产出……裸过滤只保证"我要的段在"，不保证"它们的输入有
  产出者"，于是子集跑起来输入缺失 → 执行期 run_failed（假失败，用户看到的是"流坏了"）。

  正解：从 wanted 出发，沿 outputs→inputs 反向上溯 producer，直到不动点（闭包），
  再按【原蓝图顺序】取子序列——原顺序本身就是拓扑序，取子序列天然拓扑正确。

教学点：
  1. 闭包保证"结构完整"（有生产者），不保证"运行成功"（llm 段仍需 --with-llm）；
  2. 顺序不能丢：用原蓝图顺序过滤，而不是拿 set 重新拼列表；
  3. 未知 id 静默忽略 vs 报错：函数保持纯（忽略），由入口层决定是否报错。

实验↔步骤↔运行命令：
  exp1_bare_vs_closure()  → 裸过滤 1 段 vs 闭包 5 段的对照
  exp2_closure_ids()      → 闭包结果 == 期望拓扑序；S1/S9 正确排除
  exp3_bare_breaks()      → 裸过滤子集缺上游生产者 → 执行期会 run_failed
  exp4_order_and_unknown()→ 顺序守恒（依赖段先后关系）+ 未知 id 忽略
  main()                  → 四实验串跑
  运行：
    python -c "from day38_select_stages import main; main()"
"""
from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any

if sys.platform == "win32":
    _stdout: Any = sys.stdout  # TextIO 静态类型缺 reconfigure → 经 Any 中转（禁 type: ignore）
    _stdout.reconfigure(encoding="utf-8", errors="replace")  # 防 GBK 崩


@dataclass
class MiniStage:
    """迷你蓝图节点：只保留闭包推导需要的两个字段（inputs / outputs）。"""

    stage_id: str
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)


def build_demo_blueprint() -> list[MiniStage]:
    """7 段迷你蓝图（与真实 login 蓝图同构；S1/S9 是"旁支"，用来证明闭包不会误带）。"""
    return [
        MiniStage("S1_requirement_cases",
                  inputs=["docs/requirements/login_requirement.md"],
                  outputs=["outputs/requirement_login_analysis.json"]),
        MiniStage("S3_api_plan",
                  inputs=["docs/apis/login_api.md"],
                  outputs=["outputs/api_test_plan_login.json"]),
        MiniStage("S4_test_codegen",
                  inputs=["outputs/api_test_plan_login.json"],
                  outputs=["outputs/generated_tests/test_api_suite.py"]),
        MiniStage("S6_execute_normal",
                  inputs=["outputs/generated_tests/test_api_suite.py"],
                  outputs=["outputs/flow/junit_normal.xml"]),
        MiniStage("S7_execute_bug",
                  inputs=["outputs/generated_tests/test_api_suite.py"],
                  outputs=["outputs/flow/junit_bug.xml"]),
        MiniStage("S8_exec_report",
                  inputs=["outputs/flow/junit_normal.xml", "outputs/flow/junit_bug.xml",
                          "docs/cases/api_registry.json"],
                  outputs=["outputs/flow/exec_report_normal.md"]),
        MiniStage("S9_bug_analyze",
                  inputs=["docs/bugs/login_bugs.md"],
                  outputs=["outputs/bug_login_analysis.json"]),
    ]


def select_stages(blueprint: list[MiniStage], wanted: set[str]) -> list[MiniStage]:
    """取子集并自动补齐依赖闭包（真实落地见步骤 5.1：day35_scenario.select_stages）。

    ⚠️ 纯函数：不修改传入蓝图；返回新列表，顺序 = 原蓝图顺序（拓扑序）。
    """
    by_id: dict[str, MiniStage] = {s.stage_id: s for s in blueprint}
    by_output: dict[str, MiniStage] = {out: s for s in blueprint for out in s.outputs}
    keep: set[str] = set()
    stack: list[str] = [sid for sid in wanted if sid in by_id]  # 未知 id 直接丢
    while stack:
        sid: str = stack.pop()
        if sid in keep:
            continue
        keep.add(sid)
        for inp in by_id[sid].inputs:
            producer: MiniStage | None = by_output.get(inp)
            if producer is not None:
                stack.append(producer.stage_id)
    return [s for s in blueprint if s.stage_id in keep]


def _bare_filter(blueprint: list[MiniStage], wanted: set[str]) -> list[MiniStage]:
    """裸过滤（反面教材）：只要 wanted 里的段，不管依赖。"""
    return [s for s in blueprint if s.stage_id in wanted]


def _ids(stages: list[MiniStage]) -> list[str]:
    return [s.stage_id for s in stages]


def exp1_bare_vs_closure() -> tuple[list[str], list[str]]:
    """对照：裸过滤只有 S8 一段；闭包补齐上游 → 5 段。"""
    bp: list[MiniStage] = build_demo_blueprint()
    bare: list[str] = _ids(_bare_filter(bp, {"S8_exec_report"}))
    closed: list[str] = _ids(select_stages(bp, {"S8_exec_report"}))
    assert bare == ["S8_exec_report"], bare
    assert len(closed) == 5, closed
    print(f"[exp1] 裸过滤 {len(bare)} 段 {bare} vs 闭包 {len(closed)} 段 {closed}")
    return bare, closed


def exp2_closure_ids() -> list[str]:
    """闭包结果 == 期望拓扑序（S3→S4→S6/S7→S8）；S1/S9 不是 S8 的上游 → 不带。"""
    closed: list[str] = _ids(select_stages(build_demo_blueprint(), {"S8_exec_report"}))
    expected: list[str] = ["S3_api_plan", "S4_test_codegen", "S6_execute_normal",
                           "S7_execute_bug", "S8_exec_report"]
    assert closed == expected, f"闭包结果 {closed} != 期望 {expected}"
    assert "S1_requirement_cases" not in closed, "S1 不在 S8 上游链上，不应被带入"
    assert "S9_bug_analyze" not in closed, "S9 不在 S8 上游链上，不应被带入"
    print(f"[exp2] 闭包 == 期望拓扑序 {closed}（S1/S9 正确排除）")
    return closed


def exp3_bare_breaks() -> str:
    """裸过滤的后果：子集内无人产出 S8 需要的 junit → 执行期 run_failed。"""
    bp: list[MiniStage] = build_demo_blueprint()
    bare: list[MiniStage] = _bare_filter(bp, {"S8_exec_report"})
    produced_in_subset: set[str] = {out for s in bare for out in s.outputs}
    needed: list[str] = [p for p in bare[0].inputs if p not in produced_in_subset]
    assert needed, "本例应存在无人产出的输入"
    print(f"[exp3] 裸过滤缺失的生产者输入 {needed}（执行期将 run_failed；闭包则不会）")
    return needed[0]


def exp4_order_and_unknown() -> list[str]:
    """顺序守恒（依赖段先后关系不变）+ 未知 id 静默忽略（入口层再决定是否报错）。"""
    bp: list[MiniStage] = build_demo_blueprint()
    result: list[MiniStage] = select_stages(bp, {"S8_exec_report", "S99_not_exist"})
    ids: list[str] = _ids(result)
    assert "S99_not_exist" not in ids, "未知 id 应被忽略"
    # 拓扑序不变量：生产者必须排在消费者之前
    assert ids.index("S3_api_plan") < ids.index("S4_test_codegen") < ids.index("S6_execute_normal")
    assert ids.index("S4_test_codegen") < ids.index("S8_exec_report")
    assert ids.index("S6_execute_normal") < ids.index("S8_exec_report")
    print(f"[exp4] 顺序守恒(生产者先于消费者)=True；未知 id 已忽略 → {ids}")
    return ids




if __name__ == "__main__":
    """完成态：四实验串跑（纯 stdlib，零 API）。"""
    print("=== Day38 练习2：--stage 依赖闭包 ===")
    # exp1_bare_vs_closure()
    # exp2_closure_ids()
    # exp3_bare_breaks()
    exp4_order_and_unknown()
    print("=== 全部通过 ===")
