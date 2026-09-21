# 全流程执行报告：login · 正常版（基线）

**日期**: 2026-09-20 21:43
**执行**: mock 靶场 + 生成套件（7 个 pytest node）

## 执行摘要
- 用例总数: 7
- 通过: 7
- 失败: 0
- 跳过: 0
- 错误: 0
- 通过率: 100.0%

## 详细结果
| 状态 | 用例 | 模块 | 耗时(s) | 说明 |
|------|------|------|---------|------|
| passed | test_normal | login | 0.009 |  |
| passed | test_missing_params[payload0] | login | 0.005 |  |
| passed | test_missing_params[payload1] | login | 0.004 |  |
| passed | test_invalid_credentials | login | 0.004 |  |
| passed | test_normal | orders | 0.021 |  |
| passed | test_unauthorized[headers0] | orders | 0.005 |  |
| passed | test_unauthorized[headers1] | orders | 0.004 |  |

## 失败用例（疑似缺陷）
- 无

## 结论
全部通过（7/7）：当前版本行为符合用例预期。