# register 场景补齐计划（Day 35 exp4）

由场景工厂盘点自动生成：同一 9 段蓝图，register 缺资产 → 状态见下。

| 阶段 | 状态 | 需要补什么 |
|------|------|-----------|
| S1_requirement_cases | needs_api | 输入齐、产物缺 → --with-llm 补跑（真 API） |
| S2_case_review_gate | manual_pending | day35_review_gate：exp1 生成待评审种子 → 人工审阅 → exp2 盖章(reviewed) → upsert 硬门禁（reviewed=False 拒绝入库）；manual 永远等人 |
| S3_api_plan | needs_api | 输入齐、产物缺 → --with-llm 补跑（真 API） |
| S9_bug_analyze | missing_input | 外部输入缺失：docs/bugs/register_bugs.md |

## 补齐指引（对应文档步骤 4 延伸练习）
- S1/S3：资产在位，跑 `python day34_orchestrator.py --with-llm` 由实现层补产物
- S5：缺 docs/schemas/register.json —— 抄 register_api.json 字段规则生成（.json 走代码直读）
- S9：缺 docs/bugs/register_bugs.md —— 按 login_bugs.md 格式补一份（至少 2 条 ## BUG-xx）
- S4/S6/S7/S8：code 段资产到齐后由执行器自动跑（mock 端口已按场景隔离为 8767）