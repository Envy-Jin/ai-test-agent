"""测试用例预生成模块：根据需求解析结果为约束条件自动生成边界值测试用例框架。"""

from __future__ import annotations

import re
from typing import Any

from agent.requirement_parser import Feature, ParsedRequirement
from agent.test_case_model import TestCase


def _extract_numbers(constraint: str) -> list[int]:
    """
    从约束描述中提取所有数字。

    Args:
        constraint: 约束条件文本。

    Returns:
        按出现顺序排列的整数列表。
    """
    pattern = r"(?<!\d)-?\d+"
    return [int(num) for num in re.findall(pattern, constraint)]


def _extract_range(constraint: str) -> tuple[int, int] | None:
    """
    从约束描述中提取数值区间 [下限, 上限]。

    支持格式如 ``1-150``、``3到20``、``3-20个字符`` 及含「之间」的区间描述。

    Args:
        constraint: 约束条件文本。

    Returns:
        若识别到合法区间则返回 (下限, 上限)，否则返回 None。
    """
    hyphen_match = re.search(r"(\d+)\s*[-~—]\s*(\d+)", constraint)
    if hyphen_match:
        low, high = int(hyphen_match.group(1)), int(hyphen_match.group(2))
        if low <= high:
            return low, high

    to_match = re.search(r"(\d+)\s*到\s*(\d+)", constraint)
    if to_match:
        low, high = int(to_match.group(1)), int(to_match.group(2))
        if low <= high:
            return low, high

    numbers = _extract_numbers(constraint)
    if len(numbers) >= 2 and "之间" in constraint:
        low, high = numbers[0], numbers[1]
        if low <= high:
            return low, high

    return None


def _classify_constraint(constraint: str) -> str:
    """
    判断约束类型，用于选择边界值生成策略。

    Returns:
        约束类型：``range``、``min``、``max``、``exceed`` 或 ``generic``。
    """
    if _extract_range(constraint) is not None:
        return "range"
    if any(keyword in constraint for keyword in ("不少于", "至少")):
        return "min"
    if any(keyword in constraint for keyword in ("不超过", "最多")):
        return "max"
    if "超过" in constraint:
        return "exceed"
    return "generic"


def _build_range_boundary_specs(low: int, high: int) -> list[dict[str, Any]]:
    """
    为闭区间 [low, high] 生成上下限边界测试规格。

    例如 1-150 生成 0、1、2、149、150、151。
    """
    candidates: list[tuple[int, str, str] | None] = [
        (max(low - 1, 0), "低于下限", "不符合要求，应被拒绝"),
        (low, "下限边界值", "符合要求，应被接受"),
        (low + 1, "略高于下限", "符合要求，应被接受") if low + 1 < high else None,
        (high - 1, "略低于上限", "符合要求，应被接受") if high - 1 > low else None,
        (high, "上限边界值", "符合要求，应被接受"),
        (high + 1, "高于上限", "不符合要求，应被拒绝"),
    ]

    specs: list[dict[str, Any]] = []
    seen_values: set[int] = set()
    for item in candidates:
        if item is None:
            continue
        value, label, expected = item
        if value in seen_values:
            continue
        seen_values.add(value)
        specs.append(
            {
                "value": value,
                "label": label,
                "expected_result": expected,
            }
        )
    return specs


def _build_boundary_specs(constraint: str) -> list[dict[str, Any]]:
    """
    根据约束描述构造边界值测试规格列表。

    例如「不少于8位」生成 7、8、9 三组边界数据。

    Args:
        constraint: 单条约束条件文本。

    Returns:
        边界规格字典列表，每项包含 ``value``、``label``、``expected_result``。
    """
    numbers = _extract_numbers(constraint)
    if not numbers:
        return [
            {
                "value": None,
                "label": "正向验证",
                "expected_result": f"满足约束「{constraint}」时应被系统接受",
            },
            {
                "value": None,
                "label": "反向验证",
                "expected_result": f"违反约束「{constraint}」时应被系统拒绝或提示错误",
            },
        ]

    constraint_type = _classify_constraint(constraint)

    if constraint_type == "range":
        value_range = _extract_range(constraint)
        if value_range is not None:
            return _build_range_boundary_specs(value_range[0], value_range[1])

    base_value = numbers[0]

    if constraint_type == "min":
        candidates = [
            (max(base_value - 1, 0), "低于下限", "不符合要求，应被拒绝"),
            (base_value, "边界值", "符合要求，应被接受"),
            (base_value + 1, "高于下限", "符合要求，应被接受"),
        ]
    elif constraint_type == "max":
        candidates = [
            (max(base_value - 1, 0), "低于上限", "符合要求，应被接受"),
            (base_value, "边界值", "符合要求，应被接受"),
            (base_value + 1, "高于上限", "不符合要求，应被拒绝"),
        ]
    elif constraint_type == "exceed":
        candidates = [
            (max(base_value - 1, 0), "未达触发阈值", "不应触发限制"),
            (base_value, "临界值", "处于临界状态，按规则判断是否触发"),
            (base_value + 1, "超过阈值", "应触发限制（如锁定、拒绝等）"),
        ]
    else:
        candidates = [
            (max(base_value - 1, 0), "边界下侧", "验证系统对低于边界值输入的处理"),
            (base_value, "边界值", "验证系统对边界值输入的处理"),
            (base_value + 1, "边界上侧", "验证系统对高于边界值输入的处理"),
        ]

    return [
        {
            "value": value,
            "label": label,
            "expected_result": expected,
        }
        for value, label, expected in candidates
    ]


def generate_boundary_cases(feature: Feature) -> list[TestCase]:
    """
    为单个功能模块的每条约束条件生成边界值测试用例框架。

    使用正则从约束文本中提取数字，并依据「不少于」「不超过」「超过」等
    关键词构造边界值组合（如 7、8、9）。

    Args:
        feature: 已解析的功能模块对象。

    Returns:
        该功能下所有约束对应的 TestCase 列表。
    """
    cases: list[TestCase] = []
    case_index = 1

    for constraint in feature.constraints:
        boundary_specs = _build_boundary_specs(constraint)

        for spec in boundary_specs:
            value = spec["value"]
            label = spec["label"]
            value_text = "N/A" if value is None else str(value)

            cases.append(
                TestCase(
                    id=f"TC-{case_index:03d}",
                    title=(
                        f"{feature.feature}-{label}："
                        f"{constraint[:30]}{'...' if len(constraint) > 30 else ''}"
                    ),
                    steps=[
                        f"准备测试数据，边界值 = {value_text}",
                        f"针对约束「{constraint}」构造输入并执行相关操作",
                        "记录系统实际响应并与预期结果对比",
                    ],
                    expected_result=spec["expected_result"],
                    test_type="边界",
                    priority="P1",
                    preconditions=[f"功能模块：{feature.feature}"],
                    test_data={
                        "feature": feature.feature,
                        "constraint": constraint,
                        "boundary_value": value,
                        "boundary_label": label,
                    },
                )
            )
            case_index += 1

    return cases


def generate_from_parsed_requirement(
    parsed: ParsedRequirement,
) -> dict[str, list[TestCase]]:
    """
    为完整需求解析结果中的所有功能模块生成测试用例。

    Args:
        parsed: 需求文档解析结果对象。

    Returns:
        以功能名称为 key、对应用例列表为 value 的字典。
        无约束条件的功能对应空列表。
    """
    result: dict[str, list[TestCase]] = {}

    for feature in parsed.features:
        result[feature.feature] = generate_boundary_cases(feature)

    return result
