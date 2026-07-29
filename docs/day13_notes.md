# Day 13 学习笔记：周末综合实战 — 需求文档 → 测试用例生成器（上）

## 日期
2026-07-28

## 今日成果
- [ ] 设计并实现完整的端到端流水线架构
- [ ] DocReader: 支持 .txt / .md 需求文档读取
- [ ] FeatureExtractor: 用 Gemini 提取结构化功能点
- [ ] TestCaseGenerator: 为每个功能点独立生成测试用例
- [ ] MainPipeline: 一键串联全流程并输出 JSON
- [ ] 用 2 个需求文档验证流水线通用性

## 核心架构
- DocReader → FeatureExtractor → TestCaseGenerator → MainPipeline → JSON

### 设计决策
- 每个功能点单独调用 Gemini（不把所有功能点放一个 Prompt）
  - 原因：上下文太长 LLM 会偷懒，独立调用保证每个功能点的用例质量
- 功能提取用自由 JSON（generate_json），用例生成用 Schema（generate_schema）
  - 原因：功能点结构多变用自由提取更灵活；用例结构固定用 Schema 更可靠
- 所有 API 调用统一走 SafeGeminiClient（Day 12 封装）
  - 原因：重试、日志、类型安全全有了，不重复造轮子

## 踩坑记录
- dict[str, Any]和dict的区别就是前者定死了key的类型，而后者随便key是什么类型都可以
- 有些时候输出的case可能没有达到期望，比如缺少某些case，需要注意优化prompt

## Day 14 预告
- 加入 openpyxl Excel 输出（每个功能点一个 Sheet）
- 添加命令行参数（--input / --output / --format）
- 添加 Markdown 报告输出
- 用更多需求文档测试流水线
- 可选的并行生成加速

## 第 2 周回顾
- [ ] Day 8: Gemini API 调通 + 参数理解
- [ ] Day 9: Prompt 工程五大技巧 + Pydantic Schema
- [ ] Day 10: 多模态（图片）+ 流式输出
- [ ] Day 11: 多轮对话 + 历史管理 + safe_text
- [ ] Day 12: 结构化输出封装 + SafeGeminiClient
- [ ] Day 13: 周末综合实战（上）— 需求文档 → 用例 JSON ← 今天
- [ ] Day 14: 周末综合实战（下）— Excel 输出 + CLI + 测试