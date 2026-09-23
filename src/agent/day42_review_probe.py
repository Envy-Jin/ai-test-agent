# FILE: day42_review_probe.py
"""Day 42 练习 1：复盘探测 —— 把母计划 Day 42 的 7 条复盘清单变成「静态可断言」。

为什么要有这一层：
  Day 41 最贵的一课是「接缝的问题只以'绿着错'出现」。复盘清单是同一类东西——
  「README 完整（含截图）」如果只靠眼看，**引用了一张不存在的截图**不会有人发现；
  「CLI 命令全部可用」如果只靠手敲，**漏敲一个子命令**同样不会有人发现。
  所以能静态化的部分全部变成断言（零 API、零外网、只读 + 落盘一份报告），
  人只需要看剩下的、**真正需要人眼**的那部分（截图观感 / commit 历史 / 总结质量）。

三个板块（报告里分开写，别混成一锅）：
  A. 自动化断言 · 必须全过 —— 不过就是「复盘未通过」，先修再继续
  B. 能力矩阵 · 在册 / 缺口 —— 5 类任务能力各自的生产入口；缺的要**如实标注**
  C. 需人工确认 · 脚本只打印不打勾 —— 截图清不清楚、commit 历史可不可读、总结写没写

刻意**不 import** 的两个模块（冷启动纪律，Day 38 起沿用）：
  · `day31_bug_analyzer` —— 顶层拖 langchain_google_genai，实测冷启动 ≈50-66s
  · `ui.app`             —— 顶层拖 streamlit，AppTest 单次渲染 ≈10s
  这两处今天用**文件系统 / 源码文本**检查：要守的是「入口在位」「写法没退化」，
  而不是它们的运行结果 —— 运行结果由 test_day37_app.py 与人工验收负责。

实验↔步骤↔运行命令 映射：
  check_scenario_contracts()  步骤2  python -c "from day42_review_probe import check_scenario_contracts; print(check_scenario_contracts())"
  check_cli_surface()         步骤2  （同上，替换函数名）
  check_readme_assets()       步骤2  （同上）
  check_single_source()       步骤2  （同上）
  exp1_review_report()        步骤2  python day42_review_probe.py
  main()                      步骤2  python day42_review_probe.py（完成态：落盘 + 判是否通过）
"""
from __future__ import annotations

import io
import os
import re
import sys
from typing import TYPE_CHECKING

# ── import 桥（与 tests/conftest.py 同构）──
# 本脚本要同时够到两头：`day35_*`（在 src/agent 平铺、彼此裸 import）与
# `cli`（在项目根）。所以两个目录都进 sys.path —— 这样 cd 在哪都能跑，
# 不必记"这个脚本必须在哪个目录下执行"。
_AGENT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT: str = os.path.dirname(os.path.dirname(_AGENT_DIR))
for _candidate in (_PROJECT_ROOT, _AGENT_DIR):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)

from click.testing import CliRunner  # noqa: E402

from day35_common import ROOT, output_dir, read_text, write_text  # noqa: E402
from day35_scenario import (  # noqa: E402
    SCENARIO_REGISTRY,
    ScenarioConfig,
    find_scenario_collisions,
    find_scenario_contract_violations,
)

if TYPE_CHECKING:  # 仅静态检查可见（Day 38 冷启动纪律：类型只用于注解）
    from click.testing import Result

if sys.platform == "win32":
    # 与 `check_env.py` 同法（Day 41 改动 4h）：用 isinstance 收窄，
    # **不用 `# type: ignore`** —— `sys.stdout` 的静态类型是 TextIO，
    # `reconfigure` 只在 TextIOWrapper 上（`hasattr` 不能用于类型收窄）。
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ═══════════════════════════════════════════════════════
# 通用：路径与存在性（钉 __file__ 的项目根，不用 cwd）
# ═══════════════════════════════════════════════════════
def _rel(path_rel: str) -> str:
    """相对项目根的路径 → 绝对路径。"""
    return os.path.join(ROOT, path_rel)


def _is_file(path_rel: str) -> bool:
    """文件存在且非空（空文件 = 失败产物，不算数）。"""
    abs_path: str = _rel(path_rel)
    return os.path.isfile(abs_path) and os.path.getsize(abs_path) > 0


# ═══════════════════════════════════════════════════════
# A-1：场景契约 + 产物互斥（遍历注册表，**不点名场景**）
# ═══════════════════════════════════════════════════════
def check_scenario_contracts() -> list[str]:
    """注册表里的**每个**场景都过契约自检，且所有场景产物两两互斥。

    ⚠️ 写法要点：`tuple(SCENARIO_REGISTRY.values())` 而不是 `(LOGIN, REGISTER)`。
    Day 42 的演示场景（refund）就是被这个差别照出来的：写死清单的检查函数
    **多一个场景不会报错，只会少看一个** —— 报告照旧"全绿"。
    """
    problems: list[str] = []
    scenarios: tuple[ScenarioConfig, ...] = tuple(SCENARIO_REGISTRY.values())
    for sc in scenarios:
        for violation in find_scenario_contract_violations(sc):
            problems.append(f"[契约] {violation}")
    for collision in find_scenario_collisions(scenarios):
        problems.append(f"[产物冲突] {collision}")
    return problems


# ═══════════════════════════════════════════════════════
# A-2：CLI 命令面（--help 是零副作用的，所以可以在不跑流程的前提下验完）
# ═══════════════════════════════════════════════════════
CLI_COMMANDS: frozenset[str] = frozenset({"scan", "run", "report", "cache"})
_CACHE_SUBCOMMANDS: tuple[str, ...] = ("stats", "clear")


def check_cli_surface() -> list[str]:
    """CLI 命令面 == `CLI_COMMANDS`，且每个子命令（含 cache 二级）`--help` 可跑。

    为什么这条值得自动化：`--help` 完全不触发业务（入口层把资产 import 延迟到
    命令体内，Day 38 就是为它设计的）⇒ 「命令全可用」可以零成本验完。
    """
    from cli import cli

    problems: list[str] = []
    runner = CliRunner()
    root_res: Result = runner.invoke(cli, ["--help"])
    if root_res.exit_code != 0:
        return [f"[CLI] 顶层 --help 失败（exit={root_res.exit_code}）：{root_res.output[-200:]}"]

    known: set[str] = set(cli.commands)
    # ⚠️ `frozenset - set` 的结果是 **frozenset**，不是 set（pyright 会报
    #    "Type frozenset[str] is not assignable to declared type set[str]"）。
    #    这不是绕不过去的类型洁癖：声明成 set 会诱导调用方去 mutate 它。
    missing: frozenset[str] = CLI_COMMANDS - known
    if missing:
        problems.append(
            f"[CLI] 子命令缺失：{', '.join(sorted(missing))}（现有 {', '.join(sorted(known))}）"
        )

    targets: list[list[str]] = [[name] for name in sorted(known)]
    targets += [["cache", sub] for sub in _CACHE_SUBCOMMANDS]
    for argv in targets:
        res: Result = runner.invoke(cli, [*argv, "--help"])
        if res.exit_code != 0:
            problems.append(f"[CLI] {' '.join(argv)} --help 失败（exit={res.exit_code}）")
    return problems


# ═══════════════════════════════════════════════════════
# A-3：README 引用的东西真的在（截图 + cli 子命令与代码对账）
# ═══════════════════════════════════════════════════════
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
_CLI_CMD_RE = re.compile(r"cli\.py\s+([a-z][a-z0-9_-]*)")


def check_readme_assets() -> list[str]:
    """README 里的本地图片都存在，且出现的 `cli.py <子命令>` 真的存在。

    把「README 完整（含截图）」从**观感问题**变成**可断言契约**：
    截图路径写错（或图删了没改文档）在 Markdown 里只显示一个碎图标，
    本地看文档的人**根本不会注意到** —— 而它在复盘清单里是一条硬要求。
    """
    problems: list[str] = []
    readme: str = read_text(_rel("README.md"))
    for target in _IMAGE_RE.findall(readme):
        if target.startswith(("http://", "https://")):
            continue
        if not _is_file(target):
            problems.append(f"[README] 引用的图片不存在：{target}")
    for sub in sorted(set(_CLI_CMD_RE.findall(readme))):
        if sub not in CLI_COMMANDS:
            problems.append(f"[README] 写的是 `cli.py {sub}`，但 CLI 没有这个子命令")
    return problems


# ═══════════════════════════════════════════════════════
# A-4：入口层 / 工具层「不许有第二份场景清单」
# ═══════════════════════════════════════════════════════
# (相对路径, 必须出现的派生写法, 必须消失的字面量写法)
_SINGLE_SOURCE_MARKERS: tuple[tuple[str, str, str], ...] = (
    ("ui/app.py", "dict(SCENARIO_REGISTRY)", "_SCENARIOS: dict[str, ScenarioConfig] = {"),
    ("tests/test_day37_app.py", "set(SCENARIO_REGISTRY)", 'set(selector.options) == {"login", "register"}'),
)


def _code_lines(text: str) -> str:
    """取「代码行」（丢掉整行注释）再拼回一个文本，供文本检查用。

    为什么必须丢注释：**注释里提到旧写法是合法的** —— 那正是「为什么改」的说明。
    今天实测踩到过一次**假红**：`test_day37_app.py` 的 docstring 里引用了旧断言
    `== {"login", "register"}` 用来解释"以前是写死的"，检查立刻报「还留着第二份清单」。
    假红比假绿更烦：它会让人去删一段**正确的**注释，或者干脆把检查删掉。
    ⇒ 判据要收紧到代码行，且标记要取足上下文（别只写 `== {...}`）。
    """
    kept: list[str] = [ln for ln in text.splitlines() if not ln.lstrip().startswith("#")]
    return "\n".join(kept)


def check_single_source() -> list[str]:
    """三处「第二份场景清单」必须已同源（Day 42 照妖镜照出来的）。

    三处都以「多一份清单」的形态存在，且**都不会报错**：
      · `day41_seam_probe.SCENARIOS` —— 探测少看一个场景 → **假绿**（仍旧报 0 处冲突）
      · `ui/app.py` 的 `_SCENARIOS`   —— CLI 认得新场景、**UI 下拉里没有它**
      · `tests/test_day37_app.py` 的 `== {"login","register"}` —— 加场景必红
        （红得对，但修法应该是「让断言派生」，而不是「每次加场景手改测试」）
    """
    problems: list[str] = []
    from day41_seam_probe import SCENARIOS  # 延迟 import：只在这一条检查里需要

    if SCENARIOS != tuple(SCENARIO_REGISTRY.values()):
        problems.append(
            "[同源] day41_seam_probe.SCENARIOS 与注册表不一致："
            f"{[sc.name for sc in SCENARIOS]} vs {list(SCENARIO_REGISTRY)}"
        )
    for path_rel, must_have, must_not in _SINGLE_SOURCE_MARKERS:
        text: str = read_text(_rel(path_rel))
        if must_have not in text:
            problems.append(f"[同源] {path_rel} 没有派生自注册表（找不到 {must_have!r}）")
        if must_not in _code_lines(text):
            problems.append(f"[同源] {path_rel} 里还留着第二份字面量清单（{must_not!r}）")
    return problems


# ═══════════════════════════════════════════════════════
# B：能力矩阵（信息性 · 不属于"必须全过"）
# ═══════════════════════════════════════════════════════
# (能力, 生产链入口文件, 对应段)
CAPABILITIES: tuple[tuple[str, str, str], ...] = (
    ("需求解析 → 分级用例", "src/agent/day29_requirement_analysis.py", "S1"),
    ("接口测试（计划→套件→执行→报告）", "src/agent/day30_pytest_generator.py", "S3–S8"),
    ("Bug 报告 → 结构化分析", "src/agent/day31_bug_analyzer.py", "S9"),
    ("测试数据生成（边界/异常/SQL/Mock）", "src/agent/day32_run_pipeline.py", "S5"),
    ("对话问答（RAG 知识库）", "src/agent/day21_kb_cli.py", "无 · 仅 archive"),
)


def check_capabilities() -> tuple[list[str], list[str]]:
    """5 类任务能力 → (在册, 缺口)。判据 = **生产链里的入口文件在位**。

    ⚠️ 第 5 类（对话问答）的入口 `src/agent/day21_kb_cli.py` **不在生产链** ——
    真身在 `archive/week3/`。这不是脚本 bug，是**范围事实**：RAG 知识库在第 3 周
    练过，但 Day 34 起的 9 段蓝图里没有它的位置。复盘就该如实标注，
    **别把它算进"能处理的场景"**，那正是母计划这条清单最容易自我安慰的地方。
    """
    present: list[str] = []
    missing: list[str] = []
    for title, entry, stage in CAPABILITIES:
        line: str = f"{title}（{stage}）← {entry}"
        if _is_file(entry):
            present.append(line)
        else:
            missing.append(line)
    return present, missing


# ═══════════════════════════════════════════════════════
# 汇总：复盘报告
# ═══════════════════════════════════════════════════════
def blocking_items() -> list[str]:
    """A 板块的四个检查汇总（空 = 复盘清单的自动化部分全过）。"""
    return (
        check_scenario_contracts()
        + check_cli_surface()
        + check_readme_assets()
        + check_single_source()
    )


def exp1_review_report() -> list[str]:
    """复盘四查 + 能力矩阵 → `outputs/flow/review_report.md`；返回**阻塞项**（空 = 通过）。"""
    print("=" * 72)
    print("exp1_review_report：复盘清单 → 静态可断言（零 API）")
    blocking: list[str] = blocking_items()
    present, missing = check_capabilities()

    lines: list[str] = [
        "# Day 42 复盘报告（由 day42_review_probe.py 自动生成）",
        "",
        "> 三个板块分开看：**A 必须全过**；B 是事实陈述（缺口要如实写进总结）；",
        "> C 是脚本无法判断、只能人工确认的部分。",
        "",
        f"## A. 自动化断言（阻塞项 {len(blocking)} 个）",
        "",
    ]
    lines += ([f"- ❌ {item}" for item in blocking] or ["- ✅ 全部通过"])
    lines += [
        "",
        f"## B. 能力矩阵（在册 {len(present)} / 缺口 {len(missing)}）",
        "",
        "**在册（生产链有入口）**",
        "",
    ]
    lines += ([f"- ✅ {item}" for item in present] or ["- （无）"])
    lines += ["", "**缺口（能力练过但生产链无入口）**", ""]
    lines += ([f"- ⚠️ {item}" for item in missing] or ["- ✅ 无缺口"])
    lines += [
        "",
        "## C. 需人工确认（脚本只打印，不打勾）",
        "",
        "- [ ] 截图是否清楚（`docs/images/*.png` 只保证「文件在」，好不好看只能人看）",
        "- [ ] git 历史是否可读（commit 粒度 / message 说清了「为什么」）",
        "- [ ] 学习总结是否写成（`docs/day42_notes.md` + 可选博客）",
        "- [ ] 缺口是否**写进总结**（附录里「已知局限」一节必须提到 B 板块的缺口）",
        "",
        "> 判据：A 全过 + C 逐条打勾 = 复盘完成。A 有红项时**先修**，C 不该拿来抵消 A。",
    ]
    out_path: str = os.path.join(output_dir("flow"), "review_report.md")
    write_text(out_path, "\n".join(lines))
    print(f"  A 阻塞项：{len(blocking)}　B 缺口：{len(missing)}")
    print(f"  ✅ 复盘报告落盘: {out_path}")
    return blocking


def main() -> None:
    """完成态：落盘复盘报告；有阻塞项则非零退出（复盘门）。"""
    blocking: list[str] = exp1_review_report()
    print("=" * 72)
    if blocking:
        for item in blocking:
            print(f"  ❌ {item}")
        raise SystemExit(f"❌ 复盘未通过：{len(blocking)} 项阻塞（先修，别急着写总结）")
    print("✅ 复盘通过：A 板块四个检查零阻塞项")
    print("💡 要点回顾：")
    print("   清单能不能验收，取决于它能不能被断言 —— 不能断言的条目只能靠人记性")
    print("   遍历注册表，不要点名场景：多一个场景时，点名的那份检查会静默少看一个")
    print("   缺口要如实标注：'练过'不等于'能处理'，复盘最容易在这里自我安慰")


if __name__ == "__main__":
    main()
