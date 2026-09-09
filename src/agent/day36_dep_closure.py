"""Day 36 练习 1：import 传递闭包分析 —— 归档 week5 之前的「断链安全网」。

背景（为什么先分析再归档——2026-09-07 定稿的第 5 周归档待办要求）：
  src/agent/ 平铺着 day18-day35 六十多个模块，彼此 import 织成网。第 5 周（day29-35）
  的「当日练习/pyright 避坑」脚本可以归档到 archive/week5/，但哪些能归档、哪些必须留，
  不能拍脑袋——week4 归档时就因为没查引用，把被后续引用的底座也搬走了（如 day24 的
  KB upsert 链被 day34 用到，实际必须留在 src/agent/）。
  归档安全判定的唯一依据 = import 引用事实：
    候选归档模块 X 若被「不在归档名单里」的模块引用 → 归档 X 会断链，必须留下（或同批归档）。

  本脚本 = 引用事实分析器（纯 stdlib，零 API）：
    1. scan_imports(module_dir)          扫目录，解析每个 .py 顶层 import，得「本地依赖」有向图
    2. reverse_refs(deps)                反图：每个模块被谁直接引用
    3. transitive_closure(seeds, deps)   「依赖闭包」：一组种子模块向前(被依赖)的完整传递集
    4. plan_archival(...)                归档裁决：候选清单 × 引用事实 → 阻断方/放行建议
    5. import_smoke(...)                 归档后静态冒烟：保留集内每个本地 import 目标是否仍可解析
  教学策略 demo-first：root 传真实 src/agent 出真实结论；目录不存在时自动用内置 demo 样例
  演示完整流程（冒烟/无项目环境同构可跑，逻辑与真实运行完全一致）。

实验↔步骤↔运行命令 映射：
  exp1_demo()          步骤2(教学演示)  python -c "from day36_dep_closure import exp1_demo; exp1_demo()"
  exp2_scan_real()     步骤2(真实目录)  python -c "from day36_dep_closure import exp2_scan_real; exp2_scan_real()"
  exp3_archival_plan() 步骤2(归档裁决)  python -c "from day36_dep_closure import exp3_archival_plan; exp3_archival_plan()"
  main()               步骤2(全流程)    python day36_dep_closure.py [--root DIR] [--apply-plan]
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

# ── 真实项目定位：脚本默认躺在 ai_test_agent/src/agent/（day18-35 平铺目录）
_AGENT_DIR: str = os.path.dirname(os.path.abspath(__file__))

# ═══════════════════════════════════════════════════════════════
# 1. 引用事实采集（纯静态解析，不 import 任何业务模块）
# ═══════════════════════════════════════════════════════════════

# 只匹配「顶层」from/import（缩进列 0），避免把函数内局部 import 当模块级事实
_IMPORT_RE = re.compile(r"^(?:from\s+([A-Za-z_]\w*)\s+import|import\s+([A-Za-z_]\w*))", re.MULTILINE)


def _local_names(module_dir: str) -> set[str]:
    """目录内所有 .py 模块名（不含 __init__），作为「本地依赖」的判定边界。"""
    return {p.stem for p in Path(module_dir).glob("*.py") if p.stem != "__init__"}


def scan_imports(module_dir: str) -> dict[str, set[str]]:
    """解析目录内每个 .py 的顶层 import，返回 {模块名: 直接本地依赖集}。

    只保留「目标也是本目录 .py」的依赖——第三方(pydantic/langchain…)与 stdlib 不在归档
    决策范围，跳过。返回按模块名排序的 dict。
    """
    local = _local_names(module_dir)
    deps: dict[str, set[str]] = {}
    for path in sorted(Path(module_dir).glob("*.py")):
        if path.stem == "__init__":
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        targets: set[str] = set()
        for m in _IMPORT_RE.finditer(text):
            name = m.group(1) or m.group(2)
            if name in local:
                targets.add(name)
        deps[path.stem] = targets
    return deps


def reverse_refs(deps: dict[str, set[str]]) -> dict[str, set[str]]:
    """反图：{被依赖模块: 直接引用它的模块集}。deps 里没有的 key 也会以空集出现。"""
    refs: dict[str, set[str]] = {m: set() for m in deps}
    for importer, targets in deps.items():
        for t in targets:
            if t in refs:
                refs[t].add(importer)
    return refs


def transitive_closure(seeds: set[str], deps: dict[str, set[str]]) -> set[str]:
    """seeds 的「依赖闭包」：从 seeds 出发沿被依赖方向传递，收集全部可达模块（含 seeds）。"""
    closure: set[str] = set(seeds)
    frontier: set[str] = set(seeds)
    while frontier:
        nxt: set[str] = set()
        for m in frontier:
            for t in deps.get(m, set()):
                if t not in closure:
                    closure.add(t)
                    nxt.add(t)
        frontier = nxt
    return closure


# ═══════════════════════════════════════════════════════════════
# 2. 归档裁决（决策 = 引用事实 × 候选清单）
# ═══════════════════════════════════════════════════════════════

@dataclass
class ArchivalVerdict:
    candidate: str            # 候选归档模块
    blockers: set[str] = field(default_factory=set)   # 引用它、但不在候选清单里的模块 → 阻断
    archived_together: set[str] = field(default_factory=set)  # 引用它、且同批归档的模块（无风险）
    block_reason: str = ""    # 人类可读的阻断说明


def plan_archival(candidates: list[str], deps: dict[str, set[str]]) -> list[ArchivalVerdict]:
    """对每个候选模块算归档裁决。

    规则：dependents(candidate) - set(candidates) 为空 → 放行（无人会因归档而断链）；
    非空 → 阻断，blockers 列出「必须一起处理/必须先改 import」的模块。
    """
    refs = reverse_refs(deps)
    cand_set = set(candidates)
    verdicts: list[ArchivalVerdict] = []
    for c in candidates:
        depend = refs.get(c, set())
        blockers = sorted(depend - cand_set)
        together = sorted(depend & cand_set)
        reason = ""
        if blockers:
            reason = f"被保留模块引用：{', '.join(blockers)} → 归档将断链，需先改其 import 或暂缓"
        verdicts.append(
            ArchivalVerdict(
                candidate=c,
                blockers=set(blockers),
                archived_together=set(together),
                block_reason=reason,
            )
        )
    return verdicts


def import_smoke(kept: list[str], deps: dict[str, set[str]]) -> list[str]:
    """归档后静态冒烟：kept（归档后仍留在目录的模块）里每个本地 import 是否仍可解析。

    返回问题清单（空 = 无断链）。教学用静态解析而非真 import——真 import 会触发模块级
    LLM 构造（需 key/网络），静态解析只证明「本地依赖闭环没破」。
    """
    problems: list[str] = []
    kept_set = set(kept)
    for m in kept:
        missing = sorted(deps.get(m, set()) - kept_set)
        if missing:
            problems.append(f"{m} 依赖已不在目录：{', '.join(missing)}")
    return problems


# ═══════════════════════════════════════════════════════════════
# 3. 内置 demo 样例（无真实项目时演示完整流程；结构与 src/agent 同构）
# ═══════════════════════════════════════════════════════════════

_DEMO_FILES: dict[str, str] = {
    # 保留底座（被多处引用，绝不能归档）
    "kb_upsert.py": "from doc_loader import split_doc\n\ndef upsert(text: str) -> int:\n    return len(split_doc(text))\n",
    "doc_loader.py": "def split_doc(text: str) -> list[str]:\n    return [text]\n",
    # 主干流程资产
    "case_agent.py": "from kb_upsert import upsert\n\ndef generate(requirement: str) -> dict[str, str]:\n    n = upsert(requirement)\n    return {'cases': str(n)}\n",
    # 候选归档：pyright 避坑练习（孤儿，无人引用）
    "day29_pyright_pitfalls.py": "from doc_loader import split_doc\n\ndef demo() -> None:\n    print(split_doc('x'))\n",
    # 候选归档：一次性实验（被保留模块引用 → 应被阻断，教学演示）
    "day31_bug_archive.py": "from case_agent import generate\n\ndef archive() -> None:\n    generate('bug')\n",
    # 候选归档：演示入口（自成一族，同批归档无风险）
    "day29_agent_v5.py": "from case_agent import generate\nfrom day31_bug_archive import archive\n\ndef run() -> None:\n    print(generate('r'), archive())\n",
}


def build_demo_project() -> str:
    """把 _DEMO_FILES 落到临时目录，返回目录路径（调用方负责清理）。"""
    tmp = tempfile.mkdtemp(prefix="dep_closure_demo_")
    for name, content in _DEMO_FILES.items():
        Path(tmp, name).write_text(content, encoding="utf-8")
    return tmp


# 候选归档清单（真实 src/agent 的推荐初稿 = 2026-09-09 实测扫描结论；练习里对拍裁决）
REAL_CANDIDATES: list[str] = [
    # 第 5 周 pyright 避坑练习（纯教学演示，无外部引用者）
    "day29_pyright_pitfalls",
    "day30_pyright_pitfalls",
    "day31_pyright_pitfalls",
    "day32_pyright_pitfalls",
    "day33_pyright_pitfalls",
    "day34_pyright_pitfalls",
    # 第 5 周一次性演示/入口脚本
    "day31_bug_archive",
    "day29_agent_v5",
]


# ═══════════════════════════════════════════════════════════════
# 4. 实验入口（教学步骤逐个调；main() 完成态全流程）
# ═══════════════════════════════════════════════════════════════

def _resolve_root(explicit: str | None) -> str:
    """目标目录解析：优先 --root；否则默认本文件所在目录（真实 = src/agent）。

    目录不存在时返回空串，由调用方降级到 demo。
    """
    if explicit:
        return explicit if os.path.isdir(explicit) else ""
    return _AGENT_DIR if os.path.isdir(_AGENT_DIR) else ""


def exp1_demo() -> None:
    """内置 demo：走一遍 扫描→反图→闭包→归档裁决→冒烟 全流程（零 API、零外网）。"""
    proj = build_demo_project()
    try:
        deps = scan_imports(proj)
        refs = reverse_refs(deps)
        print("=== demo 引用事实（模块 → 本地依赖）===")
        for m, ts in deps.items():
            print(f"  {m:<22} -> {sorted(ts)}")
        print("=== 反图（模块 → 被谁直接引用）===")
        for m in sorted(refs):
            if refs[m]:
                print(f"  {m:<22} <- {sorted(refs[m])}")
        print("=== 依赖闭包 demo：seeds={'day29_agent_v5'} ===")
        cl = transitive_closure({"day29_agent_v5"}, deps)
        print(f"  {sorted(cl)}")
        print("=== 归档裁决（候选 = 4 条，其中 kb_upsert 演示「被保留方引用 → 阻断」）===")
        cands = ["day29_pyright_pitfalls", "day31_bug_archive", "day29_agent_v5", "kb_upsert"]
        verdicts = plan_archival(cands, deps)
        for v in verdicts:
            flag = "放行" if not v.blockers else "阻断"
            print(f"  [{flag}] {v.candidate}  blockers={sorted(v.blockers)} 同批={sorted(v.archived_together)}")
        print("=== 冒烟：保留集 = 全模块 - 放行候选（被阻断的 kb_upsert 理应留下）===")
        released = {v.candidate for v in verdicts if not v.blockers}
        kept = sorted(set(deps) - released)
        problems = import_smoke(kept, deps)
        if problems:
            for p in problems:
                print(f"  ! {p}")
        else:
            print("  ✓ 空 = 归档「放行项」后保留集无本地断链")
    finally:
        import shutil

        shutil.rmtree(proj, ignore_errors=True)


def exp2_scan_real() -> None:
    """真实目录（src/agent）：打印全量本地引用事实。目录不可达时提示并退出。"""
    root = _resolve_root(None)
    if not root:
        print("未找到 src/agent（当前不在 ai_test_agent 项目内）→ 请用 demo 或指定 --root")
        return
    deps = scan_imports(root)
    print(f"=== 引用事实扫描：{root}（{len(deps)} 个模块）===")
    for m in sorted(deps):
        if deps[m]:
            print(f"  {m:<26} -> {sorted(deps[m])}")


def exp3_archival_plan() -> None:
    """真实目录归档裁决：对 REAL_CANDIDATES 逐条给放行/阻断结论 + 归档后冒烟。"""
    root = _resolve_root(None)
    if not root:
        print("未找到 src/agent → 降级 demo 演示裁决流程")
        proj = build_demo_project()
        try:
            deps = scan_imports(proj)
            _print_plan(deps, REAL_CANDIDATES[:3], demo=True)
        finally:
            import shutil

            shutil.rmtree(proj, ignore_errors=True)
        return
    deps = scan_imports(root)
    _print_plan(deps, REAL_CANDIDATES, demo=False)


def _print_plan(deps: dict[str, set[str]], candidates: list[str], demo: bool) -> None:
    label = "demo 目录" if demo else "src/agent"
    print(f"=== 归档裁决（候选 {len(candidates)} 条，{label}）===")
    present = [c for c in candidates if c in deps]
    absent = [c for c in candidates if c not in deps]
    if absent:
        print(f"  候选不存在于目录（跳过）：{absent}")
    verdicts = plan_archival(present, deps)
    blocked_total = 0
    for v in verdicts:
        if v.blockers:
            blocked_total += 1
        flag = "放行" if not v.blockers else "阻断"
        extra = f"  理由：{v.block_reason}" if v.blockers else ""
        print(f"  [{flag}] {v.candidate}{extra}")
    print(f"  小结：{len(present) - blocked_total}/{len(present)} 条可直接归档；{blocked_total} 条需先处理引用")
    if not demo:
        released = {v.candidate for v in verdicts if not v.blockers}
        kept = sorted(set(deps) - released)
        problems = import_smoke(kept, deps)
        print(f"=== 归档后冒烟（保留 {len(kept)} 个模块的本地依赖闭环）===")
        if problems:
            for p in problems:
                print(f"  ! {p}")
        else:
            print("  ✓ 无本地断链 —— 这批归档安全")
        print("  提示：归档动作本身（git mv → archive/week5/）见步骤 5 命令清单，本脚本只做裁决。")


def main() -> None:
    """完成态：全流程。--root 指向真实 src/agent 出真实结论；无参且在项目内则自动用真实目录。"""
    import argparse

    parser = argparse.ArgumentParser(description="Day36 练习1：import 传递闭包 → 归档裁决")
    parser.add_argument("--root", default=None, help="平铺模块目录（默认：本文件所在目录）")
    parser.add_argument("--apply-plan", action="store_true", help="(保留位) 打印可直接执行的归档 git mv 清单")
    args = parser.parse_args()
    root_arg: str | None = args.root
    root = _resolve_root(root_arg)
    if not root:
        print("目标目录不可达 → 执行内置 demo（exp1_demo 等价）")
        exp1_demo()
        return
    deps = scan_imports(root)
    print(f"目标：{root}，共 {len(deps)} 个模块\n")
    if root == _AGENT_DIR:
        exp2_scan_real()
        print()
    _print_plan(deps, REAL_CANDIDATES, demo=False)
    if args.apply_plan:
        print("\n=== 归档命令（git mv，供人工审阅后执行）===")
        present = [c for c in REAL_CANDIDATES if c in deps]
        for c in present:
            print(f"  git mv src/agent/{c}.py archive/week5/{c}.py")


if __name__ == "__main__":
    main()
