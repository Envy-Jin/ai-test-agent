# 全流程执行报告：register · 埋 Bug 版（对照）

**日期**: 2026-09-20 21:39
**执行**: mock 靶场 + 生成套件（4 个 pytest node）

## 执行摘要
- 用例总数: 4
- 通过: 3
- 失败: 1
- 跳过: 0
- 错误: 0
- 通过率: 75.0%

## 详细结果
| 状态 | 用例 | 模块 | 耗时(s) | 说明 |
|------|------|------|---------|------|
| passed | test_normal | register | 0.008 |  |
| passed | test_missing_params[payload0] | register | 0.018 |  |
| passed | test_missing_params[payload1] | register | 0.014 |  |
| failed | test_invalid_credentials | register | 0.044 | AssertionError: 期望 401 实际 200: {"code": 0, "message": "注册成功", "data": {"user_id" |

## 失败用例（疑似缺陷）
1. **TC003 验证码错误注册被拒（401）** —— AssertionError: 期望 401 实际 200: {"code": 0, "message": "注册成功", "data": {"user_id": "U10001"}}
assert 200 == 401
 +  where

## 结论
检出 1 个失败用例（疑似缺陷），建议接入 Day 31 Bug 分析（蓝图 S9）做根因与测试加固建议；本报告为轻量执行汇总，完整回归报告模板见 day33。