"""
Day 17 练习 5：Pyright 避坑实战 —— Memory 场景的类型挑战

Memory 引入后，有几个新的类型安全问题需要处理。
本练习不调用 API，纯演示类型正确的写法 vs 错误的写法。

⚠️ 所有标注「❌ 错误」的代码行都有注释说明为什么不通过 Pyright，
   以及「✅ 正确」的替代写法。

用法：直接运行，全部是演示性质，不含 API 调用。
"""

from typing import Any
from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain_core.messages import HumanMessage, AIMessage


# ═══════════════════════════════════════════════════════
# 坑 1：store 字典的值类型
# ═══════════════════════════════════════════════════════

def pitfall1_store_type() -> None:
    """坑 1：store 字典的值类型不要用具体类"""

    # ❌ 错误：用了具体类 InMemoryChatMessageHistory
    # store_bad: dict[str, InMemoryChatMessageHistory] = {}
    # 问题：如果未来改用 Redis 实现，类型不兼容

    # ✅ 正确：用抽象基类 BaseChatMessageHistory
    store: dict[str, BaseChatMessageHistory] = {}
    store["session1"] = InMemoryChatMessageHistory()
    print(f"store 类型: {type(store).__name__}[str, BaseChatMessageHistory]")


# ═══════════════════════════════════════════════════════
# 坑 2：get_session_history 返回类型
# ═══════════════════════════════════════════════════════

def pitfall2_callback_type() -> None:
    """坑 2：get_session_history 必须有明确的返回类型注解"""

    store: dict[str, BaseChatMessageHistory] = {}

    # ❌ 错误：没有返回类型注解
    # def get_session_history_bad(session_id):
    #     if session_id not in store:
    #         store[session_id] = InMemoryChatMessageHistory()
    #     return store[session_id]

    # ✅ 正确：明确的返回类型
    def get_session_history(session_id: str) -> BaseChatMessageHistory:
        if session_id not in store:
            store[session_id] = InMemoryChatMessageHistory()
        return store[session_id]

    result = get_session_history("test")
    print(f"返回类型: {type(result).__name__}, 消息数: {len(result.messages)}")


# ═══════════════════════════════════════════════════════
# 坑 3：invoke 返回值类型标注
# ═══════════════════════════════════════════════════════

def pitfall3_invoke_type() -> None:
    """坑 3：Memory Chain 的 invoke 需要有类型的变量接收"""

    # 模拟 Memory Chain 的 invoke（返回 Any）
    history = InMemoryChatMessageHistory()
    history.add_message(HumanMessage(content="test"))
    messages = history.messages

    # ❌ 错误：不标注类型，Pyright 推断为 Any
    # result = messages[0].content
    # 后续对 result 的操作都会失去类型检查

    # ✅ 正确：明确标注类型
    first_msg = messages[0]
    content = first_msg.content if isinstance(first_msg.content, str) else str(first_msg.content)
    print(f"消息内容: {content}")


# ═══════════════════════════════════════════════════════
# 坑 4：MessagesPlaceholder vs 旧 tuple 写法
# ═══════════════════════════════════════════════════════

def pitfall4_messages_placeholder() -> None:
    """坑 4：使用 MessagesPlaceholder 代替旧的 tuple 写法"""

    # ❌ 旧写法（也能用，但不推荐）：
    # prompt = ChatPromptTemplate.from_messages([
    #     ("system", "你是助手"),
    #     ("placeholder", "{chat_history}"),  # ← 这里
    #     ("human", "{input}"),
    # ])

    # ✅ 新写法（推荐，语义更清晰）：
    from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是助手"),
        MessagesPlaceholder(variable_name="chat_history"),  # ← 语义明确
        ("human", "{input}"),
    ])

    # 验证
    msgs = prompt.format_messages(chat_history=[], input="hello")
    print(f"format_messages 结果: {len(msgs)} 条消息")
    for m in msgs:
        print(f"  {type(m).__name__}: {m.content[:30]}...")


# ═══════════════════════════════════════════════════════
# 坑 5：历史消息迭代的类型处理
# ═══════════════════════════════════════════════════════

def pitfall5_history_iteration() -> None:
    """坑 5：迭代 history.messages 时正确的类型处理"""

    history = InMemoryChatMessageHistory()
    history.add_message(HumanMessage(content="用户问题"))
    history.add_message(AIMessage(content="AI 回答"))

    # ✅ 方式 1：直接用 .content（BaseMessage 有 content 属性）
    for msg in history.messages:
        print(f"[{type(msg).__name__}] {msg.content[:30]}")

    # ✅ 方式 2：需要区分 Human/AI 时，用 isinstance
    human_msgs = [m for m in history.messages if isinstance(m, HumanMessage)]
    ai_msgs = [m for m in history.messages if isinstance(m, AIMessage)]
    print(f"HumanMessage 数量: {len(human_msgs)}")
    print(f"AIMessage 数量: {len(ai_msgs)}")


# ═══════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    pitfall1_store_type()
    pitfall2_callback_type()
    pitfall3_invoke_type()
    pitfall4_messages_placeholder()
    pitfall5_history_iteration()

    print("\n💡 Memory 场景 Pyright 避坑总结：")
    print("  1. store 值类型用 BaseChatMessageHistory（抽象），不用具体类")
    print("  2. get_session_history 必须有返回类型注解")
    print("  3. Memory Chain 的 invoke 结果用具体类型变量接收")
    print("  4. 用 MessagesPlaceholder 代替 ('placeholder', '{xxx}')")
    print("  5. 迭代 history.messages 时用 isinstance 区分 Human/AI")
    print("  6. AIMessage.content 在 LangChain 中始终是 str（不是 str|None）")
