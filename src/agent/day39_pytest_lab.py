# FILE: day39_pytest_lab.py —— 教学 lab（Day 39 步骤 2）
"""Day 39 练习1：pytest 核心机制速成（教学 lab；除 pytest 外零依赖）

为什么单独练 pytest 机制：Day 39 主题是「测试」。CLI/UI 的 CliRunner / AppTest 只是
"测试的形态"；真正决定测试**写得好不好**的，是这六件工具：
  fixture（共享前置）｜parametrize（数据驱动）｜tmp_path（隔离文件系统）
  ｜monkeypatch（替换依赖）｜capsys（捕获输出）｜raises（断言异常）

⚠️ 收集规则（Day 39 实测）：本文件不以 test_ 开头 → 裸 `pytest` **不会**收集它
（它是 lab，不是套件成员）；要跑它必须**显式给路径**——pytest 对命令行显式给出的
文件路径不做 python_files 命名过滤。两种跑法都行：
    pytest src/agent/day39_pytest_lab.py -v
    python -c "from day39_pytest_lab import main; main()"

实验↔步骤↔运行命令：
  exp1_fixture / exp2_parametrize / exp3_tmp_path
  / exp4_monkeypatch / exp5_capsys / exp6_raises   → 步骤 2（六个机制各一条测试）
  main()                                           → 完成态：跑本文件全部测试
  运行：
    python -c "from day39_pytest_lab import main; main()"
"""
from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

if sys.platform == "win32":
    _stdout: Any = sys.stdout  # TextIO 静态类型缺 reconfigure → 经 Any 中转（禁 type: ignore）
    _stdout.reconfigure(encoding="utf-8", errors="replace")

_LAB_ROOT: Path = Path(__file__).resolve().parents[2]  # src/agent → 项目根


# ═══════════════════════════════════════════════════════
# 被测对象：一个"纯函数"（无 IO / 无网络 / 同输入同输出）
# —— 纯函数是单元测试的最佳标的；本 lab 用它演示六个机制
# ═══════════════════════════════════════════════════════
@dataclass(frozen=True)
class MiniStage:
    """迷你蓝图节点（闭包只需要 inputs / outputs 两个字段）。"""

    stage_id: str
    inputs: tuple[str, ...] = ()
    outputs: tuple[str, ...] = ()


MINI_BLUEPRINT: tuple[MiniStage, ...] = (
    MiniStage("S1_req", outputs=("out/req.json",)),
    MiniStage("S3_plan", inputs=("docs/api.md",), outputs=("out/plan.json",)),
    MiniStage("S4_code", inputs=("out/plan.json",), outputs=("out/suite.py",)),
    MiniStage("S8_report", inputs=("out/suite.py", "out/junit.xml"), outputs=("out/rep.md",)),
    MiniStage("S9_bug", inputs=("docs/bugs.md",), outputs=("out/bug.json",)),
)


def select_stages(blueprint: tuple[MiniStage, ...], wanted: set[str]) -> list[str]:
    """迷你闭包：从 wanted 出发沿 outputs→inputs 上溯 producer，返回**原顺序**的 stage_id。"""
    by_id: dict[str, MiniStage] = {s.stage_id: s for s in blueprint}
    by_output: dict[str, MiniStage] = {o: s for s in blueprint for o in s.outputs}
    keep: set[str] = set()
    stack: list[str] = [sid for sid in wanted if sid in by_id]
    while stack:
        sid: str = stack.pop()
        if sid in keep:
            continue
        keep.add(sid)
        for inp in by_id[sid].inputs:
            producer: MiniStage | None = by_output.get(inp)
            if producer is not None:
                stack.append(producer.stage_id)
    return [s.stage_id for s in blueprint if s.stage_id in keep]


def prefix_stage_ids(token: str, known: set[str]) -> set[str]:
    """唯一前缀归一化（演示用）：精确 → 直接用；唯一前缀 → 展开；否则 raise。"""
    if token in known:
        return {token}
    hits: list[str] = sorted(sid for sid in known if sid.startswith(token))
    if len(hits) != 1:
        raise ValueError(f"{token!r} 命中 {len(hits)} 个：{hits}")
    return {hits[0]}


def requirement_doc_exists() -> bool:
    """真实实现：检查需求文档是否在位（依赖文件系统 → 测试里应被 monkeypatch 替换）。"""
    return (_LAB_ROOT / "docs" / "requirements" / "login_requirement.md").is_file()


# ═══════════════════════════════════════════════════════
# 六个机制：一个机制一条测试
# ═══════════════════════════════════════════════════════
# ── 机制 1：fixture —— 共享前置，按参数名注入（不是 import、不是全局变量）──
@pytest.fixture
def mini_blueprint() -> tuple[MiniStage, ...]:
    """共享夹具：本文件多条测试都用它，避免各自复制一份数据。"""
    return MINI_BLUEPRINT


def test_exp1_fixture(mini_blueprint: tuple[MiniStage, ...]) -> None:
    assert len(mini_blueprint) == 5
    ids: list[str] = [s.stage_id for s in mini_blueprint]
    assert ids[0] == "S1_req" and ids[-1] == "S9_bug"


# ── 机制 2：parametrize —— 一份测试逻辑 × N 组数据 ──
@pytest.mark.parametrize(
    ("token", "expected"),
    [
        ("S8_report", {"S8_report"}),  # 精确命中
        ("S8", {"S8_report"}),          # 唯一前缀展开
        ("S9", {"S9_bug"}),             # 唯一前缀展开
    ],
)
def test_exp2_parametrize(token: str, expected: set[str]) -> None:
    """数据驱动：新增用例只需加一行数据，测试逻辑一字不改。"""
    known: set[str] = {s.stage_id for s in MINI_BLUEPRINT}
    assert prefix_stage_ids(token, known) == expected


@pytest.mark.parametrize("token", ["S", "S99"])
def test_exp2b_parametrize_raises(token: str) -> None:
    """同一份数据驱动也能覆盖「非法输入」（歧义 / 不存在）——正反用例同源。"""
    known: set[str] = {s.stage_id for s in MINI_BLUEPRINT}
    with pytest.raises(ValueError):
        prefix_stage_ids(token, known)


# ── 机制 3：tmp_path —— 每个测试一个独立临时目录（隔离文件系统）──
def test_exp3_tmp_path(mini_blueprint: tuple[MiniStage, ...], tmp_path: Path) -> None:
    """tmp_path 是 pytest 给**该测试专属**的临时目录，测试之间互不干扰、自动清理。"""
    blueprint_md: Path = tmp_path / "blueprint.md"
    blueprint_md.write_text(
        "\n".join(f"- {s.stage_id}" for s in mini_blueprint), encoding="utf-8"
    )
    assert blueprint_md.is_file()
    assert "S8_report" in blueprint_md.read_text(encoding="utf-8")
    assert len(blueprint_md.read_text(encoding="utf-8").splitlines()) == 5


# ── 机制 4：monkeypatch —— 替换依赖，让测试不依赖"外部世界状态"──
def test_exp4_monkeypatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """monkeypatch 把文件系统 / 环境变量换成受控替身。

    ⚠️ 为什么目标是 `sys.modules[__name__]` 而**不是**字符串 "day39_pytest_lab.xxx"：
       pytest 因 src/、src/agent 都有 __init__.py，会把本文件导入成
       `src.agent.day39_pytest_lab`，而 `python -c "from day39_pytest_lab import ..."`
       导入的是顶层 `day39_pytest_lab` —— **同一个文件、两个模块对象**。
       字符串目标只会打到其中一个副本上，于是"补丁打了但没生效"（本 lab 实测踩过）。
       用 `sys.modules[__name__]` 拿到"测试函数自己所在的那个模块对象"，与导入名无关。
    """
    assert requirement_doc_exists() is True  # 真实世界：需求文档在位

    this_module = sys.modules[__name__]
    monkeypatch.setattr(this_module, "requirement_doc_exists", lambda: False)
    assert requirement_doc_exists() is False  # 同一调用点，受控替身给出相反答案

    monkeypatch.setenv("DAY39_DEMO", "1")
    assert os.environ["DAY39_DEMO"] == "1"


# ── 机制 5：capsys —— 捕获 stdout/stderr（测试"打印了什么"）──
def test_exp5_capsys(capsys: pytest.CaptureFixture[str]) -> None:
    print(f"闭包结果: {select_stages(MINI_BLUEPRINT, {'S8_report'})}")
    captured = capsys.readouterr()  # 不写注解：类型由 pytest 推断（避免依赖内部类型名）
    assert "S8_report" in captured.out
    assert "S4_code" in captured.out     # 上游被闭包补齐
    assert "S9_bug" not in captured.out  # 旁支不该出现


# ── 机制 6：raises —— 断言"确实抛异常"，且异常类型/消息正确 ──
def test_exp6_raises() -> None:
    with pytest.raises(ValueError, match="命中 5 个"):
        prefix_stage_ids("S", {s.stage_id for s in MINI_BLUEPRINT})


def main() -> None:
    """完成态：用 pytest 跑本文件（显式路径 → 不走 python_files 命名过滤）。"""
    print("=== Day39 练习1：pytest 核心机制（显式路径收集本 lab）===")
    raise SystemExit(pytest.main([__file__, "-v", "--no-header", "-p", "no:cacheprovider"]))


if __name__ == "__main__":
    main()
