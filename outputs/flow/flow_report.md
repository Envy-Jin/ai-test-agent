# 全流程执行记录（flow_report）

**开始时间**: 2026-09-22 16:20:39
**运行参数**: with_llm=False force=False fail_fast=False use_cache=True

| 阶段 | 状态 | 耗时(s) | 产物指纹 | 说明 |
|------|------|---------|----------|------|
| S1_requirement_cases | reused | 0.0 | outputs/requirement_login_analysis.json#53490d52f152, outputs/requirement_login_analysis.md#fdbfa319500a | 产物在位且非空 → 断点续跑（--force 可强制重跑） |
| S2_case_review_gate | manual_pending | 0.0 | - | day35_review_gate：exp1 生成待评审种子 → 人工审阅 → exp2 盖章(reviewed) → upsert 硬门禁（reviewed=False 拒绝入库）；manual 永远等人 |
| S3_api_plan | reused | 0.0 | outputs/api_test_plan_login.json#5552f145100a, outputs/api_test_plan_login.md#8fbb79ddbd53 | 产物在位且非空 → 断点续跑（--force 可强制重跑） |
| S4_test_codegen | reused | 0.0 | outputs/generated_tests/conftest.py#ab71e884cd68, outputs/generated_tests/test_api_suite.py#4ade0c95b54f | 产物在位且非空 → 断点续跑（--force 可强制重跑） |
| S5_test_data | reused | 0.0 | outputs/data_gen/users_normal.json#16c9a77eb376, outputs/data_gen/orders_normal.json#ecc96ee17990 | 产物在位且非空 → 断点续跑（--force 可强制重跑） |
| S6_execute_normal | reused | 0.0 | outputs/flow/junit_normal.xml#9d34885bbc68 | 产物在位且非空 → 断点续跑（--force 可强制重跑） |
| S8_exec_report | reused | 0.0 | outputs/flow/exec_report_normal.md#2b7df4951351 | 产物在位且非空 → 断点续跑（--force 可强制重跑） |
| S9_bug_analyze | reused | 0.0 | outputs/bug_login_analysis.json#c07b1ac9c208, outputs/bug_login_analysis.md#5fa14399730c, outputs/bug_login_batch_report.md#5e2ca4568ffc | 产物在位且非空 → 断点续跑（--force 可强制重跑） |

## 汇总
manual_pending=1、reused=7

> 缺口提示：状态含 `skipped_needs_api` → `python day34_orchestrator.py --with-llm` 补跑；
> 含 `manual_pending` → 等 Day 35 两段式评审门；`run_failed` → 看对应 stage 输出。