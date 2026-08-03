"""
Day 17 练习 1：InMemoryChatMessageHistory 基础

理解 Chat History 的本质：一个消息列表 + 增删操作。

对比 Day 15 的手动 AIMessage 列表管理，理解 Memory 自动化的价值。

⚠️ Pyright 注意事项：
  - InMemoryChatMessageHistory.messages 返回 list[BaseMessage]
  - 迭代时元素类型为 BaseMessage，需要 isinstance 判断子类
  - AIMessage.content 类型为 str（LangChain 保证非 None）
  - store 字典的值类型用 BaseChatMessageHistory（抽象），不用具体类

用法：直接运行跑全部实验，或在 main() 中注释掉不想跑的实验函数。
"""

from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, SystemMessage


# ═══════════════════════════════════════════════════════
# 实验 1：基础 CRUD —— 创建、添加、读取、清空
# ═══════════════════════════════════════════════════════

def exp1_basic_crud() -> None:
    """实验 1：Chat History 的增删查操作"""
    print("=" * 60)
    print("实验 1：Chat History 基础 CRUD")
    print("=" * 60)

    history = InMemoryChatMessageHistory()

    # 初始为空
    print(f"初始消息数: {len(history.messages)}")

    # add_message：添加单条消息
    history.add_message(HumanMessage(content="分析登录功能的需求"))
    history.add_message(AIMessage(content="好的，登录功能包含手机号+密码验证..."))
    print(f"添加 2 条后: {len(history.messages)} 条消息")

    # 查看每条消息
    for i, msg in enumerate(history.messages):
        role = type(msg).__name__
        content_preview = msg.content[:50]
        print(f"  [{i}] {role}: {content_preview}...")

    # add_messages：批量添加（一次传一个 list）
    history.add_messages([
        HumanMessage(content="补充安全测试用例"),
        AIMessage(content="已补充：SQL注入、XSS、密码爆破..."),
    ])
    print(f"批量添加后: {len(history.messages)} 条消息")

    # clear：清空
    history.clear()
    print(f"清空后: {len(history.messages)} 条消息")

# ═══════════════════════════════════════════════════════
# 实验 2：手动模拟"有记忆"vs"无记忆"
# ═══════════════════════════════════════════════════════

def exp2_manual_memory_simulation() -> None:
    """实验 2：手动拼接历史 vs 自动 Memory

    演示 Day 15 做法的痛点：每次 invoke 前要手动把之前的所有消息拼在一起。
    Day 17 的 RunnableWithMessageHistory 自动完成这个过程。
    """
    print("\n" + "=" * 60)
    print("实验 2：手动拼接历史（Day 15 做法）")
    print("=" * 60)

    # 模拟一个对话（注意：history 只包含用户和 AI 消息，不含 SystemMessage）
    history: list[HumanMessage | AIMessage] = []

    # 第 1 轮
    history.append(HumanMessage(content="你好，我是测试工程师"))
    history.append(AIMessage(content="你好！请问有什么需要帮助的？"))
    print(f"第 1 轮后，历史消息数: {len(history)}")
    # 第 2 轮：需要手动把整段历史拼在一起
    history.append(HumanMessage(content="帮我分析登录功能"))
    # ⚠️ Pyright 坑：full_context 必须用 BaseMessage 基类，不能用 HumanMessage | AIMessage
    #    否则 SystemMessage 会报红"is not assignable"
    full_context: list[BaseMessage] = [
        SystemMessage(content="你是测试助手"),
        *history,  # ← 手动展开！
    ]
    print(f"第 2 轮 - 手动拼接了 {len(full_context)} 条消息传给 LLM")
    # 实际中：llm.invoke(full_context)

    # 第 3 轮：又要再拼一次！
    history.append(AIMessage(content="登录功能分析结果..."))
    history.append(HumanMessage(content="补充安全测试"))
    full_context = [
        SystemMessage(content="你是测试助手"),
        *history,  # ← 每次都要手动展开，代码越来越长
    ]
    print(f"第 3 轮 - 手动拼接了 {len(full_context)} 条消息传给 LLM")

    print("\n💡 痛点总结：")
    print("  1. 每次都要手动把所有历史消息拼成 list")
    print("  2. 历史消息越积越多，代码越来越臃肿")
    print("  3. 多用户时，需要手动为每个用户维护单独的列表")
    print("  → Day 17 的 RunnableWithMessageHistory 自动解决以上所有问题！")

#═══════════════════════════════════════════════════════
# 实验 3：store 模式 —— 按 session_id 隔离
# ═══════════════════════════════════════════════════════

def exp3_store_pattern() -> None:
    """实验 3：store 字典模式 —— session_id 隔离的手动实现

    这是 RunnableWithMessageHistory 底层的工作原理预览。
    """
    print("\n" + "=" * 60)
    print("实验 3：store 模式 —— session_id 隔离（Memory 底层原理）")
    print("=" * 60)

    # store 是核心数据结构：按 session_id 存储独立的对话历史
    store: dict[str, BaseChatMessageHistory] = {}

    def get_history(session_id: str) -> BaseChatMessageHistory:
        """按 session_id 获取或创建历史记录"""
        if session_id not in store:
            store[session_id] = InMemoryChatMessageHistory()
        return store[session_id]

    # 用户 A 的对话
    hist_a = get_history("user_a")
    hist_a.add_message(HumanMessage(content="分析登录功能"))
    hist_a.add_message(AIMessage(content="登录功能分析中..."))

    # 用户 B 的对话（完全独立）
    hist_b = get_history("user_b")
    hist_b.add_message(HumanMessage(content="分析注册功能"))
    hist_b.add_message(AIMessage(content="注册功能分析中..."))

    print(f"user_a 消息数: {len(hist_a.messages)}")
    print(f"user_b 消息数: {len(hist_b.messages)}")
    print(f"store 中会话数: {len(store)}")

    # 验证隔离性
    assert hist_a is not hist_b, "两个 session 的历史必须独立！"
    assert hist_a.messages[0].content != hist_b.messages[0].content, "内容也不能混！"
    print("✅ 隔离验证通过：user_a 和 user_b 的对话互不干扰")

    print("\n💡 这就是 RunnableWithMessageHistory 的底层原理：")
    print("  1. 维护一个 store 字典，key 是 session_id")
    print("  2. get_session_history 按 session_id 返回独立的历史对象")
    print("  3. invoke 时自动读写，开发者无需手动管理")



if __name__ == "__main__":
    # exp1_basic_crud()
    # exp2_manual_memory_simulation()
    exp3_store_pattern()

    print("\n💡 小结：")
    print("  - InMemoryChatMessageHistory 就是一个消息列表 + add/clear")
    print("  - 手动管理历史消息既繁琐又容易出错（忘记清空、混入脏数据）")
    print("  - store[session_id] 模式是实现会话隔离的核心")
    print("  - 下一步：RunnableWithMessageHistory 自动完成以上所有操作")