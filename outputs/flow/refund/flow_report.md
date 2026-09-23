# 全流程执行记录（flow_report）

**开始时间**: 2026-09-21 19:46:53
**运行参数**: with_llm=False force=False fail_fast=False use_cache=True

| 阶段 | 状态 | 耗时(s) | 产物指纹 | 说明 |
|------|------|---------|----------|------|
| S1_requirement_cases | skipped_needs_api | 0.0 | - | 模型段需要真实 API：python day34_orchestrator.py --with-llm 补跑 |
| S2_case_review_gate | manual_pending | 0.0 | - | day35_review_gate：exp1 生成待评审种子 → 人工审阅 → exp2 盖章(reviewed) → upsert 硬门禁（reviewed=False 拒绝入库）；manual 永远等人 |
| S3_api_plan | run_ok | 106.11 | outputs/api_test_plan_refund.json#0e326fa75472, outputs/api_test_plan_refund.md#780e02795a32 | cmd 子进程完成（exit=0） |
| S4_test_codegen | run_ok | 29.57 | outputs/generated_tests/refund/conftest.py#37e45ab8a19e, outputs/generated_tests/refund/test_api_suite.py#f1080dbdfdc8 | cmd 子进程完成（exit=0） |
| S5_test_data | run_ok | 28.92 | outputs/data_gen/refund/refund_normal.json#ffbd73eaea25 | cmd 子进程完成（exit=0） |
| S6_execute_normal | run_ok | 8.99 | outputs/flow/refund/junit_normal.xml#5a57bb08e798 | pytest exit=0，JUnit 已落盘 outputs/flow/refund/junit_normal.xml |
| S7_execute_bug | run_ok | 4.56 | outputs/flow/refund/junit_bug.xml#990786763216 | pytest exit=1，JUnit 已落盘 outputs/flow/refund/junit_bug.xml |
| S8_exec_report | run_ok | 0.47 | outputs/flow/refund/exec_report_normal.md#e86f7392c414, outputs/flow/refund/exec_report_bug.md#95e3e4e23f17 | 2 份执行报告已落盘 |
| S9_bug_analyze | skipped_needs_api | 0.0 | - | 模型段需要真实 API：python day34_orchestrator.py --with-llm 补跑 |

## 汇总
manual_pending=1、run_ok=6、skipped_needs_api=2

> 缺口提示：状态含 `skipped_needs_api` → `python day34_orchestrator.py --with-llm` 补跑；
> 含 `manual_pending` → 等 Day 35 两段式评审门；`run_failed` → 看对应 stage 输出。