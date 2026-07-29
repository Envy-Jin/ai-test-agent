# 故意有 Bug 的脚本
from test_case_model import TestCase, TestCaseManager

manager = TestCaseManager()
manager.add_case(TestCase(
    id="TC-001",
    title="测试",
    steps=["步骤1"],
    expected_result="预期"
))

# Bug：访问不存在的属性
# print(manager.cases[0].nonexistent_field)