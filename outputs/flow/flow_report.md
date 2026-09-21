# 全流程执行记录（flow_report）

**开始时间**: 2026-09-20 21:43:07
**运行参数**: with_llm=False force=True fail_fast=False use_cache=True

| 阶段 | 状态 | 耗时(s) | 产物指纹 | 说明 |
|------|------|---------|----------|------|
| S1_requirement_cases | skipped_needs_api | 0.0 | - | 模型段需要真实 API：python day34_orchestrator.py --with-llm 补跑 |
| S2_case_review_gate | manual_pending | 0.0 | - | day35_review_gate：exp1 生成待评审种子 → 人工审阅 → exp2 盖章(reviewed) → upsert 硬门禁（reviewed=False 拒绝入库）；manual 永远等人 |
| S3_api_plan | skipped_needs_api | 0.0 | - | 模型段需要真实 API：python day34_orchestrator.py --with-llm 补跑 |
| S4_test_codegen | run_ok | 21.31 | outputs/generated_tests/conftest.py#ab71e884cd68, outputs/generated_tests/test_api_suite.py#4ade0c95b54f | cmd 子进程完成（exit=0） |
| S5_test_data | skipped_needs_api | 0.0 | - | 模型段需要真实 API：python day34_orchestrator.py --with-llm 补跑 |
| S6_execute_normal | run_ok | 5.6 | outputs/flow/junit_normal.xml#9d34885bbc68 | pytest exit=0，JUnit 已落盘 outputs/flow/junit_normal.xml |
| S7_execute_bug | run_ok | 4.68 | outputs/flow/junit_bug.xml#e22b5bd697cd | pytest exit=1，JUnit 已落盘 outputs/flow/junit_bug.xml |
| S8_exec_report | run_ok | 0.07 | outputs/flow/exec_report_normal.md#2b7df4951351, outputs/flow/exec_report_bug.md#669ad812140c | 2 份执行报告已落盘 |
| S9_bug_analyze | skipped_needs_api | 0.0 | - | 模型段需要真实 API：python day34_orchestrator.py --with-llm 补跑 |

## 汇总
manual_pending=1、run_ok=4、skipped_needs_api=4

> 缺口提示：状态含 `skipped_needs_api` → `python day34_orchestrator.py --with-llm` 补跑；
> 含 `manual_pending` → 等 Day 35 两段式评审门；`run_failed` → 看对应 stage 输出。