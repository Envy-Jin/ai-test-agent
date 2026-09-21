# 全流程执行记录（flow_report）

**开始时间**: 2026-09-20 21:39:27
**运行参数**: with_llm=False force=True fail_fast=False use_cache=True

| 阶段 | 状态 | 耗时(s) | 产物指纹 | 说明 |
|------|------|---------|----------|------|
| S1_requirement_cases | skipped_needs_api | 0.0 | - | 模型段需要真实 API：python day34_orchestrator.py --with-llm 补跑 |
| S2_case_review_gate | manual_pending | 0.0 | - | day35_review_gate：exp1 生成待评审种子 → 人工审阅 → exp2 盖章(reviewed) → upsert 硬门禁（reviewed=False 拒绝入库）；manual 永远等人 |
| S3_api_plan | run_ok | 83.53 | outputs/api_test_plan_register.json#23e86a7d0fbb, outputs/api_test_plan_register.md#24ca853f4063 | cmd 子进程完成（exit=0） |
| S4_test_codegen | run_ok | 25.97 | outputs/generated_tests/register/conftest.py#3c4aca15367a, outputs/generated_tests/register/test_api_suite.py#81c6e5100ea3 | cmd 子进程完成（exit=0） |
| S5_test_data | run_ok | 25.29 | outputs/data_gen/register/register_normal.json#d30f79eca4e2 | cmd 子进程完成（exit=0） |
| S6_execute_normal | run_ok | 3.96 | outputs/flow/register/junit_normal.xml#9f0a37fe8d27 | pytest exit=0，JUnit 已落盘 outputs/flow/register/junit_normal.xml |
| S7_execute_bug | run_ok | 3.84 | outputs/flow/register/junit_bug.xml#8c14135e012c | pytest exit=1，JUnit 已落盘 outputs/flow/register/junit_bug.xml |
| S8_exec_report | run_ok | 0.13 | outputs/flow/register/exec_report_normal.md#ed6df27636a2, outputs/flow/register/exec_report_bug.md#64a7e9ce0a20 | 2 份执行报告已落盘 |
| S9_bug_analyze | skipped_needs_api | 0.0 | - | 模型段需要真实 API：python day34_orchestrator.py --with-llm 补跑 |

## 汇总
manual_pending=1、run_ok=6、skipped_needs_api=2

> 缺口提示：状态含 `skipped_needs_api` → `python day34_orchestrator.py --with-llm` 补跑；
> 含 `manual_pending` → 等 Day 35 两段式评审门；`run_failed` → 看对应 stage 输出。