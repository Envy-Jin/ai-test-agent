# Day 36 学习笔记：项目架构重构 + 蓝图 v2 设计定稿

## 日期
2026-09-09（第 6 周 Day 1）

## 今日成果
- 完成第 5 周归档：8 个实验脚本 → archive/week5/（6 个 pyright_pitfalls + day31_bug_archive + day29_agent_v5）
- 完成第 4 周残留补档：6 个 → archive/week4/（day25-28 老 Agent 链）
- utils 物理合并：day35_common 的 4 函数 + ROOT 并入 utils.py，day35_common 降级薄包装（re-export）
- 归档后 import 冒烟全绿（保留 43 模块无本地断链；day34/35 业务链 import OK）
- 蓝图 v2 扩展原型（day36_blueprint_v2）：14 段蓝图（v1 9 + v2 5），产物链闭包校验通过

## 核心概念
### 1. 模块边界 = import 面
### 2. 归档裁决 = 引用事实 × 候选清单（dependents − 候选集 = ∅ 才放行）
### 3. 薄包装兼容层（旧 import 不炸 = 可回退）
### 4. 蓝图 v2：升级 = 换数据（插段/标注全在数据层，执行器零改动）
### 5. S7 语义重定位：埋 Bug mock = 测试资产自验证（变异测试轻量近似）
### 6. 分级闸门：非确定性人审 / 确定性机检
### 7. 本日踩坑记录
- 蓝图同锚点多段注入顺序 bug（S13 一度插到 S10 前 → 链校验失败）→ 维护 inserted_at_anchor 计数修复
- git 命令路径必须正斜杠（Windows Git Bash 反斜杠当转义符）
- Python 多行字符串不能裸跨行（SyntaxError）→ 单行或续行符
- 真实 day34 的 kind 是 llm/manual/code（不是 demo 的 analysis/review/codegen）→ 闸门关键词需覆盖两套词汇

## 还存在的问题 / 待办
- [ ] 第二批分层迁移（17 流程资产 + 通用底座 → src/tools、src/rag、src/config.py），纪律见 5.4
- [ ] 蓝图 v2 真跑全链（S10-S13 + S4.5 需要 register/login 双场景资产与 mock 靶场）—— 周末综合
- [ ] register 资产补齐、评审门扩展 requirement、outputs 场景维度（跟随上两条）
- [ ] utils 纯叶子拆分（paths.py）—— 可选


## day36_dep_closure.py 结果
-目标：d:\AI\Projects\Cursor\ai_test_agent\src\agent，共 58 个模块
-
-=== 引用事实扫描：d:\AI\Projects\Cursor\ai_test_agent\src\agent（58 个模块）===
-  day21_kb_persist           -> ['day20_knowledge_loader']
-  day22_agent_multi          -> ['day20_knowledge_loader', 'day21_kb_persist', 'day22_ddg_search', 'day22_first_agent', 'day22_tool_basics']
-  day22_first_agent          -> ['day22_ddg_search']
-  day23_case_tools           -> ['day22_agent_multi', 'day23_annotated_args', 'json_extractor']        
-  day24_case_agent           -> ['day20_knowledge_loader', 'day21_kb_persist', 'day23_case_tools', 'day24_kb_upsert']
-  day24_kb_upsert            -> ['day20_knowledge_loader', 'day21_kb_persist']
-  day25_error_handling       -> ['day23_case_tools']
-  day25_test_agent_v2        -> ['day23_case_tools', 'day24_case_agent', 'day24_kb_upsert', 'day25_error_handling']
-  day27_multi_tool_agent     -> ['day25_error_handling', 'day25_test_agent_v2', 'day27_mock_api', 'day27_report']
-  day29_agent_v5             -> ['day25_error_handling', 'day25_test_agent_v2', 'day27_multi_tool_agent', 'day27_report', 'day28_mock_api', 'day29_requirement_analysis']
-  day29_pyright_pitfalls     -> ['day27_report', 'day29_doc_loader', 'day29_requirement_analysis']     
-  day29_requirement_analysis -> ['day24_case_agent', 'day29_doc_loader']
-  day30_api_schema           -> ['day29_doc_loader']
-  day30_pyright_pitfalls     -> ['day30_api_schema', 'day30_pytest_generator']
-  day30_pytest_generator     -> ['day30_api_schema']
-  day30_run_pipeline         -> ['day30_mock_api', 'day30_pytest_generator']
-  day31_bug_analyzer         -> ['day24_case_agent', 'day29_doc_loader']
-  day31_bug_archive          -> ['day21_kb_persist', 'day24_case_agent', 'day31_bug_analyzer']
-  day31_pyright_pitfalls     -> ['day31_bug_analyzer']
-  day32_data_generator       -> ['day32_data_schema']
-  day32_data_schema          -> ['day29_doc_loader']
-  day32_pyright_pitfalls     -> ['day32_data_generator', 'day32_data_schema']
-  day32_run_pipeline         -> ['day32_data_generator', 'day32_data_schema']
-  day33_pyright_pitfalls     -> ['day33_change_schema', 'day33_regression_analyzer', 'day33_report_pipeline']
-  day33_regression_analyzer  -> ['day33_change_schema']
-  day33_report_pipeline      -> ['day30_mock_api', 'day33_change_schema', 'day33_regression_analyzer'] 
-  day34_orchestrator         -> ['day30_mock_api', 'day33_change_schema', 'day33_report_pipeline', 'day34_flow_map']
-  day34_pyright_pitfalls     -> ['day34_flow_map', 'day34_orchestrator']
-  day35_review_gate          -> ['day31_bug_analyzer', 'day35_common']
-  day35_scenario             -> ['day34_flow_map', 'day34_orchestrator', 'day35_common']
-  doc_reader                 -> ['logger_config']
-  excel_reporter             -> ['logger_config']
-  feature_extractor          -> ['json_extractor', 'logger_config', 'safe_gemini_client']
-  generate_cases             -> ['logger_config']
-  main_pipeline              -> ['doc_reader', 'feature_extractor', 'logger_config', 'test_case_generator']
-  markdown_reporter          -> ['logger_config']
-  retry_generator            -> ['json_extractor', 'utils']
-  safe_gemini_client         -> ['json_extractor', 'logger_config', 'retry_generator', 'utils']        
-  test_case_generator        -> ['case_schema', 'feature_extractor', 'json_extractor', 'logger_config', 'safe_gemini_client']
-
-  [放行] day29_pyright_pitfalls
-  [放行] day30_pyright_pitfalls
-  [放行] day31_pyright_pitfalls
-  [放行] day32_pyright_pitfalls
-  [放行] day33_pyright_pitfalls
-  [放行] day34_pyright_pitfalls
-  [放行] day31_bug_archive
-  [放行] day29_agent_v5
-  小结：8/8 条可直接归档；0 条需先处理引用
-=== 归档后冒烟（保留 50 个模块的本地依赖闭环）===
-  ✓ 无本地断链 —— 这批归档安全
-  提示：归档动作本身（git mv → archive/week5/）见步骤 5 命令清单，本脚本只做裁决。

## day36_restructure.py 结果
目标：d:\AI\Projects\Cursor\ai_test_agent\src\agent（59 个模块）
-=== 决策对拍 ===
-  [archive_week5] (8) ['day29_agent_v5', 'day29_pyright_pitfalls', 'day30_pyright_pitfalls', 'day31_bug_archive', 'day31_pyright_pitfalls', 'day32_pyright_pitfalls', 'day33_pyright_pitfalls', 'day34_pyright_pitfalls']
-  [archive_week4] (6) ['day25_error_handling', 'day25_test_agent_v2', 'day27_mock_api', 'day27_multi_tool_agent', 'day27_report', 'day28_mock_api']
-  [merge_utils] (1) ['day35_common']
-  [stay] (17) ['day29_doc_loader', 'day29_requirement_analysis', 'day30_api_schema', 'day30_mock_api', 
'day30_pytest_generator', 'day30_run_pipeline', 'day31_bug_analyzer', 'day32_data_generator', 'day32_data_schema', 'day32_run_pipeline', 'day33_change_schema', 'day33_regression_analyzer', 'day33_report_pipeline', 'day34_flow_map', 'day34_orchestrator', 'day35_review_gate', 'day35_scenario']
-=== 命令清单 ===
-  mkdir -p archive/week5   # 归档周目录（相对项目根）
-  git mv src/agent/day29_pyright_pitfalls.py archive/week5/day29_pyright_pitfalls.py
-  git mv src/agent/day30_pyright_pitfalls.py archive/week5/day30_pyright_pitfalls.py
-  git mv src/agent/day31_pyright_pitfalls.py archive/week5/day31_pyright_pitfalls.py
-  git mv src/agent/day32_pyright_pitfalls.py archive/week5/day32_pyright_pitfalls.py
-  git mv src/agent/day33_pyright_pitfalls.py archive/week5/day33_pyright_pitfalls.py
-  git mv src/agent/day34_pyright_pitfalls.py archive/week5/day34_pyright_pitfalls.py
-  git mv src/agent/day31_bug_archive.py archive/week5/day31_bug_archive.py
-  git mv src/agent/day29_agent_v5.py archive/week5/day29_agent_v5.py
-  git mv src/agent/day25_error_handling.py archive/week4/day25_error_handling.py
-  git mv src/agent/day25_test_agent_v2.py archive/week4/day25_test_agent_v2.py
-  git mv src/agent/day27_mock_api.py archive/week4/day27_mock_api.py
-  git mv src/agent/day27_multi_tool_agent.py archive/week4/day27_multi_tool_agent.py
-  git mv src/agent/day27_report.py archive/week4/day27_report.py
-  git mv src/agent/day28_mock_api.py archive/week4/day28_mock_api.py
-  # 合并 src/agent/day35_common.py → utils.py（见 exp3_utils_merge 指引）
-  # 保留 src/agent/day29_doc_loader.py（第 5 周流程资产 = 第 6 周整合素材（蓝图层 day3…）
-  # 保留 src/agent/day29_requirement_analysis.py（第 5 周流程资产 = 第 6 周整合素材（蓝图层 day3…）    
-  # 保留 src/agent/day30_api_schema.py（第 5 周流程资产 = 第 6 周整合素材（蓝图层 day3…）
-  # 保留 src/agent/day30_mock_api.py（第 5 周流程资产 = 第 6 周整合素材（蓝图层 day3…）
-  # 保留 src/agent/day30_pytest_generator.py（第 5 周流程资产 = 第 6 周整合素材（蓝图层 day3…）        
-  # 保留 src/agent/day30_run_pipeline.py（第 5 周流程资产 = 第 6 周整合素材（蓝图层 day3…）
-  # 保留 src/agent/day32_data_generator.py（第 5 周流程资产 = 第 6 周整合素材（蓝图层 day3…）
-  # 保留 src/agent/day32_data_schema.py（第 5 周流程资产 = 第 6 周整合素材（蓝图层 day3…）
-  # 保留 src/agent/day32_run_pipeline.py（第 5 周流程资产 = 第 6 周整合素材（蓝图层 day3…）
-  # 保留 src/agent/day33_change_schema.py（第 5 周流程资产 = 第 6 周整合素材（蓝图层 day3…）
-  # 保留 src/agent/day33_regression_analyzer.py（第 5 周流程资产 = 第 6 周整合素材（蓝图层 day3…）     
-  # 保留 src/agent/day33_report_pipeline.py（第 5 周流程资产 = 第 6 周整合素材（蓝图层 day3…）
-  # 保留 src/agent/day34_flow_map.py（第 5 周流程资产 = 第 6 周整合素材（蓝图层 day3…）
-  # 保留 src/agent/day34_orchestrator.py（第 5 周流程资产 = 第 6 周整合素材（蓝图层 day3…）
-  # 保留 src/agent/day35_review_gate.py（第 5 周流程资产 = 第 6 周整合素材（蓝图层 day3…）
-  # 保留 src/agent/day35_scenario.py（第 5 周流程资产 = 第 6 周整合素材（蓝图层 day3…）
-
-（dry-run：未执行任何动作。确认命令无误后加 --apply 再跑）