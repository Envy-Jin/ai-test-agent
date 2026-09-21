# 全流程执行报告：register · 正常版（基线）

**日期**: 2026-09-20 21:39
**执行**: mock 靶场 + 生成套件（4 个 pytest node）

## 执行摘要
- 用例总数: 4
- 通过: 4
- 失败: 0
- 跳过: 0
- 错误: 0
- 通过率: 100.0%

## 详细结果
| 状态 | 用例 | 模块 | 耗时(s) | 说明 |
|------|------|------|---------|------|
| passed | test_normal | register | 0.036 |  |
| passed | test_missing_params[payload0] | register | 0.024 |  |
| passed | test_missing_params[payload1] | register | 0.004 |  |
| passed | test_invalid_credentials | register | 0.026 |  |

## 失败用例（疑似缺陷）
- 无

## 结论
全部通过（4/4）：当前版本行为符合用例预期。