# FILE: day38_click_basics.py
"""Day 38 练习1：Click 基础 + CliRunner 无头测试（教学 demo，除 click 外零依赖）

为什么单独练 Click 基础：Day 38 的 cli.py 是"入口层"，它唯一的框架就是 Click。
先把"装饰器怎么把函数变成命令""怎么在进程内测命令"练熟，再谈业务。

教学点：
  1. @click.group() 是路由容器，@cli.command() 把函数注册成子命令；
     is_flag 是布尔开关（--force），option 带值（--scenario login），argument 是位置参数。
  2. **被装饰后名字绑定的不再是函数**：type(scan).__name__ == "Command"。
     直接 scan() 不会执行你的函数体，而是去解析 sys.argv → 测试必须走 CliRunner。
  3. CliRunner 在**进程内**调用（不起子进程、无浏览器），能断言 exit_code / output / exception
     ——与 Day 37 的 AppTest 是同一类"无头测试"思想。
  4. BadParameter 是"参数非法"的标准出口：exit_code != 0，且 output 里带你的错误消息。

实验↔步骤↔运行命令：
  exp1_help()      → --help 列出子命令（group 路由生效）
  exp2_options()   → option 带值 + is_flag 开关（--no-bug-probe 取反）
  exp3_argument()  → 位置参数 argument（show S4；缺了 click 自动报错）
  exp4_bad_param() → BadParameter 出口 + 验证"名字是 Command 不是函数"
  main()           → 四实验串跑
  运行：
    python -c "from day38_click_basics import main; main()"
"""
from __future__ import annotations

import sys
from typing import Any

import click
from click.testing import CliRunner, Result

if sys.platform == "win32":
    _stdout: Any = sys.stdout  # TextIO 静态类型缺 reconfigure → 经 Any 中转（禁 type: ignore）
    _stdout.reconfigure(encoding="utf-8", errors="replace")  # 防 GBK 崩

SCENARIOS: list[str] = ["login", "register"]


@click.group()
def demo() -> None:
    """Day38 练习1：Click 基础演示（group / command / option / flag / argument）。"""


@demo.command()
@click.option("--scenario", default="login", show_default=True, help="被测场景（login/register）")
@click.option("--no-bug-probe", is_flag=True, help="关闭 S7 变异自验证档位")
def scan(scenario: str, no_bug_probe: bool) -> None:
    """盘点蓝图（demo：只回显收到的参数）。"""
    if scenario not in SCENARIOS:
        raise click.BadParameter(f"未知场景 {scenario!r}，可选：{', '.join(SCENARIOS)}")
    click.echo(f"scenario={scenario} bug_probe={not no_bug_probe}")


@demo.command()
@click.argument("stage_id")
def show(stage_id: str) -> None:
    """演示位置参数：show S4。"""
    click.echo(f"stage_id={stage_id}")


def exp1_help() -> Result:
    """--help：group 路由 + 自动生成帮助页（零业务代码）。"""
    result: Result = CliRunner().invoke(demo, ["--help"])
    assert result.exit_code == 0, result.output
    assert "scan" in result.output and "show" in result.output, result.output
    print(f"[exp1] --help exit={result.exit_code}，子命令 scan/show 已列出")
    return result


def exp2_options() -> None:
    """option 带值 + is_flag 开关：默认 login/True → --scenario register --no-bug-probe → register/False。"""
    default_run: Result = CliRunner().invoke(demo, ["scan"])
    assert default_run.exit_code == 0, default_run.output
    assert "scenario=login bug_probe=True" in default_run.output, default_run.output

    off_run: Result = CliRunner().invoke(demo, ["scan", "--scenario", "register", "--no-bug-probe"])
    assert off_run.exit_code == 0, off_run.output
    assert "scenario=register bug_probe=False" in off_run.output, off_run.output
    print("[exp2] 默认=login/True；--scenario register --no-bug-probe → register/False")


def exp3_argument() -> None:
    """位置参数 argument：show S4（必填，缺了 click 自动报错）。"""
    ok: Result = CliRunner().invoke(demo, ["show", "S4"])
    assert ok.exit_code == 0, ok.output
    assert "stage_id=S4" in ok.output, ok.output

    missing: Result = CliRunner().invoke(demo, ["show"])
    assert missing.exit_code != 0, "缺位置参数应非零退出"
    print(f"[exp3] show S4 → {ok.output.strip()}；缺参数 → exit={missing.exit_code}")


def exp4_bad_param() -> None:
    """BadParameter 出口：参数非法 → 非零退出 + 消息进 output（不是抛栈）。"""
    bad: Result = CliRunner().invoke(demo, ["scan", "--scenario", "nope"])
    assert bad.exit_code != 0, "未知场景应非零退出"
    assert "未知场景" in bad.output, bad.output

    # 教学点 2：被装饰后的名字绑定的是 Command 对象，不是原函数
    kind: str = type(scan).__name__
    assert isinstance(scan, click.Command), kind
    print(f"[exp4] 未知场景 exit={bad.exit_code}（消息含'未知场景'）；type(scan)={kind}（不是函数）")





if __name__ == "__main__":
    """完成态：四实验串跑（全程进程内、零子进程、零 API）。"""
    print("=== Day38 练习1：Click 基础 + CliRunner ===")
    exp1_help()
    exp2_options()
    exp3_argument()
    exp4_bad_param()
    print("=== 全部通过 ===")