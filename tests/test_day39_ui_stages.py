# FILE: test_day39_ui_stages.py —— 真实落地到 ai_test_agent/tests/test_day39_ui_stages.py
"""Day 39 步骤 5.13：UI「只跑指定阶段」的无头测试（Streamlit AppTest）。

为什么单开一个文件：`test_day37_app.py` 测的是「页面能渲染 + 默认档位」，
本文件测的是「选段 → 闭包 → 预览文案」。标的物不同，分开好定位。
两边都用 AppTest 且**都不点「执行」按钮** → 零 API、不起 mock。

运行（ai_test_agent 项目根）：
    .venv/Scripts/python.exe -m pytest tests/test_day39_ui_stages.py -q

⚠️ 本文件**不用** module 级共享夹具（`test_day37_app.py` 用了）：
   选段类断言要把实例推到"选中之后"的状态，共享一个实例会互相污染，
   所以每条测试自己 `_run()` 一次。代价是多付 4 次 AppTest 冷启动（约 4×1.7s）。
"""
from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

_TIMEOUT: float = 120.0  # 同 test_day37_app：AppTest 默认 3s 必然不够
_LABEL: str = "只跑指定阶段（留空 = 全流程）"


def _app_path() -> str:
    """ui/app.py 的绝对路径（tests/ 的上一级 = 项目根）。"""
    return str(Path(__file__).resolve().parents[1] / "ui" / "app.py")


def _run() -> AppTest:
    """统一入口：带放宽的超时跑一次 app。"""
    return AppTest.from_file(_app_path(), default_timeout=_TIMEOUT).run()


def _stage_box(at: AppTest):
    """按 label 取阶段多选框（不按下标：下标会随页面结构漂移）。"""
    return next(m for m in at.multiselect if m.label == _LABEL)


def _probe_box(at: AppTest):
    """按 label 取 S7 档位复选框（sidebar 限定范围）。"""
    return next(c for c in at.sidebar.checkbox if "S7" in c.label)


def _captions(at: AppTest) -> str:
    """把所有 st.caption 拼成一个串，便于 `in` 断言。"""
    return " | ".join(c.value for c in at.caption)


def test_options_are_exact_stage_ids_with_title() -> None:
    """选项 = 9 个精确 stage_id（前面是 id，后面跟标题）—— 不是前缀、不是序号。

    ⚠️ 这条守的是"UI 不做前缀猜谜"的契约：选项必须来自蓝图的 stage_id 本身。
    """
    at = _run()
    assert not at.exception, f"app 渲染异常: {at.exception}"
    options: list[str] = list(_stage_box(at).options)
    assert len(options) == 9, options
    prefixes: list[str] = [o.split(" · ")[0] for o in options]
    assert len(set(prefixes)) == 9, f"stage_id 有重复: {prefixes}"
    assert prefixes[0] == "S1_requirement_cases", prefixes[0]
    assert "S8_exec_report" in prefixes, prefixes


def test_empty_selection_means_full_flow() -> None:
    """留空 = 全流程（与 CLI 不带 --stage 同语义）→ 明确写出段数，别让人猜。"""
    at = _run()
    assert _stage_box(at).value == []
    assert "全流程：9 段" in _captions(at)


def test_select_s8_pulls_upstream_closure() -> None:
    """只选 S8 → 资产层闭包补出 5 段，且被补的 4 段逐个点名（可见即可信）。"""
    at = _run()
    _stage_box(at).select("S8_exec_report").run()
    assert _stage_box(at).value == ["S8_exec_report"], "控件的值应是精确 id，不是格式化后的显示文案"
    info: str = " | ".join(i.value for i in at.info)
    assert "子集执行：5 段" in info, info
    assert "自动补齐上游 4 段" in info, info
    for upstream in ("S3_api_plan", "S4_test_codegen", "S6_execute_normal", "S7_execute_bug"):
        assert upstream in info, f"{upstream} 未被点名: {info}"


def test_turning_off_bug_probe_resets_selection() -> None:
    """开关档位 → 多选自动清空（key 编入档位），不会留下"已不存在的 S7 选择"。

    为什么必须测：关档位的蓝图只有 8 段（没有 S7），若选择残留为 {'S7_execute_bug'}，
    `select_stages` 会返回**空列表**（不是报错），于是"点执行 = 一段都不跑"。
    """
    at = _run()
    _stage_box(at).select("S8_exec_report")
    at.run()
    _probe_box(at).set_value(False)
    at.run()
    assert _stage_box(at).value == [], "换档位后选择应被清空（widget key 变了 → 状态重置）"
    assert "全流程：8 段" in _captions(at)
    assert not at.exception, f"app 渲染异常: {at.exception}"


