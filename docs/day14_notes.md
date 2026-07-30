# Day 14 学习笔记：周末综合实战 — Excel/CLI/归档（下）

## 日期
2026-07-29

## 今日成果
- [ ] openpyxl 实现多 Sheet 带格式的 Excel 测试报告
- [ ] Markdown 测试报告生成器
- [ ] argparse CLI 命令行工具（--input / --output / --format）
- [ ] 用 3+ 个需求文档验证流水线通用性
- [ ] 第 2 周练习文件归档整理

## 新学到的知识

### openpyxl
- WorkBook → Sheet → Cell 三级结构
- 样式控制：Font / PatternFill / Alignment / Border
- merge_cells() 合并单元格
- freeze_panes 冻结表头
- 条件格式化：优先级颜色、用例类型背景色

### argparse
- ArgumentParser 构建 CLI 工具
- 位置参数 vs 可选参数
- choices 限制参数值
- --version 内置

### 项目工程化
- 练习代码 vs 业务代码的分离（归档的重要性）
- 文件结构随项目演进的整理习惯

## 第 2 周整体回顾
- [ ] Day 8: Gemini API 调通 + 参数理解 ✓
- [ ] Day 9: Prompt 工程 + Pydantic Schema ✓
- [ ] Day 10: 多模态 + 流式输出 ✓
- [ ] Day 11: 多轮对话 + safe_text ✓
- [ ] Day 12: 结构化输出 + SafeGeminiClient 封装 ✓
- [ ] Day 13: 周末实战（上）— 主流水线 + JSON 输出 ✓
- [ ] Day 14: 周末实战（下）— Excel/CLI/Markdown + 归档 ✓

## 第 3 周预告
- Day 15: LangChain 架构与 Gemini 集成
- LangChain 核心概念：LLM / Chain / Memory
- LCEL 表达式语言
- 带记忆的对话系统
