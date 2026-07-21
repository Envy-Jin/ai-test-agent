"""screenshot_schema 单元测试（不调用 Gemini API）"""

import pytest
from pydantic import ValidationError

from agent.screenshot_schema import (
    ScreenshotAnalysis,
    UIElement,
    UITestCase as SchemaUITestCase,
)
from agent.test_case_model import TestCaseManager


def _sample_element(element_id: str = "EL001") -> UIElement:
    return UIElement(
        element_id=element_id,
        element_type="按钮",
        label="登录",
        location="表单区下部",
        state="置灰",
    )


def _sample_ui_case(case_id: str = "TC001") -> SchemaUITestCase:
    return SchemaUITestCase(
        id=case_id,
        title="空手机号提交",
        type="边界",
        priority="P1",
        target_element_id="EL001",
        target_element="手机号",
        test_scope="UI可测",
        steps=["不输入手机号", "点击登录"],
        expected="提示不能为空",
    )


def test_ui_test_case_to_dataclass():
    dc = _sample_ui_case().to_dataclass()
    assert dc.expected_result == "提示不能为空"
    assert dc.test_type == "边界"


def test_screenshot_analysis_requires_elements_and_cases():
    with pytest.raises(ValidationError):
        ScreenshotAnalysis(
            page_name="登录页",
            page_description="测试",
            elements=[],
            test_cases=[_sample_ui_case()],
        )


def test_test_scope_literal():
    case = _sample_ui_case().model_copy(update={"test_scope": "需环境模拟"})
    assert case.test_scope == "需环境模拟"


def test_collection_to_manager():
    analysis = ScreenshotAnalysis(
        page_name="登录页",
        page_description="手机号登录",
        analysis_summary="中部表单区",
        elements=[_sample_element()],
        test_cases=[_sample_ui_case()],
        visual_issues=["间距不均"],
    )
    manager = TestCaseManager()
    for case in analysis.to_dataclass_list():
        manager.add_case(case)
    assert len(manager.cases) == 1
