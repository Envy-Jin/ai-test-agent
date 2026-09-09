"""
src/agent/case_schema.py —— 测试用例的 Pydantic Schema

用 Pydantic 定义输出结构，配合 Gemini response_schema 实现精确的结构化输出。
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from test_case_model import TestCase as DataclassTestCase  # pyright: ignore[reportMissingImports]


class TestCase(BaseModel):
    """单个测试用例（LLM 输出 Schema）"""

    id: str = Field(min_length=1, description="用例编号，如 TC001")
    title: str = Field(min_length=1, description="用例标题，简明扼要")
    type: Literal["正向", "边界", "异常"] = Field(description="用例类型")
    priority: Literal["P0", "P1", "P2"] = Field(description="优先级，P0最高")
    preconditions: list[str] = Field(default_factory=list, description="前置条件列表")
    steps: list[str] = Field(min_length=1, description="测试步骤列表，至少1步")
    expected: str = Field(min_length=1, description="预期结果")

    def to_dataclass(self) -> DataclassTestCase:
        """转换为 test_case_model.TestCase，便于入库 TestCaseManager。"""
        from test_case_model import TestCase as DataclassTestCase  # pyright: ignore[reportMissingImports]

        return DataclassTestCase(
            id=self.id,
            title=self.title,
            steps=list(self.steps),
            expected_result=self.expected,
            test_type=self.type,
            priority=self.priority,
        )


class TestCaseCollection(BaseModel):
    """测试用例集合（generate 的顶层输出结构）"""

    feature_name: str = Field(min_length=1, description="从需求中提取的功能名称")
    analysis_summary: str | None = Field(
        default=None,
        description="约束识别与边界/异常分析摘要（显式 CoT 输出）",
    )
    test_cases: list[TestCase] = Field(min_length=1, description="测试用例列表，至少1条")

    def to_dataclass_list(self) -> list[DataclassTestCase]:
        """批量转换为 dataclass 用例列表。"""
        return [tc.to_dataclass() for tc in self.test_cases]


class RefineResponse(BaseModel):
    """refine 方法的 LLM 输出结构（仅包含新增用例）"""

    summary: str = Field(min_length=1, description="本次补充说明，简述新增覆盖了哪些场景")
    new_test_cases: list[TestCase] = Field(min_length=1, description="新增用例，不得与已有 id 重复")


_ID_PATTERN = re.compile(r"TC(\d+)", re.IGNORECASE)


def _max_case_number(cases: list[TestCase]) -> int:
    """从用例 id 中提取最大编号，无法解析时返回 0。"""
    numbers = []
    for case in cases:
        match = _ID_PATTERN.search(case.id)
        if match:
            numbers.append(int(match.group(1)))
    return max(numbers) if numbers else 0


def _make_case_id(number: int) -> str:
    return f"TC{number:03d}"


def dedupe_case_ids(existing: list[TestCase], incoming: list[TestCase]) -> list[TestCase]:
    """为与已有 id 冲突的新用例自动重新编号。"""
    used_ids = {case.id for case in existing}
    next_number = _max_case_number(existing) + 1
    result: list[TestCase] = []

    for case in incoming:
        if case.id not in used_ids:
            result.append(case)
            used_ids.add(case.id)
            match = _ID_PATTERN.search(case.id)
            if match:
                next_number = max(next_number, int(match.group(1)) + 1)
            continue

        new_id = _make_case_id(next_number)
        while new_id in used_ids:
            next_number += 1
            new_id = _make_case_id(next_number)
        result.append(case.model_copy(update={"id": new_id}))
        used_ids.add(new_id)
        next_number += 1

    return result


def merge_collections(
    base: TestCaseCollection,
    new_cases: list[TestCase],
    summary: str | None = None,
) -> TestCaseCollection:
    """将 refine 返回的新用例合并进已有集合。"""
    normalized = dedupe_case_ids(base.test_cases, new_cases)
    analysis = base.analysis_summary or ""
    if summary:
        analysis = f"{analysis}\n[补充] {summary}".strip() if analysis else summary

    return TestCaseCollection(
        feature_name=base.feature_name,
        analysis_summary=analysis or None,
        test_cases=[*base.test_cases, *normalized],
    )
