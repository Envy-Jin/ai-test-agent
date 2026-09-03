# 回归测试报告：变更后（重构缺陷模拟）

**日期**: 2026-09-03 16:19
**执行人**: AI Agent（mock 靶场）
**变更文件**: src/agent/auth_common.py, src/agent/day30_mock_api.py
**变更摘要**: 将分散的鉴权与 token 签发逻辑收口至 auth_common.py，并将固定 token 改为按手机号后四位动态派生。
**回归范围**: 必回归 ['TC001', 'TC003', 'TC004', 'TC005'] / 建议 [] / 跳过 ['TC002']

## 执行摘要
- 用例总数: 5
- 通过: 2
- 失败: 3
- 跳过: 0
- 错误: 0
- 通过率: 40.0%

## 详细结果
| 状态 | 用例 | 模块 | 耗时(s) | 说明 |
|------|------|------|---------|------|
| passed | test_normal | login | 0.011 |  |
| failed | test_invalid_credentials | login | 0.035 | AssertionError: 期望 401 实际 500: {"code": 50000, "message": "服务端内部异常（错误凭据未捕获）"}
as |
| passed | test_normal | orders | 0.004 |  |
| failed | test_unauthorized[headers0] | orders | 0.005 | AssertionError: 期望 401 实际 200: {"code": 0, "data": {"orders": []}}
assert 200 == |
| failed | test_unauthorized[headers1] | orders | 0.005 | AssertionError: 期望 401 实际 200: {"code": 0, "data": {"orders": []}}
assert 200 == |

## 缺陷列表（疑似回归缺陷）
1. **TC003 错误凭据登录被拒（401）** —— AssertionError: 期望 401 实际 500: {"code": 50000, "message": "服务端内部异常（错误凭据未捕获）"}
assert 500 == 401
 +  where 500 = <Respons
2. **TC005 无/错 token 访问订单被拒（越权）** —— AssertionError: 期望 401 实际 200: {"code": 0, "data": {"orders": []}}
assert 200 == 401
 +  where 200 = <Response [200]>.st
3. **TC005 无/错 token 访问订单被拒（越权）** —— AssertionError: 期望 401 实际 200: {"code": 0, "data": {"orders": []}}
assert 200 == 401
 +  where 200 = <Response [200]>.st

## 测试结论
检出 3 个疑似回归缺陷：TC003(错误凭据登录被拒（401）), TC005(无/错 token 访问订单被拒（越权）), TC005(无/错 token 访问订单被拒（越权）)。这些用例在变更前基线是通过的——本次变更极可能引入了回归，建议修复后重跑 affected 范围（Day 31 Bug 分析流程可接续分析）再上线。