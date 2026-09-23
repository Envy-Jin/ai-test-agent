# 全流程执行报告：refund · 埋 Bug 版（对照）

**日期**: 2026-09-21 19:46
**执行**: mock 靶场 + 生成套件（4 个 pytest node）

## 执行摘要
- 用例总数: 4
- 通过: 1
- 失败: 3
- 跳过: 0
- 错误: 0
- 通过率: 25.0%

## 详细结果
| 状态 | 用例 | 模块 | 耗时(s) | 说明 |
|------|------|------|---------|------|
| passed | test_normal | refund | 0.009 |  |
| failed | test_missing_params[payload0] | refund | 0.054 | AssertionError: 期望 400 实际 200: {"code": 0, "message": "退款申请已受理", "data": {"refun |
| failed | test_missing_params[payload1] | refund | 0.004 | AssertionError: 期望 400 实际 200: {"code": 0, "message": "退款申请已受理", "data": {"refun |
| failed | test_invalid_credentials | refund | 0.017 | AssertionError: 期望 401 实际 200: {"code": 0, "message": "退款申请已受理", "data": {"refun |

## 失败用例（疑似缺陷）
1. **TC002 退款缺少必填参数** —— AssertionError: 期望 400 实际 200: {"code": 0, "message": "退款申请已受理", "data": {"refund_id": "RF10001"}}
assert 200 == 400
 + 
2. **TC002 退款缺少必填参数** —— AssertionError: 期望 400 实际 200: {"code": 0, "message": "退款申请已受理", "data": {"refund_id": "RF10001"}}
assert 200 == 400
 + 
3. **TC003 订单号不合法退款被拒（401）** —— AssertionError: 期望 401 实际 200: {"code": 0, "message": "退款申请已受理", "data": {"refund_id": "RF10001"}}
assert 200 == 401
 + 

## 结论
检出 3 个失败用例（疑似缺陷），建议接入 Day 31 Bug 分析（蓝图 S9）做根因与测试加固建议；本报告为轻量执行汇总，完整回归报告模板见 day33。