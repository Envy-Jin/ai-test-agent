# 回归测试报告：变更后（样本）

**日期**: 2026-09-03 15:58
**执行人**: AI Agent（mock 靶场）
**变更文件**: src/agent/auth_common.py, src/agent/day30_mock_api.py
**变更摘要**: （样本报告）变更后执行结果
**回归范围**: 必回归 [] / 建议 [] / 跳过 []

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
| passed | test_normal | login | 0.080 |  |
| passed | test_missing_params[payload0] | login | 0.072 |  |
| passed | test_missing_params[payload1] | login | 0.070 |  |
| failed | test_invalid_credentials | login | 0.090 | AssertionError: 期望 401 实际 500: {"code": 50000, "message": "服务器内部错误"} |
| passed | test_normal | orders | 0.095 |  |
| failed | test_unauthorized[headers0] | orders | 0.088 | AssertionError: 期望 401 实际 200: {"code": 0, "data": {"orders": []}} |
| failed | test_unauthorized[headers1] | orders | 0.091 | AssertionError: 期望 401 实际 200: {"code": 0, "data": {"orders": []}} |

## 缺陷列表（疑似回归缺陷）
1. **TC003 错误凭据登录被拒（401）** —— AssertionError: 期望 401 实际 500: {"code": 50000, "message": "服务器内部错误"}
2. **TC005 无/错 token 访问订单被拒（越权）** —— AssertionError: 期望 401 实际 200: {"code": 0, "data": {"orders": []}}
3. **TC005 无/错 token 访问订单被拒（越权）** —— AssertionError: 期望 401 实际 200: {"code": 0, "data": {"orders": []}}

## 测试结论
检出 3 个疑似回归缺陷：TC003(错误凭据登录被拒（401）), TC005(无/错 token 访问订单被拒（越权）), TC005(无/错 token 访问订单被拒（越权）)。这些用例在变更前基线是通过的——本次变更极可能引入了回归，建议修复后重跑 affected 范围（Day 31 Bug 分析流程可接续分析）再上线。