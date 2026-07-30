"""测试数据生成模块：根据字段定义批量生成随机测试数据。"""

from __future__ import annotations

import random
import string
from typing import Any


class TestDataGenerator:
    """测试数据生成器，支持生成常见类型的随机字段值及批量数据。"""

    _EMAIL_DOMAINS: tuple[str, ...] = (
        "example.com",
        "test.com",
        "mail.cn",
        "demo.org",
    )

    def generate_string(self, max_length: int = 50) -> str:
        """
        生成随机字符串。

        Args:
            max_length: 字符串最大长度，实际长度在 1~max_length 之间随机。

        Returns:
            由大小写字母和数字组成的随机字符串。

        Raises:
            ValueError: max_length 小于 1。
        """
        if max_length < 1:
            raise ValueError("max_length 必须大于等于 1")

        length = random.randint(1, max_length)
        chars = string.ascii_letters + string.digits
        return "".join(random.choices(chars, k=length))

    def generate_email(self) -> str:
        """
        生成随机邮箱地址。

        Returns:
            格式为 ``local@domain`` 的邮箱字符串，如 ``user123@example.com``。
        """
        local_part = self.generate_string(max_length=random.randint(5, 12)).lower()
        domain = random.choice(self._EMAIL_DOMAINS)
        return f"{local_part}@{domain}"

    def generate_phone(self) -> str:
        """
        生成随机中国大陆手机号。

        Returns:
            11 位手机号字符串，首位为 1，第二位为 3~9。
        """
        second_digit = random.choice("3456789")
        remaining = "".join(random.choices(string.digits, k=9))
        return f"1{second_digit}{remaining}"

    def generate_number(self, min_val: int = 0, max_val: int = 100) -> int:
        """
        生成指定范围内的随机整数。

        Args:
            min_val: 最小值（含）。
            max_val: 最大值（含）。

        Returns:
            [min_val, max_val] 区间内的随机整数。

        Raises:
            ValueError: min_val 大于 max_val。
        """
        if min_val > max_val:
            raise ValueError("min_val 不能大于 max_val")
        return random.randint(min_val, max_val)

    def _generate_field_value(self, field_name: str, definition: dict[str, Any]) -> Any:
        """
        根据单个字段定义生成对应类型的值。

        Args:
            field_name: 字段名称，用于错误提示。
            definition: 字段定义字典，需包含 ``type`` 键。

        Returns:
            生成的字段值。

        Raises:
            ValueError: 字段定义无效或类型不支持。
        """
        if not isinstance(definition, dict):
            raise ValueError(f"字段 {field_name} 的定义必须是字典")

        field_type = definition.get("type")
        if not field_type:
            raise ValueError(f"字段 {field_name} 缺少 type 定义")

        if field_type == "string":
            max_length = definition.get("max_length", 50)
            if not isinstance(max_length, int):
                raise ValueError(f"字段 {field_name} 的 max_length 必须是整数")
            return self.generate_string(max_length=max_length)

        if field_type == "email":
            return self.generate_email()

        if field_type == "phone":
            return self.generate_phone()

        if field_type == "number":
            min_val = definition.get("min_val", 0)
            max_val = definition.get("max_val", 100)
            if not isinstance(min_val, int) or not isinstance(max_val, int):
                raise ValueError(f"字段 {field_name} 的 min_val/max_val 必须是整数")
            return self.generate_number(min_val=min_val, max_val=max_val)

        raise ValueError(f"字段 {field_name} 使用了不支持的类型: {field_type}")

    def generate_batch(
        self,
        field_definitions: dict[str, dict[str, Any]],
        count: int,
    ) -> list[dict[str, Any]]:
        """
        根据字段定义批量生成测试数据。

        Args:
            field_definitions: 字段定义字典。key 为字段名，value 为类型配置，例如::

                {
                    "username": {"type": "string", "max_length": 20},
                    "email": {"type": "email"},
                    "phone": {"type": "phone"},
                    "age": {"type": "number", "min_val": 18, "max_val": 60},
                }

                支持的 type: ``string``、``email``、``phone``、``number``。

            count: 生成记录条数，必须大于 0。

        Returns:
            由字典组成的列表，每条字典对应一组生成的测试数据。

        Raises:
            ValueError: count 小于 1，或 field_definitions 为空/无效。
        """
        if count < 1:
            raise ValueError("count 必须大于等于 1")
        if not field_definitions:
            raise ValueError("field_definitions 不能为空")

        batch: list[dict[str, Any]] = []
        for _ in range(count):
            record = {
                field_name: self._generate_field_value(field_name, definition)
                for field_name, definition in field_definitions.items()
            }
            batch.append(record)
        return batch
