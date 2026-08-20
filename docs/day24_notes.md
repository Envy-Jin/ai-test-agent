# Day 24 学习笔记：Tool Calling Agent —— 结构化输出 + 向量库修复

## 日期
2026-08-18

## 今日成果
- [ ] `day24_kb_upsert.py`：修复 Day 22 遗留待办——向量库增量更新（KnowledgeUpserter 幂等 upsert + feature 字段 + kb_import 工具）
- [ ] `day24_structured_output.py`：response_format 三种写法（ToolStrategy / ProviderStrategy / 直接传 Schema 类）+ 三个实验
- [ ] `day24_case_agent.py`：完整测试用例生成 Agent（5 工具 + ToolStrategy(TestCaseBundle)）
- [ ] `day24_pyright_pitfalls.py`：5 个新坑位
- [ ] 实操踩坑修复：`m.tool_calls` 需 `isinstance(m, AIMessage)` 收窄（BaseMessage 没有该属性）

## 核心概念

### 1. response_format 结构化输出（2026 新 API）
```python
from langchain.agents.structured_output import ToolStrategy, ProviderStrategy

# ① 人工 tool calling：任何支持工具调用的模型都行（flash-lite 求稳选它）
create_agent(..., response_format=ToolStrategy(ContactInfo))
# ② 模型原生 json_schema：Gemini 支持，更可靠
create_agent(..., response_format=ProviderStrategy(BugReport))
# ③ 直接传 Schema 类：langchain>=1.1 自动选择（支持原生→Provider，否则→Tool）
create_agent(..., response_format=ContactInfo)

result = agent.invoke({...})
contact = result["structured_response"]   # 直接是 Pydantic 实例，无需 json.loads
