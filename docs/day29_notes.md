# Day 29 学习笔记：第 5 周开篇 —— 需求文档解析 → 分级测试用例生成（.txt/.md/.docx）

## 日期
2026-08-27

## 今日成果
- [ ] `day29_doc_loader.py`：文档加载器（.txt/.md 零依赖 + python-docx 1.2.0 可选导入读 .docx 段落+表格；不支持格式/缺失文件 → None）
- [ ] `day29_requirement_analysis.py`：RequirementAnalysis 分级 Schema（P0/P1/P2 + 功能/边界/异常/安全/兼容 Literal 枚举）+ 分析 Chain（with_fallbacks 容错）+ validate_analysis 质检（id 唯一/分级覆盖度/统计 sum 推导）+ Markdown 渲染 + 幂等入库
- [ ] `day29_agent_v5.py`：Agent v5 多出口（ToolStrategy(Union[RequirementAnalysis, TestReport])，模型按任务自动选 Schema）——联网确认的新特性落地
- [ ] `day29_pyright_pitfalls.py`：4 个新坑演示 + 模块零 API 自检
- [ ] `outputs/`：requirement_login_analysis.json/.md、requirement_register_analysis.json/.md、requirement_v5_analysis.md
- [ ] 联网确认：python-docx 1.2.0（2026-04 发布）；ToolStrategy Union 多出口官方特性；with_fallbacks = Chain 标准容错

## 核心概念

### 1. 固定任务 Chain，检索决策 Agent（昨日答疑落地）
```python
# 需求解析是固定单任务 → 不建 Agent 循环：
chain = prompt | llm.with_fallbacks([backup]).with_structured_output(RequirementAnalysis)
result = chain.invoke({"requirement": text})   # 一次调用，输出即校验过的 Pydantic 实例
# Agent 循环 = 模型驱动轮次（每轮决策都是 LLM 调用）；LCEL 链 = 开发者驱动（固定转换）
# 判断口诀：任务需要"自主决定下一步" → Agent；任务"输入→输出形状固定" → Chain
