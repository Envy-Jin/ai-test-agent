# FILE: day39_blueprint_contract.py —— 教学 lab（Day 39 步骤 3）
"""Day 39 练习2：把"静默失败"变成"可断言契约"（纯 stdlib 原型）

背景（为什么需要它）：
  select_stages 用 `by_output = {out: spec for spec in bp for out in spec.outputs}` 做反向索引。
  这行有两个**隐含前提**，破了都不报错、只静默出错：

    ① **输出路径全局唯一** —— 两个 stage 声明同一输出文件时，字典推导**后者覆盖前者**；
       于是"某段的上游生产者"被认错/丢失 → 闭包少补上游 → 执行期才 run_failed。
    ② **路径写法规范** —— 索引靠字符串**逐字相等**匹配；`./outputs/x` 与 `outputs/x`
       是两个不同的键，写法不规范 → 匹配不上 → 被误判为"外部输入" → 同样静默不补齐。

  本练习把这两条隐含前提写成**可断言的纯函数**（返回违规列表，空 = 合规）。
  步骤 5.3 把它并入 day35_scenario（真实签名收 list[StageSpec]），
  步骤 5.5 用测试钉住"当前 login / register 蓝图零违规"。
  教学点：隐患 → 契约 → 测试，是"静默失败"唯一被驯服的路径。

实验↔步骤↔运行命令：
  exp1_clean()          → 合规蓝图：违规列表为空
  exp2_duplicate_out()  → 检出"输出重复"（会静默覆盖 by_output 的那类）
  exp3_bad_path()       → 检出"路径未规范化"（./ 前缀、反斜杠）
  exp4_manual_no_out()  → manual 段无 outputs 是合法的（S2 就是这种段）
  main()                → 完成态：四实验串跑
  运行：
    python -c "from day39_blueprint_contract import main; main()"
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, Sequence

if sys.platform == "win32":
    _stdout: Any = sys.stdout  # TextIO 静态类型缺 reconfigure → 经 Any 中转（禁 type: ignore）
    _stdout.reconfigure(encoding="utf-8", errors="replace")


@dataclass(frozen=True)
class MiniSpec:
    """迷你 stage（只保留契约检查需要的字段）。"""

    stage_id: str
    kind: str = "code"
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()


def find_contract_violations(blueprint: Sequence[MiniSpec]) -> list[str]:
    """返回违规描述列表（空 = 合规）。纯函数：不改入参、不读文件系统。"""
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
                violations.append(f"{spec.stage_id}：路径未规范化 {path!r}")
    return violations


def _ids_to_str(blueprint: Sequence[MiniSpec]) -> str:
    return "、".join(s.stage_id for s in blueprint)


def exp1_clean() -> list[str]:
    """合规蓝图（含一个合法的 manual 段）→ 违规列表为空。"""
    clean: list[MiniSpec] = [
        MiniSpec("S1_req", kind="llm", inputs=("docs/req.md",), outputs=("out/req.json",)),
        MiniSpec("S2_gate", kind="manual", inputs=("out/req.json",)),
        MiniSpec("S8_report", inputs=("out/req.json",), outputs=("out/rep.md",)),
    ]
    violations: list[str] = find_contract_violations(clean)
    assert violations == [], violations
    print(f"[exp1] 合规蓝图（{_ids_to_str(clean)}）→ 违规 0 条")
    return violations


def exp2_duplicate_out() -> str:
    """两个 stage 声明同一输出 → 检出（这正是字典推导静默覆盖的那类隐患）。"""
    bad: list[MiniSpec] = [
        MiniSpec("A_produce", outputs=("out/same.json",)),
        MiniSpec("B_produce", outputs=("out/same.json",)),
    ]
    violations: list[str] = find_contract_violations(bad)
    assert any("输出重复" in v for v in violations), violations
    print(f"[exp2] 检出输出重复 → {violations[0]}")
    return violations[0]


def exp3_bad_path() -> list[str]:
    """路径写法不规范（./ 前缀 / 反斜杠）→ 检出（索引逐字匹配，写法不同 = 匹配不上）。"""
    bad: list[MiniSpec] = [
        MiniSpec("A", inputs=("./out/plan.json",), outputs=("out/a.json",)),
        MiniSpec("B", inputs=("out\\plan.json",), outputs=("out/b.json",)),
    ]
    violations: list[str] = find_contract_violations(bad)
    assert len(violations) == 2, violations
    print(f"[exp3] 检出路径不规范 {len(violations)} 条：{violations}")
    return violations


def exp4_manual_no_out() -> list[str]:
    """manual 段（评审门）本来就没有 outputs → 不算违规（S2 的真实形态）。"""
    ok: list[MiniSpec] = [MiniSpec("S2_case_review_gate", kind="manual", inputs=("out/req.json",))]
    violations: list[str] = find_contract_violations(ok)
    assert violations == [], violations
    print("[exp4] manual 段无 outputs → 合法（不算违规）")
    return violations


def main() -> None:
    """完成态：四实验串跑（纯 stdlib、零 IO、零 API）。"""
    print("=== Day39 练习2：蓝图契约检查（把静默失败变成可断言）===")
    exp1_clean()
    exp2_duplicate_out()
    exp3_bad_path()
    exp4_manual_no_out()
    print("=== 全部通过 ===")


if __name__ == "__main__":
    main()
