"""测试用例数据管理模块：定义 TestCase 数据类并提供 JSON 持久化能力。"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TestCase:
    """测试用例数据类，用于结构化描述一条测试用例。"""

    id: str
    title: str
    steps: list[str]
    expected_result: str
    test_type: str = "功能"
    priority: str = "P2"
    preconditions: list[str] = field(default_factory=list)
    test_data: dict[str, Any] = field(default_factory=dict)
    actual_result: str | None = None
    passed: bool | None = None


class TestCaseManager:
    """测试用例管理器，支持增删查与 JSON 文件读写。"""

    def __init__(self) -> None:
        """初始化空的测试用例列表。"""
        self._cases: list[TestCase] = []

    @property
    def cases(self) -> list[TestCase]:
        """返回当前所有测试用例（副本列表，避免外部直接修改内部状态）。"""
        return list(self._cases)

    def add_case(self, case: TestCase) -> None:
        """
        添加一条测试用例。

        若已存在相同 id 的用例，则抛出 ValueError。

        Args:
            case: 待添加的 TestCase 实例。

        Raises:
            ValueError: 用例 id 已存在。
        """
        if any(existing.id == case.id for existing in self._cases):
            raise ValueError(f"用例 id 已存在: {case.id}")
        self._cases.append(case)

    def find_by_priority(self, priority: str) -> list[TestCase]:
        """
        按优先级查找测试用例。

        Args:
            priority: 优先级，如 P0、P1、P2。

        Returns:
            匹配该优先级的用例列表；无匹配时返回空列表。
        """
        return [case for case in self._cases if case.priority == priority]

    def find_by_type(self, test_type: str) -> list[TestCase]:
        """
        按测试类型查找测试用例。

        Args:
            test_type: 测试类型，如 功能、边界、异常。

        Returns:
            匹配该类型的用例列表；无匹配时返回空列表。
        """
        return [case for case in self._cases if case.test_type == test_type]

    def save_to_json(self, filepath: str) -> None:
        """
        将当前所有测试用例序列化并写入 JSON 文件。

        Args:
            filepath: 输出 JSON 文件路径。

        Raises:
            OSError: 文件写入失败。
            TypeError: 数据无法序列化为 JSON。
        """
        output_path = Path(filepath)
        data = [asdict(case) for case in self._cases]

        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w", encoding="utf-8") as file:
                json.dump(data, file, ensure_ascii=False, indent=2)
        except TypeError as exc:
            raise TypeError(f"测试用例数据无法序列化为 JSON: {filepath}") from exc
        except OSError as exc:
            raise OSError(f"写入 JSON 文件失败: {filepath}") from exc

    def load_from_json(self, filepath: str) -> None:
        """
        从 JSON 文件加载测试用例并替换当前列表。

        Args:
            filepath: JSON 文件路径。

        Raises:
            FileNotFoundError: 文件不存在。
            json.JSONDecodeError: JSON 格式错误。
            ValueError: JSON 内容不是列表，或用例字段不完整。
            OSError: 文件读取失败。
        """
        input_path = Path(filepath)

        try:
            with input_path.open("r", encoding="utf-8") as file:
                raw_data = json.load(file)
        except FileNotFoundError as exc:
            raise FileNotFoundError(f"JSON 文件不存在: {filepath}") from exc
        except json.JSONDecodeError as exc:
            raise json.JSONDecodeError(
                f"JSON 格式错误: {filepath}",
                exc.doc,
                exc.pos,
            ) from exc
        except OSError as exc:
            raise OSError(f"读取 JSON 文件失败: {filepath}") from exc

        if not isinstance(raw_data, list):
            raise ValueError(f"JSON 根节点必须是列表: {filepath}")

        loaded_cases: list[TestCase] = []
        for index, item in enumerate(raw_data):
            if not isinstance(item, dict):
                raise ValueError(f"第 {index + 1} 条用例不是对象: {filepath}")
            try:
                loaded_cases.append(TestCase(**item))
            except TypeError as exc:
                raise ValueError(f"第 {index + 1} 条用例字段不完整: {filepath}") from exc

        self._cases = loaded_cases


if __name__ == "__main__":
    manager = TestCaseManager()

    manager.add_case(
        TestCase(
            id="TC-001",
            title="用户登录正常流程",
            steps=["打开登录页", "输入手机号和密码", "点击登录"],
            expected_result="成功跳转首页",
            priority="P0",
            test_type="功能",
            preconditions=["用户未登录"],
            test_data={"phone": "13800138000", "password": "Test1234"},
        )
    )
    manager.add_case(
        TestCase(
            id="TC-002",
            title="密码错误时登录失败",
            steps=["输入正确手机号", "输入错误密码", "点击登录"],
            expected_result="提示密码错误，不跳转",
            priority="P1",
            test_type="异常",
        )
    )

    print("=== 按优先级 P0 查找 ===")
    for case in manager.find_by_priority("P0"):
        print(f"  {case.id}: {case.title}")

    print("\n=== 按类型 异常 查找 ===")
    for case in manager.find_by_type("异常"):
        print(f"  {case.id}: {case.title}")

    json_path = "docs/sample_test_cases.json"
    manager.save_to_json(json_path)
    print(f"\n已保存 {len(manager.cases)} 条用例到 {json_path}")

    new_manager = TestCaseManager()
    new_manager.load_from_json(json_path)
    print(f"从 JSON 加载 {len(new_manager.cases)} 条用例:")
    for case in new_manager.cases:
        print(f"  [{case.priority}] {case.id}: {case.title}")