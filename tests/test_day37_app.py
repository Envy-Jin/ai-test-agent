# FILE: test_day37_app.py —— 真实落地到 ai_test_agent/tests/test_day37_app.py
"""Day 37 UI 无头冒烟（streamlit.testing.v1.AppTest）：页面能渲染 + 默认档位为 True。

运行（ai_test_agent 项目根）：
    .venv/Scripts/python.exe -m pytest tests/test_day37_app.py -q
说明：AppTest 会真实执行 app.py 脚本（等价一次 rerun），但不点击「执行」按钮
→ 只触发零 API 的盘点页签，不会调用 run_flow（无 LLM 消耗、无 mock 启动）。

Day 39 改动：从「每条测试各跑一次」改成「整模块共跑一次」（module 级 fixture）——
AppTest 冷启动（streamlit + app.py 的导入链）从 3 次降到 1 次，裸 pytest 总耗时明显下降。
"""
from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

# ⚠️ AppTest 默认超时仅 3s；本项目 app.py 冷启动要 import streamlit + 资产链
#    → 必须放宽，否则必然 RuntimeError: AppTest script run timed out after 3(s)
_TIMEOUT: float = 120.0


def _app_path() -> str:
    """ui/app.py 的绝对路径（tests/ 的上一级 = 项目根）。"""
    return str(Path(__file__).resolve().parents[1] / "ui" / "app.py")


def _run() -> AppTest:
    """统一入口：带放宽的超时跑一次 app。"""
    return AppTest.from_file(_app_path(), default_timeout=_TIMEOUT).run()


@pytest.fixture(scope="module")
def app_test() -> Iterator[AppTest]:
    """整模块共跑一次（Day 39）：三条断言复用同一次渲染结果，冷启动只付一次。"""
    yield _run()


def test_app_renders_without_exception(app_test: AppTest) -> None:
    """页面能完整渲染（盘点页签零 API 路径不抛异常）。"""
    assert not app_test.exception, f"app 渲染异常: {app_test.exception}"


def test_default_bug_probe_checkbox_checked(app_test: AppTest) -> None:
    """执行档位复选框默认勾选（True）= 向后兼容契约。"""
    # 按标签查、用 sidebar 限定范围（不按下标：下标会随页面结构漂移）
    probe = next(c for c in app_test.sidebar.checkbox if "S7" in c.label)
    assert probe.value is True, "bug_probe 应默认开启"


def test_scenario_selector_matches_registry(app_test: AppTest) -> None:
    """场景下拉 == **资产层注册表**里的全部场景（Day 42：不再写死清单）。

    ⚠️ 原来这里断言的是 `== {"login", "register"}` —— 那是**第二份写死的场景清单**：
    加第三个场景时它会红（红得对，但它守的是「测试记得改」，而不是「UI 真的同源」）。
    改为从 `SCENARIO_REGISTRY` 派生后，再加场景**不需要**动这个文件。
    """
    from day35_scenario import SCENARIO_REGISTRY

    # ⚠️ 不能用 at.selectbox[0]：元素顺序主区先于 sidebar，
    #    下标 0 实际是「产物浏览」页签的“选择报告”下拉（选项是报告文件名）
    selector = next(sb for sb in app_test.sidebar.selectbox if sb.label == "被测场景")
    assert set(selector.options) == set(SCENARIO_REGISTRY), selector.options