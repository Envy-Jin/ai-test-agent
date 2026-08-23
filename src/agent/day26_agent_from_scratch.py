"""
Day 26 练习 2：手写 ReAct Agent —— 拆开 create_agent 黑盒

目标：
  1. 用 ~15 行 StateGraph 复刻 create_agent 的核心循环（model ⇄ tools）
  2. 理解 Day 25 笔记的认知：create_agent 内部就是这张图
  3. 对比手写版 vs create_agent 版：能力等价，封装省心

核心结构（背下来）：
  START → model（bind_tools 的 LLM）
           ├─ 有 tool_calls → tools（ToolNode 执行）→ 回到 model
           └─ 无 tool_calls → END
  条件边 should_continue 是循环开关（工具调用 → 继续循环；否则结束）

⚠️ Pyright 避坑：
  - 遍历 messages 访问 tool_calls 需 isinstance(m, AIMessage)（Day 24 口诀 16 复用）
  - ToolNode 接受 list[BaseTool]（@tool 产物类型，Day 23 口诀 15 复用）

用法：
  python day26_agent_from_scratch.py    # 真实 API 跑一轮工具循环
"""

import sys
from typing import Annotated, TypedDict

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from day24_case_agent import kb_search

# ═══════════════════════════════════════════════════════
# 状态：消息列表（add_messages reducer → 追加 + 去重）
# ═══════════════════════════════════════════════════════

class AgentState(TypedDict):
    """手写 Agent 的状态：只需要消息列表（聊天图的标准形态）。"""
    messages: Annotated[list[BaseMessage], add_messages]


llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0.2)
model_with_tools = llm.bind_tools([kb_search])  # 绑定工具 → 模型会"看到"工具并可能发起 tool_call

# ═══════════════════════════════════════════════════════
# 节点 1：model —— LLM 决策（返回消息）
# ═══════════════════════════════════════════════════════

def call_model(state: AgentState) -> dict[str, object]:
    """模型节点：把全部消息交给 LLM，返回其回复（可能带 tool_calls）。"""
    response = model_with_tools.invoke(state["messages"])
    # print(f"模型回复：{response}")
    # print(f"模型回复类型：{type(response).__name__}")
    return {"messages": [response]}

# ═══════════════════════════════════════════════════════
# 条件边路由：工具循环的开关
# ═══════════════════════════════════════════════════════

def should_continue(state: AgentState) -> str:
    """路由：最后一条消息是 AIMessage 且有 tool_calls → 去 tools；否则 → END。"""
    msgs: list[BaseMessage] = state["messages"]
    last: BaseMessage = msgs[-1]
    if isinstance(last, AIMessage) and last.tool_calls:
        return "tools"
    return "end"

# ═══════════════════════════════════════════════════════
# 构建图（~15 行核心）
# ═══════════════════════════════════════════════════════

def build_scratch_agent():
    """手写 ReAct：START → model ⇄ tools（条件边循环）→ END。"""
    builder = StateGraph(AgentState)
    builder.add_node("model", call_model)
    builder.add_node("tools", ToolNode([kb_search]))
    builder.add_edge(START, "model")
    builder.add_conditional_edges(
        "model",
        should_continue,
        {"tools": "tools", "end": END},
    )
    builder.add_edge("tools", "model")  # 工具执行完必须回到 model 再决策
    return builder.compile()

# ═══════════════════════════════════════════════════════
# 对比参照：create_agent 一行搞定（Day 22-25 一直在用）
# ═══════════════════════════════════════════════════════

def build_compare_agent():
    """对比版：create_agent 封装（等价于上面的手写图 + 更多内置能力）。"""
    from langchain.agents import create_agent  # noqa: PLC0415

    return create_agent(model=llm, tools=[kb_search])

# ═══════════════════════════════════════════════════════
# 实验
# ═══════════════════════════════════════════════════════

def exp1_run_scratch() -> None:
    """实验 1：手写 Agent 真实运行——让模型自己决定要不要查知识库。"""
    print("=" * 60)
    print("实验 1：手写 ReAct Agent（model ⇄ tools 循环）")
    app = build_scratch_agent()
    config: RunnableConfig = {"recursion_limit": 15}
    result: dict[str, object] = app.invoke(
        {"messages": [HumanMessage(content="查一下知识库：登录功能的历史 Bug 有哪些？")]},
        config=config,
    )
    msgs_obj: object = result.get("messages", [])
    if isinstance(msgs_obj, list) and msgs_obj:
        last: BaseMessage = msgs_obj[-1]
        content: object = last.content
        print(f"✅ Agent 最终回复（前 200 字）：{str(content)[:200]}")
        tool_count: int = 0
        for m in msgs_obj:
            if isinstance(m, AIMessage) and m.tool_calls:
                tool_count += 1
                for tc in m.tool_calls:
                    print(f"   🔧 模型决策调用工具: {tc.get('name')}({tc.get('args')})")
        print(f"   本轮共 {tool_count} 次工具决策（≥1 说明循环真的转了）")


def exp2_compare() -> None:
    """实验 2：对比 create_agent——同样的活儿，一行封装。"""
    print("=" * 60)
    print("实验 2：create_agent 对比版（Day 22-25 的日常写法）")
    agent = build_compare_agent()
    config: RunnableConfig = {"recursion_limit": 15}
    result: dict[str, object] = agent.invoke(
        {"messages": [HumanMessage(content="查一下知识库：登录功能的历史 Bug 有哪些？")]},
        config=config,
    )
    msgs_obj: object = result.get("messages", [])
    if isinstance(msgs_obj, list) and msgs_obj:
        content: object = msgs_obj[-1].content
        print(f"✅ create_agent 回复（前 200 字）：{str(content)[:200]}")


if __name__ == "__main__":
    # exp1_run_scratch()
    exp2_compare()
    print("\n💡 要点回顾：")
    print("   create_agent 的内部 = START → model ⇄ tools → END（今天亲手写了一遍）")
    print("   条件边 should_continue 是循环开关：有 tool_calls 继续转，没有就收工")
    print("   手写版能力等价但少了 middleware/结构化输出/记忆 → 日常还是用 create_agent")
    print("   看透黑盒的意义：出问题时你能推理到内部哪一步挂了")

