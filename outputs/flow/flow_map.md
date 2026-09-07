# 测试全流程 Agent：蓝图 + 资产盘点

**项目根**: `d:\AI\Projects\Cursor\ai_test_agent`

| # | 阶段 | 来源 | 性质 | 执行器 | 状态 | 说明 |
|---|------|------|------|--------|------|------|
| S1_requirement_cases | 需求解析 → 分级用例 | day29 | llm | cmd | reused | 产物在位且非空，可回放（指纹由执行器算） |
| S2_case_review_gate | 用例评审闸门（占位） | day35 | manual | cmd | manual_pending | 两段式评审门（Day 35）：exp_generate 落盘止 → exp_seed_approved 读回打 reviewed → upsert 硬门禁。今天只占位，永远 manual_pending |
| S3_api_plan | 接口文档 → 接口测试计划 | day30 | llm | cmd | reused | 产物在位且非空，可回放（指纹由执行器算） |
| S4_test_codegen | 计划 → pytest 代码（确定性渲染） | day30 | code | cmd | reused | 产物在位且非空，可回放（指纹由执行器算） |
| S5_test_data | 字段规则 → 测试数据 | day32 | llm | cmd | reused | 产物在位且非空，可回放（指纹由执行器算） |
| S6_execute_normal | 执行：mock 正常版 → JUnit XML | day30/综合 | code | mock+pytest | reused | 产物在位且非空，可回放（指纹由执行器算） |
| S7_execute_bug | 执行：mock 埋 Bug 版 → JUnit XML（对照回路） | day30/综合 | code | mock+pytest | reused | 产物在位且非空，可回放（指纹由执行器算） |
| S8_exec_report | JUnit → 执行报告（缺陷反查注册表） | day33/综合 | code | 报告渲染 | reused | 产物在位且非空，可回放（指纹由执行器算） |
| S9_bug_analyze | Bug 报告 → 结构化分析（批量+聚合） | day31 | llm | cmd | reused | 产物在位且非空，可回放（指纹由执行器算） |

## 状态汇总
manual_pending=1、reused=8

> 缺口清单 = 周末训练任务：`needs_api` 段用 `--with-llm` 补跑；`run_ready` 段由执行器自动跑；`manual_pending` 段等 Day 35 评审门。