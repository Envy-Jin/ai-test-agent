# pytest 执行报告（生成代码）

**场景**: 埋Bug版
**退出码**: 1（0=全部通过，1=有用例失败）

## 执行摘要（由代码解析 pytest 输出）

- 通过: 4
- 失败: 3
- 错误: 0

## 产物

- conftest: `d:\AI\Projects\Cursor\ai_test_agent\src\agent\..\..\outputs\generated_tests\conftest.py`
- 测试代码: `d:\AI\Projects\Cursor\ai_test_agent\src\agent\..\..\outputs\generated_tests\test_api_suite.py`
- 接口测试计划: `d:\AI\Projects\Cursor\ai_test_agent\src\agent\..\..\outputs\api_test_plan_login.md`

## 失败用例（= 生成的代码发现的缺陷）

- `outputs/generated_tests/test_api_suite.py::TestApiLogin::test_invalid_credentials`
- `outputs/generated_tests/test_api_suite.py::TestApiOrders::test_unauthorized`
- `outputs/generated_tests/test_api_suite.py::TestApiOrders::test_unauthorized`

## pytest 输出尾部

```
atus_code == 401, f"���� 401 ʵ�� {resp.status_code}: {resp.text[:200]}"
E   AssertionError: ���� 401 ʵ�� 200: {"code": 0, "data": {"orders": []}}
E   assert 200 == 401
E    +  where 200 = <Response [200]>.status_code
=========================== short test summary info ===========================
FAILED outputs/generated_tests/test_api_suite.py::TestApiLogin::test_invalid_credentials
FAILED outputs/generated_tests/test_api_suite.py::TestApiOrders::test_unauthorized[headers0]
FAILED outputs/generated_tests/test_api_suite.py::TestApiOrders::test_unauthorized[headers1]
3 failed, 4 passed in 1.11s

```
