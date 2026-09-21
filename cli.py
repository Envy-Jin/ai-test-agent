# FILE: cli.py —— 真实落地到 ai_test_agent/cli.py（Day 38 第 4 层入口层 · CLI）
"""AI 测试全流程 Agent · 命令行入口（薄入口层：只调资产，不写业务）

运行（在 ai_test_agent 项目根）：
    .venv/Scripts/python.exe cli.py --help
    .venv/Scripts/python.exe cli.py scan   --scenario login
    .venv/Scripts/python.exe cli.py run    --scenario login                  # 零 API
    .venv/Scripts/python.exe cli.py run    --scenario login --with-llm       # 真 API
    .venv/Scripts/python.exe cli.py run    --scenario login --stage S4,S8    # 子集（闭包补上游）
    .venv/Scripts/python.exe cli.py report --name exec_report_normal.md

冒烟（无浏览器无 API）：
    .venv/Scripts/python.exe -m pytest tests/test_day39_cli.py -q     # CliRunner 无头

设计纪律（Day 38 步骤 1 决策）：
  - 入口层最薄：命令体只做「参数 → 调 day34/35 资产 → 打印」
  - 资产延迟导入（在命令体内 import）：--help / 参数错误路径零重依赖（冷启动 ≈31s → 亚秒级）
  - 场景注册表单一来源：运行期校验（BadParameter），不在导入期固定 Choice（避免把 day35 拉进顶层）
  - 阶段标识归一化在入口层：支持唯一前缀（S4 → S4_test_codegen），歧义/未知一律报错（绝不静默猜）
"""
from __future__ import annotations

import sys
from pathlib import Path

import click

# ── import 桥（与 ui/app.py 同构）：资产在 src/agent 平铺、彼此裸 import ──
_AGENT_DIR: Path = Path(__file__).resolve().parent / "src" / "agent"
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

_FLOW_REL: str = "outputs/flow"


def _pick_scenario(name: str, *, bug_probe: bool):
    """按名字取场景配置并派生执行档位（延迟导入 day35_scenario）。

    ⚠️ 不写返回注解：ScenarioConfig 在命令体内才导入；留空由 pyright 推断
       （项目规范：构建函数返回注解留空，避免复制契约漂移）。
    
    Day 41：场景注册表改从 `day35_scenario.SCENARIO_REGISTRY` 读（单一来源），
    入口层不再自己维护一份字典 —— 加场景只改资产层一处。
    """
    from day35_scenario import SCENARIO_REGISTRY

    chosen = SCENARIO_REGISTRY.get(name)
    if chosen is None:
        raise click.BadParameter(
            f"未知场景 {name!r}，可选：{', '.join(sorted(SCENARIO_REGISTRY))}"
        )
    return chosen.model_copy(update={"bug_probe": bug_probe})

def resolve_stage_ids(tokens: set[str], known: set[str]) -> set[str]:
    """把用户输入的阶段标识归一化为精确 stage_id（支持唯一前缀：S4 → S4_test_codegen）。

    为什么放在入口层：select_stages 保持"精确 id"的严格契约（库层不做猜谜）；
    用户的自然输入（S4）在入口层归一化，且**必须唯一命中**——歧义或未知直接报错。

    ⚠️ 前缀匹配的代价是模糊性（Day 36 教训：`startswith("S7")` 曾误伤 S7.5 实验段）——
       这里用"唯一性校验"把它关进笼子：命中的候选多于 1 个就报错并列出，绝不静默猜。
    """
    resolved: set[str] = set()
    problems: list[str] = []
    for token in sorted(tokens):
        if token in known:
            resolved.add(token)
            continue
        hits: list[str] = sorted(sid for sid in known if sid.startswith(token))
        if len(hits) == 1:
            resolved.add(hits[0])
        elif hits:
            problems.append(f"{token!r} 歧义（{', '.join(hits)}）")
        else:
            problems.append(f"{token!r} 不存在")
    if problems:
        raise click.BadParameter(
            "阶段标识无法唯一确定：" + "；".join(problems) + f"。可选：{', '.join(sorted(known))}"
        )
    return resolved


@click.group()
def cli() -> None:
    """AI 测试全流程 Agent 命令行（薄入口层：业务委托 day29-35 编排资产）。"""


@cli.command()
@click.option("--scenario", default="login", show_default=True, help="被测场景（login/register）")
@click.option("--no-bug-probe", is_flag=True, help="关闭 S7 变异自验证档位（蓝图 9→8 段）")
def scan(scenario: str, no_bug_probe: bool) -> None:
    """盘点蓝图（零 API）：打印每个阶段的状态与原因 + 场景契约校验。"""
    from day35_scenario import build_blueprint, find_scenario_contract_violations, scan_blueprint

    sc = _pick_scenario(scenario, bug_probe=not no_bug_probe)
    blueprint = build_blueprint(sc)
    rows = scan_blueprint(blueprint)
    click.echo(f"场景 [{sc.name}] {sc.title} · {len(blueprint)} 段 · bug_probe={sc.bug_probe}")
    for spec, status, reason in rows:
        click.echo(f"  [{status:<14}] {spec.stage_id:<22} {reason}")
    counts: dict[str, int] = {}
    for _, status, _ in rows:
        counts[status] = counts.get(status, 0) + 1
    click.echo("汇总: " + "、".join(f"{k}={v}" for k, v in sorted(counts.items())))
    # Day 41：盘点顺手报契约违规 —— 「能不能跑」和「跑得对不对」是两件事
    violations = find_scenario_contract_violations(sc)
    if violations:
        click.echo("契约校验: ✗ 有违规（先修再跑，否则会绿着错）")
        for item in violations:
            click.echo(f"  ✗ {item}")
    else:
        click.echo("契约校验: ✅ 通过（端口同源 / S5 点名本场景 schema / 靶场同源）")


@cli.command(name="run")
@click.option("--scenario", default="login", show_default=True, help="被测场景（login/register）")
@click.option("--no-bug-probe", is_flag=True, help="关闭 S7 变异自验证档位")
@click.option("--with-llm", is_flag=True, help="补跑模型段（真 API；不加则 llm 段 skipped_needs_api）")
@click.option("--force", is_flag=True, help="忽略既有产物，全部重跑")
@click.option("--fail-fast", is_flag=True, help="遇 run_failed 立即中断整链")
@click.option("--stage", "stage_ids", default="", help="只跑指定阶段（逗号分隔，如 S4,S8；支持唯一前缀）；依赖上游自动补齐")
@click.option("--no-cache", is_flag=True, help="关闭 LLM 缓存（量冷启动真实耗时 / 排查结果串味时用）")
def run_cmd(scenario: str, no_bug_probe: bool, with_llm: bool,
            force: bool, fail_fast: bool, stage_ids: str, no_cache: bool) -> None:
    """执行全流程（或 --stage 子集）：code 段本地跑，llm 段需 --with-llm。

    Day 41：llm 段的模型调用默认**带缓存**（同 prompt 第二次不出网）；  
    跑完把 flow_report 落到场景自己的目录（原来命令行跑完什么都不留）。"""
    from day34_orchestrator import persist_flow_report, run_flow
    from day35_scenario import build_blueprint, output_namespace, select_stages

    sc = _pick_scenario(scenario, bug_probe=not no_bug_probe)
    blueprint = build_blueprint(sc)

    if stage_ids.strip():
        tokens: set[str] = {s.strip() for s in stage_ids.split(",") if s.strip()}
        known: set[str] = {spec.stage_id for spec in blueprint}
        wanted: set[str] = resolve_stage_ids(tokens, known)
        blueprint = select_stages(blueprint, wanted)
        click.echo(f"子集执行：{len(blueprint)} 段（已自动补齐依赖上游）")

    flow_report = run_flow(
        blueprint=blueprint, with_llm=with_llm, force=force,
        fail_fast=fail_fast, use_cache=not no_cache,
    )
    json_path, md_path = persist_flow_report(flow_report, output_namespace(sc))
    click.echo(f"\n执行完成 · 开始时间 {flow_report.started_at} · {flow_report.note}")
    for record in flow_report.stages:
        click.echo(f"  {record.stage_id:<22} {record.status:<18} {record.duration_s:>6.2f}s")
    counts: dict[str, int] = {}
    for record in flow_report.stages:
        counts[record.status] = counts.get(record.status, 0) + 1
    click.echo("汇总: " + "、".join(f"{k}={v}" for k, v in sorted(counts.items())))
    click.echo(f"审计记录: {md_path}")


@cli.command()
@click.option("--name", default="flow_report.md", show_default=True, help="outputs/flow 下的报告文件名")
@click.option("--scenario", default="login", show_default=True, help="场景（决定 outputs/flow 下的子目录）")
def report(name: str, scenario: str) -> None:
    """打印 outputs/flow 下的报告（默认 flow_report.md）。"""
    from day35_scenario import SCENARIO_REGISTRY, output_namespace
    from utils import ROOT, read_text

    chosen = SCENARIO_REGISTRY.get(scenario)
    if chosen is None:
        raise click.BadParameter(
            f"未知场景 {scenario!r}，可选：{', '.join(sorted(SCENARIO_REGISTRY))}"
        )
    ns: str = output_namespace(chosen)
    flow_dir: Path = (Path(ROOT) / _FLOW_REL / ns) if ns else (Path(ROOT) / _FLOW_REL)
    target: Path = flow_dir / name
    if not target.is_file():
        available: str = ", ".join(sorted(p.name for p in flow_dir.glob("*.md"))) or "（空）"
        shown: str = f"{_FLOW_REL}/{ns + '/' if ns else ''}{name}"
        raise click.BadParameter(f"{shown} 不存在；可选：{available}")
    click.echo(read_text(str(target)))


@cli.group(name="cache")
def cache_group() -> None:
    """管理 LLM 调用缓存（Day 40：同 prompt 不重复花钱）。"""


@cache_group.command(name="stats")
def cache_stats() -> None:
    """查看缓存现状：条目数 + 数据库大小（零 API）。"""
    from day40_llm_cache import CACHE_PATH, CACHE_REL

    if not CACHE_PATH.is_file():
        click.echo(f"缓存不存在：{CACHE_REL}（首次调用模型后自动创建）")
        return
    cache = _open_cache()
    total: int = cache.count()
    size_kb: float = CACHE_PATH.stat().st_size / 1024
    click.echo(f"缓存文件: {CACHE_REL}")
    click.echo(f"条目数  : {total}")
    click.echo(f"大小    : {size_kb:.1f} KB")


@cache_group.command(name="clear")
@click.confirmation_option(prompt="确定清空 LLM 缓存？")
def cache_clear() -> None:
    """清空缓存（清完下次调用会重新出网）。"""
    cache = _open_cache()
    cache.clear()
    click.echo("✅ 缓存已清空")


def _open_cache():
    """打开缓存实例（延迟导入：cache 子命令之外零代价）。

    ⚠️ 不写返回注解：SQLiteLLMCache 在函数体内导入（与本文件既有风格一致，见
       `_pick_scenario` 的说明——避免为注解把资产提到模块顶层）。
    """
    from day40_llm_cache import SQLiteLLMCache

    return SQLiteLLMCache()


if __name__ == "__main__":
    cli()
