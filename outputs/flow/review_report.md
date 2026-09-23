# Day 42 复盘报告（由 day42_review_probe.py 自动生成）

> 三个板块分开看：**A 必须全过**；B 是事实陈述（缺口要如实写进总结）；
> C 是脚本无法判断、只能人工确认的部分。

## A. 自动化断言（阻塞项 4 个）

- ❌ [同源] ui/app.py 没有派生自注册表（找不到 'dict(SCENARIO_REGISTRY)'）
- ❌ [同源] ui/app.py 里还留着第二份字面量清单（'_SCENARIOS: dict[str, ScenarioConfig] = {'）
- ❌ [同源] tests/test_day37_app.py 没有派生自注册表（找不到 'set(SCENARIO_REGISTRY)'）
- ❌ [同源] tests/test_day37_app.py 里还留着第二份字面量清单（'set(selector.options) == {"login", "register"}'）

## B. 能力矩阵（在册 4 / 缺口 1）

**在册（生产链有入口）**

- ✅ 需求解析 → 分级用例（S1）← src/agent/day29_requirement_analysis.py
- ✅ 接口测试（计划→套件→执行→报告）（S3–S8）← src/agent/day30_pytest_generator.py
- ✅ Bug 报告 → 结构化分析（S9）← src/agent/day31_bug_analyzer.py
- ✅ 测试数据生成（边界/异常/SQL/Mock）（S5）← src/agent/day32_run_pipeline.py

**缺口（能力练过但生产链无入口）**

- ⚠️ 对话问答（RAG 知识库）（无 · 仅 archive）← src/agent/day21_kb_cli.py

## C. 需人工确认（脚本只打印，不打勾）

- [ ] 截图是否清楚（`docs/images/*.png` 只保证「文件在」，好不好看只能人看）
- [ ] git 历史是否可读（commit 粒度 / message 说清了「为什么」）
- [ ] 学习总结是否写成（`docs/day42_notes.md` + 可选博客）
- [ ] 缺口是否**写进总结**（附录里「已知局限」一节必须提到 B 板块的缺口）

> 判据：A 全过 + C 逐条打勾 = 复盘完成。A 有红项时**先修**，C 不该拿来抵消 A。