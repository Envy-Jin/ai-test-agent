# 全流程执行报告：login · 埋 Bug 版（对照）

**日期**: 2026-09-20 21:43
**执行**: mock 靶场 + 生成套件（7 个 pytest node）

## 执行摘要
- 用例总数: 7
- 通过: 4
- 失败: 3
- 跳过: 0
- 错误: 0
- 通过率: 57.1%

## 详细结果
| 状态 | 用例 | 模块 | 耗时(s) | 说明 |
|------|------|------|---------|------|
| passed | test_normal | login | 0.009 |  |
| passed | test_missing_params[payload0] | login | 0.018 |  |
| passed | test_missing_params[payload1] | login | 0.016 |  |
| failed | test_invalid_credentials | login | 0.058 | AssertionError: 期望 401 实际 500: {"code": 50000, "message": "服务端内部异常（错误凭据未捕获）"}
as |
| passed | test_normal | orders | 0.021 |  |
| failed | test_unauthorized[headers0] | orders | 0.004 | AssertionError: 期望 401 实际 200: {"code": 0, "data": {"orders": []}}
assert 200 == |
| failed | test_unauthorized[headers1] | orders | 0.004 | AssertionError: 期望 401 实际 200: {"code": 0, "data": {"orders": []}}
assert 200 == |

## 失败用例（疑似缺陷）
1. **TC003 错误凭据登录被拒（401）** —— AssertionError: 期望 401 实际 500: {"code": 50000, "message": "服务端内部异常（错误凭据未捕获）"}
assert 500 == 401
 +  where 500 = <Respons
2. **TC005 无/错 token 访问订单被拒（越权）** —— AssertionError: 期望 401 实际 200: {"code": 0, "data": {"orders": []}}
assert 200 == 401
 +  where 200 = <Response [200]>.st
3. **TC005 无/错 token 访问订单被拒（越权）** —— AssertionError: 期望 401 实际 200: {"code": 0, "data": {"orders": []}}
assert 200 == 401
 +  where 200 = <Response [200]>.st

## 结论
检出 3 个失败用例（疑似缺陷），建议接入 Day 31 Bug 分析（蓝图 S9）做根因与测试加固建议；本报告为轻量执行汇总，完整回归报告模板见 day33。