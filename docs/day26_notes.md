# Day 26 学习笔记：LangGraph 状态管理 + checkpointer 对话记忆

## 日期
2026-08-22

## 今日成果
- [ ] `day26_state_graph.py`：StateGraph 显式流程图（五件套 + 条件边回炉循环 + LLM 增强版）
- [ ] `day26_agent_from_scratch.py`：手写 ReAct Agent（model ⇄ tools 条件循环，拆开 create_agent 黑盒）
- [ ] `day26_checkpointer_memory.py`：Agent v3（checkpointer 对话记忆，InMemorySaver + SqliteSaver）
- [ ] `day26_pyright_pitfalls.py`：6 个新坑位
- [ ] 联网确认：create_agent 原生支持 checkpointer；InMemorySaver 是新名；gemini-3.5-flash 存在（Premium 付费）

## 核心概念

### 1. LangGraph 五件套
```python
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from typing import Annotated, TypedDict
import operator

class State(TypedDict):
    messages: Annotated[list, add_messages]   # 消息追加+去重（聊天专用）
    count: Annotated[int, operator.add]       # 数值累积
    topic: str                                # 覆盖式（最后写入者胜）

def node(state: State) -> dict[str, object]:  # 节点 = 函数，返回部分更新
    return {"count": 1}

builder = StateGraph(State)
builder.add_node("node", node)
builder.add_edge(START, "node")               # START 是标准入口（set_entry_point 是 legacy）
builder.add_edge("node", END)
app = builder.compile()

# 条件边 + 循环（LCEL 做不到的回炉重试）
builder.add_conditional_edges("node", router_fn, {"a": "node", "b": END})
