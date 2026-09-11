# FILE: test_day37_app.py —— 真实落地到 ai_test_agent/tests/test_day37_app.py
"""Day 37 UI 无头冒烟（streamlit.testing.v1.AppTest）：页面能渲染 + 默认档位为 True。

运行（ai_test_agent 项目根）：
    .venv/Scripts/python.exe -m pytest tests/test_day37_app.py -q
说明：AppTest 会真实执行 app.py 脚本（等价一次 rerun），但不点击「执行」按钮
→ 只触发零 API 的盘点页签，不会调用 run_flow（无 LLM 消耗、无 mock 启动）。
"""
from __future__ import annotations

from pathlib import Path

from streamlit.testing.v1 import AppTest

# ⚠️ AppTest 默认超时仅 3s；本项目 app.py 冷启动要 import
#    day35_scenario → day34_orchestrator → day33 → langchain_google_genai
#    → transformers + torch（实测 ≈31s）→ 必须放宽，否则必然
#    RuntimeError: AppTest script run timed out after 3(s)
_TIMEOUT: float = 120.0


def _app_path() -> str:
    """ui/app.py 的绝对路径（tests/ 的上一级 = 项目根）。"""
    return str(Path(__file__).resolve().parents[1] / "ui" / "app.py")


def _run() -> AppTest:
    """统一入口：带放宽的超时跑一次 app（每个测试各跑一次 = 各一次 rerun）。"""
    return AppTest.from_file(_app_path(), default_timeout=_TIMEOUT).run()


def test_app_renders_without_exception() -> None:
    """页面能完整渲染（盘点页签零 API 路径不抛异常）。"""
    at: AppTest = _run()
    assert not at.exception, f"app 渲染异常: {at.exception}"


def test_default_bug_probe_checkbox_checked() -> None:
    """执行档位复选框默认勾选（True）= 向后兼容契约。"""
    at: AppTest = _run()
    # 按标签查、用 at.sidebar 限定范围（不按下标：下标会随页面结构漂移）
    probe = next(c for c in at.sidebar.checkbox if "S7" in c.label)
    assert probe.value is True, "bug_probe 应默认开启"


def test_scenario_selector_has_login_register() -> None:
    """场景下拉包含 login / register 两个选项。"""
    at: AppTest = _run()
    # ⚠️ 不能用 at.selectbox[0]：元素顺序主区先于 sidebar，
    #    下标 0 实际是「产物浏览」页签的“选择报告”下拉（选项是报告文件名）
    selector = next(sb for sb in at.sidebar.selectbox if sb.label == "被测场景")
    assert set(selector.options) == {"login", "register"}, selector.options
