# FILE: test_day38_cli.py —— 真实落地到 ai_test_agent/tests/test_day38_cli.py
"""Day 38 CLI 无头冒烟（click.testing.CliRunner）：参数解析 + 盘点路径零 API。

运行（ai_test_agent 项目根）：
    .venv/Scripts/python.exe -m pytest tests/test_day38_cli.py -q

说明：CliRunner 在**进程内**执行命令（不起子进程、不点执行按钮）。
      本文件只覆盖 scan / 参数解析 / select_stages（零 API、零执行），
      不 invoke 会真跑的 run（mock+pytest）——真跑留步骤 5.5 人工验收 + Day 39 行为测试。
"""
from __future__ import annotations

import sys
from pathlib import Path

import click
import pytest
from click.testing import CliRunner, Result

# 根目录 cli.py 需要项目根在 sys.path（显式优于隐式，同 ui/app.py 的桥接思路）
_ROOT: Path = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from cli import cli  # noqa: E402  # 根目录 cli.py


def _invoke(args: list[str]) -> Result:
    """统一入口：进程内调用 CLI。"""
    return CliRunner().invoke(cli, args)


def test_help_lists_three_commands() -> None:
    """--help 列出三个子命令（零资产导入）。"""
    result: Result = _invoke(["--help"])
    assert result.exit_code == 0, result.output
    for name in ("scan", "run", "report"):
        assert name in result.output, result.output


def test_scan_login_nine_stages() -> None:
    """scan login：默认档位 9 段（含 S7）。"""
    result: Result = _invoke(["scan", "--scenario", "login"])
    assert result.exit_code == 0, result.output
    assert "S1_requirement_cases" in result.output, result.output
    assert "9 段" in result.output, result.output


def test_scan_no_bug_probe_drops_s7() -> None:
    """scan --no-bug-probe：档位关闭 → 8 段、无 S7（Day37 档位在 CLI 侧同样生效）。"""
    result: Result = _invoke(["scan", "--scenario", "login", "--no-bug-probe"])
    assert result.exit_code == 0, result.output
    assert "S7_execute_bug" not in result.output, result.output
    assert "8 段" in result.output, result.output


def test_scan_unknown_scenario_exits_nonzero() -> None:
    """未知场景 → BadParameter（非零退出 + 消息），不是抛栈。"""
    result: Result = _invoke(["scan", "--scenario", "nope"])
    assert result.exit_code != 0
    assert "未知场景" in result.output, result.output


def test_run_unknown_stage_exits_nonzero() -> None:
    """run --stage S99 → BadParameter（在 run_flow 之前 raise，不会真跑）。"""
    result: Result = _invoke(["run", "--stage", "S99"])
    assert result.exit_code != 0
    assert "无法唯一确定" in result.output, result.output


def test_resolve_stage_ids_exact_prefix_ambiguity() -> None:
    """阶段标识归一化：精确 / 唯一前缀 / 歧义报错 / 未知报错（入口层，纯函数）。"""
    from cli import resolve_stage_ids

    known: set[str] = {"S1_requirement_cases", "S4_test_codegen", "S8_exec_report"}
    assert resolve_stage_ids({"S4_test_codegen"}, known) == {"S4_test_codegen"}
    assert resolve_stage_ids({"S4"}, known) == {"S4_test_codegen"}
    assert resolve_stage_ids({"S4", "S8"}, known) == {"S4_test_codegen", "S8_exec_report"}
    with pytest.raises(click.BadParameter):
        resolve_stage_ids({"S"}, known)       # 歧义：S1 / S4 / S8 都命中
    with pytest.raises(click.BadParameter):
        resolve_stage_ids({"S99"}, known)     # 未知


def test_select_stages_closure_includes_upstream() -> None:
    """select_stages 闭包：S8 自动带上 S3/S4/S6/S7，且保持原蓝图顺序。"""
    from day35_scenario import LOGIN_SCENARIO, build_blueprint, select_stages

    blueprint = build_blueprint(LOGIN_SCENARIO)
    subset = select_stages(blueprint, {"S8_exec_report"})
    ids: list[str] = [spec.stage_id for spec in subset]
    assert ids == ["S3_api_plan", "S4_test_codegen", "S6_execute_normal",
                   "S7_execute_bug", "S8_exec_report"], ids
