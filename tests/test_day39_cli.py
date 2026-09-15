# FILE: test_day39_cli.py —— 真实落地到 ai_test_agent/tests/test_day39_cli.py
"""Day 39：CLI 入口层测试（click.testing.CliRunner，零 API、零子进程）。

⚠️ 命名说明：本文件是 Day 38 文档步骤 5.4 `tests/test_day38_cli.py` 的**超集**。
   2026-09-14 15:17 实测：`test_day38_cli.py` **已存在（7 条）**，且 7/7 全被本文件覆盖
   （本文件断言更严：`exit_code == 2` vs 那份的 `!= 0`）→ **请归档那份**（见文档 5.2）。
   不要两份并存：零新增覆盖、纯维护负担，以后改 cli.py 要同时改两处断言且必然漂移。

覆盖范围（全部走「零 API 路径」）：
  --help / scan（含档位联动）/ 参数错误退出码 / report 缺文件 / resolve_stage_ids 归一化。
  **不** invoke 会真跑的 run（除非参数非法、在 run_flow 之前就 raise）——真跑留人工验收。

运行（ai_test_agent 项目根）：
    .venv/Scripts/python.exe -m pytest tests/test_day39_cli.py -q
"""
from __future__ import annotations

import pytest
from click.testing import CliRunner, Result

from cli import cli, resolve_stage_ids


def _invoke(args: list[str]) -> Result:
    """统一入口：进程内调用 CLI（不起子进程、不点执行）。"""
    return CliRunner().invoke(cli, args)


# ═══════════════════════════════════════════════════════
# 解析层：--help / 参数校验（零资产导入）
# ═══════════════════════════════════════════════════════
def test_help_lists_three_commands() -> None:
    """--help 列出三个子命令 scan / run / report。"""
    result: Result = _invoke(["--help"])
    assert result.exit_code == 0, result.output
    for name in ("scan", "run", "report"):
        assert name in result.output, result.output


def test_scan_unknown_scenario_exits_nonzero() -> None:
    """未知场景 → BadParameter（退出码 2 + 消息进 output），不是抛栈。"""
    result: Result = _invoke(["scan", "--scenario", "nope"])
    assert result.exit_code == 2, result.output
    assert "未知场景" in result.output, result.output


def test_report_missing_file_exits_nonzero() -> None:
    """report 指定不存在的报告 → BadParameter（退出码 2）。"""
    result: Result = _invoke(["report", "--name", "no_such_report_xyz.md"])
    assert result.exit_code == 2, result.output
    assert "不存在" in result.output, result.output


# ═══════════════════════════════════════════════════════
# 盘点路径：scan（零 API）
# ═══════════════════════════════════════════════════════
def test_scan_login_default_nine_stages() -> None:
    """scan login：默认档位 9 段（含 S7 对照回路）。"""
    result: Result = _invoke(["scan", "--scenario", "login"])
    assert result.exit_code == 0, result.output
    assert "9 段" in result.output, result.output
    assert "S1_requirement_cases" in result.output, result.output


def test_scan_no_bug_probe_drops_s7() -> None:
    """scan --no-bug-probe：档位关闭 → 8 段、无 S7（CLI 与 UI 档位语义一致）。"""
    result: Result = _invoke(["scan", "--scenario", "login", "--no-bug-probe"])
    assert result.exit_code == 0, result.output
    assert "8 段" in result.output, result.output
    assert "S7_execute_bug" not in result.output, result.output


def test_run_unknown_stage_exits_nonzero() -> None:
    """run --stage S99 → BadParameter（在 run_flow 之前 raise，不会真跑）。"""
    result: Result = _invoke(["run", "--stage", "S99"])
    assert result.exit_code == 2, result.output
    assert "无法唯一确定" in result.output, result.output


# ═══════════════════════════════════════════════════════
# 入口层归一化：resolve_stage_ids（纯函数，参数化）
# ═══════════════════════════════════════════════════════
KNOWN_IDS: set[str] = {"S1_requirement_cases", "S4_test_codegen", "S8_exec_report"}


@pytest.mark.parametrize(
    ("tokens", "expected"),
    [
        ({"S4_test_codegen"}, {"S4_test_codegen"}),                              # 精确命中
        ({"S4"}, {"S4_test_codegen"}),                                           # 唯一前缀
        ({"S4", "S8"}, {"S4_test_codegen", "S8_exec_report"}),                   # 多个唯一前缀
        ({"S1", "S4", "S8"}, KNOWN_IDS),                                         # 全部展开
    ],
)
def test_resolve_stage_ids_happy_path(tokens: set[str], expected: set[str]) -> None:
    """精确 / 唯一前缀 → 归一化为精确 stage_id。"""
    assert resolve_stage_ids(tokens, KNOWN_IDS) == expected


@pytest.mark.parametrize("token", ["S", "S99"])
def test_resolve_stage_ids_rejects_ambiguous_and_unknown(token: str) -> None:
    """歧义（S 命中 3 个）与未知（S99）一律报错——绝不静默猜。"""
    with pytest.raises(Exception, match="无法唯一确定"):
        resolve_stage_ids({token}, KNOWN_IDS)
