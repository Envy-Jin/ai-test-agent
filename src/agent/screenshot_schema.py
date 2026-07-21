"""
src/agent/screenshot_schema.py —— 截图分析的 Pydantic Schema

定义 UI 截图分析的输出结构，配合 response_schema 实现精确结构化输出
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from .test_case_model import TestCase as DataclassTestCase

ElementType = Literal[
    "按钮",
    "输入框",
    "链接",
    "文本",
    "图片",
    "下拉框",
    "复选框",
    "单选框",
    "标签页",
    "图标按钮",
    "开关",
    "弹窗",
    "列表项",
    "其他",
]

ElementState = Literal["正常", "置灰", "选中", "隐藏", "未知"]

TestScope = Literal["UI可测", "需环境模拟"]


class UIElement(BaseModel):
    """识别到的界面元素"""

    element_id: str = Field(min_length=1, description="元素唯一标识，如 EL001")
    element_type: ElementType = Field(description="界面元素的类型")
    label: str = Field(min_length=1, description="元素上显示的文字或标识")
    location: str = Field(
        min_length=1,
        description="元素位置，如'顶部导航栏'、'表单区中部'、'底部协议区'",
    )
    state: ElementState | None = Field(
        default=None,
        description="元素可见状态，如置灰、选中等；无法判断时可省略",
    )


class UITestCase(BaseModel):
    """基于截图生成的 UI 测试用例"""

    id: str = Field(min_length=1, description="用例编号，如 TC001")
    title: str = Field(min_length=1, description="用例标题")
    type: Literal["正向", "边界", "异常", "视觉", "交互"] = Field(description="用例类型")
    priority: Literal["P0", "P1", "P2"] = Field(description="优先级")
    target_element_id: str | None = Field(
        default=None,
        description="对应 elements 中的 element_id",
    )
    target_element: str = Field(min_length=1, description="针对的界面元素名称")
    test_scope: TestScope = Field(
        default="UI可测",
        description="UI可测=仅通过界面操作可验证；需环境模拟=如断网、权限等需额外环境",
    )
    steps: list[str] = Field(min_length=1, description="测试步骤，至少1步")
    expected: str = Field(min_length=1, description="预期结果")

    def to_dataclass(self) -> DataclassTestCase:
        """转换为 test_case_model.TestCase，便于入库 TestCaseManager。"""
        from .test_case_model import TestCase as DataclassTestCase

        return DataclassTestCase(
            id=self.id,
            title=self.title,
            steps=list(self.steps),
            expected_result=self.expected,
            test_type=self.type,
            priority=self.priority,
        )


class ScreenshotAnalysis(BaseModel):
    """截图分析的完整输出结构"""

    page_name: str = Field(min_length=1, description="页面名称，如'登录页'、'注册页'")
    page_description: str = Field(min_length=1, description="页面功能的一句话描述")
    analysis_summary: str | None = Field(
        default=None,
        description="布局结构、交互流程、风险点等分析摘要",
    )
    elements: list[UIElement] = Field(min_length=1, description="识别到的界面元素列表")
    test_cases: list[UITestCase] = Field(min_length=1, description="生成的 UI 测试用例")
    visual_issues: list[str] = Field(
        default_factory=list,
        description="发现的潜在视觉/可用性问题",
    )

    def to_dataclass_list(self) -> list[DataclassTestCase]:
        """批量转换为 dataclass 用例列表。"""
        return [tc.to_dataclass() for tc in self.test_cases]
