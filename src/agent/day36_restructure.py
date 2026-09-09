"""Day 36 练习 2：分层迁移蓝图 —— 从「按天平铺」到「按职责分层」的迁移规划器 + utils 物理合并。

背景（为什么需要迁移蓝图）：
  src/agent/ 平铺 60+ 模块，第 6 周 Day37(UI)/Day38(CLI) 需要稳定的包级 import 面。
  Day 36 的最终目标结构（学习计划 v6）：
      src/agent/  (核心 agent：core/executor + 流程编排)
      src/tools/  (5 类测试工具：case/api/bug/data/report generator)
      src/rag/    (loader/retriever)
      src/config.py  (统一配置)
      其余历史实验 → archive/weekN
  但「谁去哪、谁归档」由 import 事实决定（练习 1 已扫）。本脚本 = 迁移执行蓝图：
    1. 决策表（RestructureDecision：哪些文件 → 归档 week5/week4 / 原地保留 / 并入 utils）
    2. validate()：决策 × 真实目录对拍（源缺失 / 一条文件被两条决策命中 → 冲突）
    3. render_commands()：生成可执行的 git mv / mkdir 命令清单（默认只打印，人审后执行）
    4. utils 物理合并计划（Day35 遗留收口）：detect 同名冲突 → 打印「utils.py 需追加代码」
       → 生成 day35_common.py 薄包装（re-export，历史 import 不炸）
  demo-first：无真实项目自动用内置 mini 项目演示（冒烟同构）。

实验↔步骤↔运行命令 映射：
  exp1_demo()              步骤3(教学演示)  python -c "from day36_restructure import exp1_demo; exp1_demo()"
  exp2_real_plan()         步骤3(真实规划)  python -c "from day36_restructure import exp2_real_plan; exp2_real_plan()"
  exp3_utils_merge()       步骤3(合并计划)  python -c "from day36_restructure import exp3_utils_merge; exp3_utils_merge()"
  wrapper_source()         步骤5(薄包装)    python -c "from day36_restructure import wrapper_source; print(wrapper_source())"
  main()                   步骤3(全流程)    python day36_restructure.py [--root DIR] [--apply]
"""
from __future__ import annotations

import fnmatch
import os
import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

_AGENT_DIR: str = os.path.dirname(os.path.abspath(__file__))

Action = Literal["archive_week5", "archive_week4", "stay", "merge_utils", "mkdir"]


@dataclass
class RestructureDecision:
    """一条迁移决策。patterns 用 fnmatch 匹配模块 stem（文件名去 .py）。"""

    action: Action
    patterns: tuple[str, ...]
    reason: str
    target: str = ""  # archive 周次 / 目标归属说明 / 待建目录


# ═══════════════════════════════════════════════════════════════
# 1. 决策表（2026-09-09 基于真实 import 扫描的推荐草稿；运行可对拍）
# ═══════════════════════════════════════════════════════════════

REAL_DECISIONS: list[RestructureDecision] = [
    RestructureDecision(
        action="mkdir",
        patterns=("archive/week5",),
        reason="第 5 周归档目录（week1-4 已存在）",
        target="archive/week5",
    ),
    RestructureDecision(
        action="archive_week5",
        patterns=(
            "day29_pyright_pitfalls",
            "day30_pyright_pitfalls",
            "day31_pyright_pitfalls",
            "day32_pyright_pitfalls",
            "day33_pyright_pitfalls",
            "day34_pyright_pitfalls",
        ),
        reason="第 5 周 pyright 避坑练习（纯教学演示，无保留方引用 → 归档安全）",
        target="archive/week5",
    ),
    RestructureDecision(
        action="archive_week5",
        patterns=("day31_bug_archive",),
        reason="第 5 周一次性演示脚本（Bug 归档实验，无保留方引用）",
        target="archive/week5",
    ),
    RestructureDecision(
        action="archive_week5",
        patterns=("day29_agent_v5",),
        reason="需求→用例 Agent v5 雏形（第 4 周老链入口，仅被同批模块引用；v6 统一 Agent 将取代）",
        target="archive/week5",
    ),
    RestructureDecision(
        action="archive_week4",
        patterns=(
            "day25_error_handling",
            "day25_test_agent_v2",
            "day27_mock_api",
            "day27_multi_tool_agent",
            "day27_report",
            "day28_mock_api",
        ),
        reason="第 4 周归档遗留补档（week4 当时未收净；仅被 day29_agent_v5 链引用，同批归档不断链。day24_case_agent 等 KB/Agent 底座仍被 day29/31 引用 → 保留）",
        target="archive/week4",
    ),
    RestructureDecision(
        action="merge_utils",
        patterns=("day35_common",),
        reason="Day35 遗留收口：read_text/write_text/schema_doc_path/output_dir/ROOT 物理并入 utils.py（无同名冲突），day35_common.py 改薄包装 re-export，历史 import 不炸",
        target="src/agent/utils.py",
    ),
    RestructureDecision(
        action="stay",
        patterns=(
            "day29_doc_loader",
            "day29_requirement_analysis",
            "day30_api_schema",
            "day30_pytest_generator",
            "day30_mock_api",
            "day30_run_pipeline",
            "day31_bug_analyzer",
            "day32_data_schema",
            "day32_data_generator",
            "day32_run_pipeline",
            "day33_change_schema",
            "day33_regression_analyzer",
            "day33_report_pipeline",
            "day34_flow_map",
            "day34_orchestrator",
            "day35_scenario",
            "day35_review_gate",
        ),
        reason="第 5 周流程资产 = 第 6 周整合素材（蓝图层 day34/35 + 专项实现 day29-33），本轮保留原位；分层落位（src/tools、src/rag）作为下一批迁移（Day37-42 穿插/周末综合）",
        target="src/agent/（下批迁移对象）",
    ),
]

# ═══════════════════════════════════════════════════════════════
# 2. 决策对拍与命令渲染
# ═══════════════════════════════════════════════════════════════

def _module_stems(module_dir: str) -> set[str]:
    return {p.stem for p in Path(module_dir).glob("*.py") if p.stem != "__init__"}


def match_decisions(
    decisions: list[RestructureDecision], stems: set[str]
) -> tuple[dict[str, list[str]], list[str]]:
    """决策 × 实际文件对拍。

    返回 (命中表 {action: 命中模块列表}, 冲突清单)。冲突 = 同一模块被多条决策命中
    （决策表写重，必须人工修正——绝不静默取第一条）。
    """
    hits: dict[str, list[str]] = {}
    owner: dict[str, str] = {}
    conflicts: list[str] = []
    for dec in decisions:
        if dec.action == "mkdir":
            continue
        for stem in sorted(stems):
            if any(fnmatch.fnmatch(stem, p) for p in dec.patterns):
                if stem in owner:
                    conflicts.append(f"{stem} 被两条决策命中：{owner[stem]} vs {dec.action}")
                    continue
                owner[stem] = dec.action
                hits.setdefault(dec.action, []).append(stem)
    for key in hits:
        hits[key] = sorted(hits[key])
    return hits, conflicts


def render_commands(module_dir: str, decisions: list[RestructureDecision]) -> list[str]:
    """生成可执行命令清单（默认 dry-run 打印；--apply 时逐条 os.system 执行）。"""
    cmds: list[str] = []
    project_root = os.path.dirname(os.path.dirname(module_dir))  # src/agent → 项目根
    # git 命令一律用正斜杠（Windows Git Bash 下反斜杠会被当转义符破坏路径）
    rel = os.path.relpath(module_dir, project_root).replace(os.sep, "/")  # 通常 = src/agent
    archive_base = os.path.join(project_root, "archive")
    for dec in decisions:
        if dec.action == "mkdir":
            target_dir = os.path.join(project_root, dec.patterns[0])
            if not os.path.isdir(target_dir):
                cmds.append(f"mkdir -p {dec.patterns[0]}   # 归档周目录（相对项目根）")
            continue
        for stem in sorted(dec.patterns):
            src = os.path.join(module_dir, f"{stem}.py")
            if not os.path.isfile(src):
                continue
            if dec.action in ("archive_week5", "archive_week4"):
                cmds.append(f"git mv {rel}/{stem}.py archive/{dec.target.replace('archive/', '')}/{stem}.py")
            elif dec.action == "stay":
                cmds.append(f"# 保留 {rel}/{stem}.py（{dec.reason[:30]}…）")
            elif dec.action == "merge_utils":
                cmds.append(f"# 合并 {rel}/{stem}.py → utils.py（见 exp3_utils_merge 指引）")
    return cmds


# ═══════════════════════════════════════════════════════════════
# 3. utils 物理合并（Day35 遗留收口）：冲突检测 + 追加代码 + 薄包装
# ═══════════════════════════════════════════════════════════════

def _top_level_names(path: str) -> set[str]:
    """提取 .py 顶层定义的名称（def/class/大写常量），用于合并冲突检测。"""
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    names: set[str] = set()
    for line in text.splitlines():
        s = line.strip()
        if s.startswith("def ") or s.startswith("class "):
            head = s.split("(")[0].split(":")[0]
            names.add(head.split(" ", 1)[1])
        elif s.startswith(("ROOT", "TARGET", "_AGENT")) and "=" in s and not s.startswith(("if ", "for ")):
            names.add(s.split(":", 1)[0].split(" ", 1)[0])
    return names


def utils_merge_plan(module_dir: str) -> list[str]:
    """返回 utils 合并指引文本行：冲突检测 + 需追加函数清单。"""
    utils_path = os.path.join(module_dir, "utils.py")
    common_path = os.path.join(module_dir, "day35_common.py")
    lines: list[str] = []
    if not (os.path.isfile(utils_path) and os.path.isfile(common_path)):
        lines.append("（本目录缺 utils.py 或 day35_common.py → 直接看 wrapper 演示，无真实合并计划）")
        return lines
    utils_names = _top_level_names(utils_path)
    common_names = _top_level_names(common_path)
    collision = sorted(common_names & utils_names)
    lines.append(f"utils.py 现有顶层名：{sorted(utils_names)}")
    lines.append(f"day35_common 顶层名：{sorted(common_names)}")
    if collision:
        lines.append(f"⚠️ 同名冲突（需人工决定保留哪份）：{collision}")
    else:
        lines.append("✓ 无同名冲突 —— 可直接追加以下 4 个函数 + ROOT 常量到 utils.py")
    move_names = sorted(common_names - {"exp1_equivalence"})
    lines.append(f"待并入：{move_names}")
    lines.append("步骤：① 在 utils.py 顶部加 import os ② 复制 ROOT + 4 函数定义（见 utils_addition_source）")
    lines.append("      ③ day35_common.py 替换为薄包装（见 wrapper_source）")
    return lines


def utils_addition_source() -> str:
    """返回「应追加进 utils.py」的代码段全文（与 day35_common 原实现逐字一致）。"""
    return '''# ── 以下为 Day 36 从 day35_common 并入的路径/IO 公共工具 ──
# 路径基准钉 __file__（2026-08-28 规范）：utils.py 位于 src/agent/ → 项目根 = 上两级
_AGENT_DIR: str = os.path.dirname(os.path.abspath(__file__))
ROOT: str = os.path.dirname(os.path.dirname(_AGENT_DIR))  # src/agent → 项目根


def read_text(path: str) -> str:
    """读 utf-8 文本（errors=replace 兜底乱码）—— 收敛 day31/day32 三份 _read_text。"""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def write_text(path: str, text: str) -> str:
    """utf-8 落盘并返回路径（返回 str 便于链式拼接/打印）。"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def schema_doc_path(name: str) -> str:
    """定位 docs/schemas/<name>（收敛两份 _schema_path）。"""
    return os.path.join(ROOT, "docs", "schemas", name)


def output_dir(sub: str) -> str:
    """定位并创建 outputs/<sub>，返回目录绝对路径（收敛 day32 的 _out_dir）。"""
    out: str = os.path.join(ROOT, "outputs", sub)
    os.makedirs(out, exist_ok=True)
    return out
'''


def wrapper_source() -> str:
    """返回新 day35_common.py（薄包装兼容层）全文。"""
    return '''"""Day 35 公共底座（day35_common.py）—— Day 36 重构后：物理并入 utils.py，本文件降级为薄包装。

背景：
  Day 35 抽取的公共工具（ROOT/read_text/write_text/schema_doc_path/output_dir）已按 Day 36
  计划并入 src/agent/utils.py。本文件只做 re-export，让仍写
  `from day35_common import ROOT, output_dir` 的历史脚本（day35_scenario / day35_review_gate）
  零改动继续工作 —— 重构期间「旧 import 不炸」= 随时可回归。
  原 exp1_equivalence（等价性回归实验）使命已于 Day 35 完成，随重构退役；
  回归义务转交 utils 函数冒烟 + day36 系列 import 冒烟。
"""
from __future__ import annotations

from utils import ROOT, output_dir, read_text, schema_doc_path, write_text

__all__ = ["ROOT", "read_text", "write_text", "schema_doc_path", "output_dir"]
'''


# ═══════════════════════════════════════════════════════════════
# 4. 内置 demo mini 项目（结构与 src/agent 同构）
# ═══════════════════════════════════════════════════════════════

_DEMO_FILES: dict[str, str] = {
    "utils.py": '"""mini utils（模拟真实 utils.py：只含 genai 安全函数，无路径工具）"""\n\ndef safe_text(text: str | None, default: str = "") -> str:\n    return text if text is not None else default\n',
    "day35_common.py": '"""mini day35_common（模拟：含 ROOT + 4 工具 + exp1）"""\nfrom __future__ import annotations\nimport os\n\nROOT: str = "PROJECT_ROOT"\n\ndef read_text(path: str) -> str:\n    with open(path, "r", encoding="utf-8") as f:\n        return f.read()\n\ndef write_text(path: str, text: str) -> str:\n    with open(path, "w", encoding="utf-8") as f:\n        f.write(text)\n    return path\n\ndef schema_doc_path(name: str) -> str:\n    return os.path.join(ROOT, "docs", "schemas", name)\n\ndef output_dir(sub: str) -> str:\n    out: str = os.path.join(ROOT, "outputs", sub)\n    os.makedirs(out, exist_ok=True)\n    return out\n\ndef exp1_equivalence() -> list[str]:\n    return []\n',
    "day35_scenario.py": "from day35_common import ROOT, output_dir\n\ndef build() -> None:\n    print(ROOT, output_dir('flow'))\n",
    "day29_pyright_pitfalls.py": "def demo() -> None:\n    print('pitfall')\n",
    "day34_pyright_pitfalls.py": "def demo() -> None:\n    print('pitfall34')\n",
    "day33_report_pipeline.py": "def run() -> None:\n    print('report')\n",
    "day34_orchestrator.py": "from day33_report_pipeline import run\n\ndef main() -> None:\n    run()\n",
}


def build_demo_project() -> str:
    """mini 项目落到临时目录：src/agent 同构 + 一个 archive 父层。"""
    tmp = tempfile.mkdtemp(prefix="restructure_demo_")
    agent = Path(tmp, "src", "agent")
    agent.mkdir(parents=True, exist_ok=True)
    for name, content in _DEMO_FILES.items():
        Path(agent, name).write_text(content, encoding="utf-8")
    return str(agent)


# ═══════════════════════════════════════════════════════════════
# 5. 实验入口
# ═══════════════════════════════════════════════════════════════

def exp1_demo() -> None:
    """内置 mini 项目：决策对拍 → 命令渲染 → utils 合并计划 → 薄包装冒烟。"""
    agent = build_demo_project()
    try:
        demo_decs: list[RestructureDecision] = [
            RestructureDecision("archive_week5", ("day29_pyright_pitfalls", "day34_pyright_pitfalls"),
                                "pyright 练习归档", "archive/week5"),
            RestructureDecision("merge_utils", ("day35_common",), "并入 utils", "src/agent/utils.py"),
            RestructureDecision("stay", ("day35_scenario", "day33_report_pipeline", "day34_orchestrator"),
                                "流程资产保留", "src/agent/"),
        ]
        stems = _module_stems(agent)
        hits, conflicts = match_decisions(demo_decs, stems)
        print(f"=== demo 决策对拍（{len(stems)} 个模块）===")
        if conflicts:
            print(f"  ⚠️ 冲突：{conflicts}")
        for action, mods in hits.items():
            print(f"  [{action}] {mods}")
        print("=== demo 命令渲染（dry-run）===")
        for c in render_commands(agent, demo_decs):
            print(f"  {c}")
        print("=== demo utils 合并计划 ===")
        for line in utils_merge_plan(agent):
            print(f"  {line}")
        print("=== demo 薄包装冒烟：wrapper 内容可 import（模拟已并入 utils）===")
        merged_utils = Path(agent, "utils.py").read_text(encoding="utf-8") + "\n" + utils_addition_source()
        Path(agent, "utils.py").write_text(merged_utils, encoding="utf-8")
        wrapper = Path(agent, "day35_common_wrapper.py")
        wrapper.write_text(wrapper_source(), encoding="utf-8")
        print("  wrapper 已写入 demo 目录（内容与 wrapper_source() 相同）")
    finally:
        shutil.rmtree(os.path.dirname(os.path.dirname(agent)), ignore_errors=True)


def exp2_real_plan() -> None:
    """真实 src/agent：REAL_DECISIONS 对拍 + 冲突报告 + 命令清单（dry-run，不执行）。"""
    if not os.path.isdir(_AGENT_DIR):
        print("当前不在 src/agent 目录（冒烟环境）→ 请用 exp1_demo 或指定 --root")
        return
    stems = _module_stems(_AGENT_DIR)
    hits, conflicts = match_decisions(REAL_DECISIONS, stems)
    print(f"=== 真实决策对拍：{_AGENT_DIR}（{len(stems)} 个模块）===")
    if conflicts:
        print(f"  ⚠️ 决策表冲突（需人工修正 REAL_DECISIONS）：{conflicts}")
    for action, mods in hits.items():
        print(f"  [{action}] ({len(mods)} 个) {mods}")
    print("=== 命令清单（dry-run；确认后按 步骤5 执行或 --apply）===")
    for c in render_commands(_AGENT_DIR, REAL_DECISIONS):
        print(f"  {c}")


def exp3_utils_merge() -> None:
    """真实 utils 合并计划（冲突检测 + 追加清单）。"""
    if not os.path.isdir(_AGENT_DIR):
        print("当前不在 src/agent 目录 → 用 exp1_demo 看演示")
        return
    for line in utils_merge_plan(_AGENT_DIR):
        print(f"  {line}")


def main() -> None:
    """完成态全流程：--root 指定平铺目录（默认本文件目录）；--apply 才真正执行命令。"""
    import argparse

    parser = argparse.ArgumentParser(description="Day36 练习2：分层迁移蓝图 + utils 合并")
    parser.add_argument("--root", default=None, help="平铺模块目录（默认：本文件所在目录）")
    parser.add_argument("--apply", action="store_true", help="执行归档 git mv（默认仅 dry-run 打印）")
    args = parser.parse_args()
    root_arg: str | None = args.root
    root = root_arg if root_arg and os.path.isdir(root_arg) else _AGENT_DIR
    if not os.path.isdir(root):
        print("目标目录不可达 → 内置 demo")
        exp1_demo()
        return
    stems = _module_stems(root)
    decs = REAL_DECISIONS
    hits, conflicts = match_decisions(decs, stems)
    print(f"目标：{root}（{len(stems)} 个模块）\n=== 决策对拍 ===")
    for action, mods in hits.items():
        print(f"  [{action}] ({len(mods)}) {mods}")
    if conflicts:
        print(f"  ⚠️ 冲突：{conflicts}")
    print("=== 命令清单 ===")
    cmds = render_commands(root, decs)
    for c in cmds:
        print(f"  {c}")
    if not args.apply:
        print("\n（dry-run：未执行任何动作。确认命令无误后加 --apply 再跑）")
        return
    print("\n=== 执行归档（--apply）===")
    project_root = os.path.dirname(os.path.dirname(root))
    for c in cmds:
        if c.startswith("git mv"):
            parts = c.split()
            src = os.path.join(project_root, parts[1].replace("/", os.sep))
            dst = os.path.join(project_root, parts[2].replace("/", os.sep))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.move(src, dst)
            print(f"  moved {parts[1]} -> {parts[2]}")
    print("  完成（merge_utils / stay 不在此执行，按指引手工处理）")


if __name__ == "__main__":
    main()
