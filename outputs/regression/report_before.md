# 回归测试报告：变更前基线

**日期**: 2026-09-03 16:19
**执行人**: AI Agent（mock 靶场）
**变更文件**: src/agent/auth_common.py, src/agent/day30_mock_api.py
**变更摘要**: 将分散的鉴权与 token 签发逻辑收口至 auth_common.py，并将固定 token 改为按手机号后四位动态派生。
**回归范围**: 必回归 ['TC001', 'TC003', 'TC004', 'TC005'] / 建议 [] / 跳过 ['TC002']

## 执行摘要
- 用例总数: 5
- 通过: 5
- 失败: 0
- 跳过: 0
- 错误: 0
- 通过率: 100.0%

## 详细结果
| 状态 | 用例 | 模块 | 耗时(s) | 说明 |
|------|------|------|---------|------|
| passed | test_normal | login | 0.009 |  |
| passed | test_invalid_credentials | login | 0.024 |  |
| passed | test_normal | orders | 0.015 |  |
| passed | test_unauthorized[headers0] | orders | 0.004 |  |
| passed | test_unauthorized[headers1] | orders | 0.004 |  |

## 缺陷列表（疑似回归缺陷）
- 无

## 测试结论
未发现回归缺陷：本次变更范围内的用例全部通过，建议补充 need_add 用例后放行上线。