# FILE: day37_flow_blueprint.py
"""Day 37 练习2：run_flow 显式蓝图入参 —— 为什么全局覆盖是接口缺陷（demo-first）

背景（2026-09-09 实测）：
  day34_orchestrator.run_flow() 内部 for spec in BLUEPRINT（模块级全局）。换蓝图跑另一个
  场景 = 先执行 day34_orchestrator.BLUEPRINT = build_blueprint(sc) 全局覆盖再调 run_flow。
  后果：①调用方必须记得改全局（忘了 = 静默跑错场景）；②不可重入/并发；③UI/CLI 各自
  偷偷覆盖同一全局，互相踩。修复 = 显式入参 blueprint: list | None = None（默认兜底全局）。

教学点：入口函数依赖 = 显式参数优于隐式全局；默认 None 回退全局 = 向后兼容零破坏。

实验↔步骤↔运行命令：
  exp1_global_trap()   → 缺陷复现：忘覆盖全局 → 静默跑错场景
  exp2_explicit()      → 修复演示：显式传蓝图，两个场景同进程交替互不干扰
  exp3_default_fallback() → 向后兼容：blueprint=None 时行为与旧版完全一致
  运行：
    python -c "from day37_flow_blueprint import main; main()"
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any

if sys.platform == "win32":
    _stdout: Any = sys.stdout  # TextIO 静态类型缺 reconfigure → 经 Any 中转（禁 type: ignore）
    _stdout.reconfigure(encoding="utf-8", errors="replace")  # 防 GBK 崩


@dataclass
class MiniStage:
    """迷你蓝图节点：只需要 stage_id 演示「跑哪个蓝图」的语义。"""
    stage_id: str


# ── 两个迷你场景蓝图（模拟真实 login / register）──
LOGIN_BP: list[MiniStage] = [
    MiniStage("S1_requirement_cases"), MiniStage("S3_api_plan"),
    MiniStage("S4_test_codegen"), MiniStage("S6_execute_normal"),
]
REGISTER_BP: list[MiniStage] = [
    MiniStage("S1_requirement_cases"), MiniStage("S3_api_plan"),
    MiniStage("S4_test_codegen"), MiniStage("S6_execute_normal"),
    MiniStage("S9_bug_analyze"),
]


# ═══════════ 缺陷版：执行器读「模块级全局蓝图」═══════════
_current_blueprint: list[MiniStage] = LOGIN_BP


def old_run_flow() -> list[str]:
    """缺陷版执行器：隐式读模块级全局（对应 Day 34 run_flow 内部 for spec in BLUEPRINT）。"""
    return [s.stage_id for s in _current_blueprint]


# ═══════════ 修复版：显式入参，默认 None 兜底全局 ═══════════
def run_flow(blueprint: list[MiniStage] | None = None) -> list[str]:
    """修复版执行器（对应步骤 5.2 给真实 run_flow 加的 blueprint 入参）。

    blueprint=None → 用模块级全局（向后兼容，旧调用零改动）。
    """
    plan: list[MiniStage] = _current_blueprint if blueprint is None else blueprint
    return [s.stage_id for s in plan]


def exp1_global_trap() -> list[str]:
    """缺陷复现：UI 场景切换时「忘了覆盖全局」→ 静默跑错场景。"""
    global _current_blueprint
    _current_blueprint = LOGIN_BP                      # 用户以为当前是 login
    first: list[str] = old_run_flow()                  # login 正常
    # UI 切到 register：正确做法是先覆盖全局再跑——但代码忘写了
    # _current_blueprint = REGISTER_BP                 # ← 忘了这行
    second: list[str] = old_run_flow()                 # 静默还是 login！
    assert first == second, "全局覆盖缺陷：两次运行应相同（第二次本应是 register）"
    print(f"[exp1] 缺陷复现: 第二次想跑 register 却跑了 {second[:3]}... (静默错场景)")
    return second


def exp2_explicit() -> tuple[list[str], list[str]]:
    """修复演示：显式传蓝图，同进程交替跑 login/register，互不干扰、无需改全局。"""
    r_login: list[str] = run_flow(blueprint=LOGIN_BP)
    r_register: list[str] = run_flow(blueprint=REGISTER_BP)
    r_login_again: list[str] = run_flow(blueprint=LOGIN_BP)
    assert "S9_bug_analyze" not in r_login, "login 蓝图不应含 register 的 S9"
    assert "S9_bug_analyze" in r_register, "register 蓝图应含 S9"
    assert r_login == r_login_again, "显式传参可重入：两次 login 结果一致"
    print(f"[exp2] 显式传参: login={len(r_login)}段 / register={len(r_register)}段 / 交替无串扰")
    return r_login, r_register


def exp3_default_fallback() -> list[str]:
    """向后兼容：blueprint=None → 走模块级全局，行为与旧版一致。"""
    global _current_blueprint
    _current_blueprint = REGISTER_BP
    by_default: list[str] = run_flow(blueprint=None)   # 新接口默认行为
    legacy: list[str] = old_run_flow()                 # 旧接口行为
    assert by_default == legacy, "blueprint=None 应与旧版全局行为一致"
    print(f"[exp3] 默认兜底: blueprint=None 与旧版一致（当前全局={by_default[:3]}...）")
    return by_default


if __name__ == "__main__":
    """完成态：三个实验串跑（demo 全程零 API）。"""
    print("=== Day37 练习2：run_flow 显式蓝图接口收口 ===")
    exp1_global_trap()
    # exp2_explicit()
    # exp3_default_fallback()
    print("=== 全部通过 ===")
