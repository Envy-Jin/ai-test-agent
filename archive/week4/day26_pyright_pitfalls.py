"""
Day 26 避坑实战：LangGraph 场景的 Pyright / 运行时陷阱

坑 1：TypedDict 取值是声明的类型，但消息列表要访问 tool_calls 需 isinstance(AIMessage) 收窄
坑 2：节点函数返回 dict 值类型 invariant → 统一标注 dict[str, object]（reducer 字段除外）
坑 3：Annotated[list, add_messages] 里 add_messages 是 Any（pyright 不校验元数据）
坑 4：条件边路由函数返回 str；映射 dict 的 key 必须覆盖所有返回值
坑 5：get_state 返回 StateSnapshot → .values 是 dict（取值要收窄）
坑 6：checkpointer 的 config 是嵌套结构：thread_id 在 configurable 里，recursion_limit 在外层

用法：python day26_pyright_pitfalls.py（纯本地逻辑，无 API）
"""

import sys
from typing import Annotated, TypedDict

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph.message import add_messages


# ── 坑 1 + 坑 3：State 定义 ──────────────────────────────

class ChatState(TypedDict):
    """消息 + 自定义字段的混合状态。"""
    messages: Annotated[list[BaseMessage], add_messages]  # 坑 3：add_messages 元数据 pyright 不校验
    topic: str  # 覆盖式字段


def demo_message_narrow(state: ChatState) -> None:
    """坑 1：消息列表取值后访问 tool_calls 必须 isinstance 收窄到 AIMessage。"""
    msgs: list[BaseMessage] = state["messages"]
    last: BaseMessage = msgs[-1]
    # ❌ 直接 last.tool_calls → pyright 报错：BaseMessage 没有 tool_calls 属性
    if isinstance(last, AIMessage):  # ✅ 收窄后才有 tool_calls
        print(f"✅ AIMessage 收窄成功: tool_calls={last.tool_calls}")
    else:
        print(f"✅ 非 AIMessage（{type(last).__name__}），跳过 tool_calls 访问")


# ── 坑 2：节点函数返回类型 ──────────────────────────────

def demo_node_return_type() -> None:
    """坑 2：节点函数返回 dict[str, object] 统一标注（避免 dict 值类型 invariant）。"""
    # ❌ def node(state: ChatState) -> dict[str, str]: return {"topic": "x", "messages": [...]}
    #    → messages 是 list，dict[str, str] 容不下 → invariant 报错
    # ✅ 返回类型统一 dict[str, object]
    def node(state: ChatState) -> dict[str, object]:
        return {"topic": "登录", "messages": [HumanMessage(content="hi")]}

    out: dict[str, object] = node({"messages": [], "topic": ""})
    topic: object = out.get("topic")
    if isinstance(topic, str):
        print(f"✅ 节点返回 dict[str, object] 兼容混合字段: topic={topic}")


# ── 坑 4：条件边路由函数 ────────────────────────────────

def demo_router() -> None:
    """坑 4：路由函数返回 str；映射 dict 的 key 必须覆盖所有返回值。"""
    def route(state: ChatState) -> str:
        msgs: list[BaseMessage] = state["messages"]
        last: BaseMessage = msgs[-1]
        if isinstance(last, AIMessage) and last.tool_calls:
            return "tools"
        return "end"

    state: ChatState = {"messages": [HumanMessage(content="hello")], "topic": ""}
    nxt: str = route(state)
    # 映射表（graph 里用的）：
    mapping: dict[str, str] = {"tools": "tools", "end": "__end__"}  # 实际写 {"tools": "tools", "end": END}
    print(f"✅ 路由返回值 {nxt!r} → 映射到 {mapping[nxt]!r}（key 必须全覆盖，否则运行期 KeyError）")


# ── 坑 5 + 坑 6：get_state 与 config ─────────────────────

def demo_state_snapshot() -> None:
    """坑 5：get_state 返回 StateSnapshot，.values 是 dict[str, Any]，取值要收窄。

    坑 6：config 嵌套结构——thread_id 在 configurable 里，recursion_limit 在外层。
    """
    config: dict[str, object] = {
        "configurable": {"thread_id": "demo"},
        "recursion_limit": 25,
    }
    # 演示读取 thread_id（实际代码里直接传给 agent.invoke，这里只演示结构）
    conf_obj: object = config.get("configurable", {})
    if isinstance(conf_obj, dict):
        tid: object = conf_obj.get("thread_id")
        if isinstance(tid, str):
            print(f"✅ config 嵌套读取: thread_id={tid}, recursion_limit={config.get('recursion_limit')}")
    # StateSnapshot 的 values 同理：object 取值 → isinstance 收窄
    fake_snapshot: dict[str, object] = {"values": {"topic": "登录"}, "next": ()}
    values_obj: object = fake_snapshot.get("values")
    if isinstance(values_obj, dict):
        topic_obj: object = values_obj.get("topic")
        topic: str = topic_obj if isinstance(topic_obj, str) else ""
        print(f"✅ snapshot.values 收窄: topic={topic}")


def main() -> None:
    demo_message_narrow({"messages": [HumanMessage(content="hi")], "topic": ""})
    demo_node_return_type()
    demo_router()
    demo_state_snapshot()
    print("\n💡 坑位回顾：")
    print("   1. 消息容器访问 tool_calls → isinstance(m, AIMessage)（Day 24 口诀 16 复用）")
    print("   2. 节点函数返回 dict[str, object]（混合字段不触发 invariant）")
    print("   3. Annotated 元数据（add_messages）pyright 不校验，放心写")
    print("   4. 条件边映射 dict 的 key 要覆盖路由函数全部返回值")
    print("   5. get_state/snapshot.values 取值要 isinstance 收窄")
    print("   6. thread_id 在 config.configurable 里，recursion_limit 在外层")


if __name__ == "__main__":
    main()
