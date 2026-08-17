"""
Day 17 练习 2：RunnableWithMessageHistory 基础

把一个普通 Chain 包装成"有记忆"的 Chain。

核心：RunnableWithMessageHistory 自动完成两件事：
  1. invoke() 前：从 store 取历史，插入 Prompt 的 {chat_history} 位置
  2. invoke() 后：把本轮 input + output 追加回 store

⚠️ Pyright 注意事项：
  - store 值类型用 BaseChatMessageHistory（抽象），不用 InMemoryChatMessageHistory
  - get_session_history 返回类型须显式注解 -> BaseChatMessageHistory
  - config 参数传 {"configurable": {"session_id": "xxx"}}
  - 使用 MessagesPlaceholder(variable_name="chat_history") 而非旧的元组写法
  - invoke() 返回 str（经过 StrOutputParser），类型安全

用法：直接运行跑全部实验，或在 main() 中注释掉不想跑的实验函数。
"""

import os
from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser
from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.runnables import RunnableConfig


# ═══════════════════════════════════════════════════════
# 模块级：LLM + Prompt + store（所有实验共用）
# ═══════════════════════════════════════════════════════

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.3,
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

# 基础 Prompt：注意 MessagesPlaceholder 是历史消息的占位符
base_prompt = ChatPromptTemplate.from_messages([
    ("system", "你是一个友好的软件测试助手。请用简洁专业的中文回答。"),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
])

# 基础 Chain：prompt → LLM → 字符串
base_chain = base_prompt | llm | StrOutputParser()

# store：按 session_id 存储对话历史
store: dict[str, BaseChatMessageHistory] = {}

def get_session_history(session_id: str) -> BaseChatMessageHistory:
    """按 session_id 获取或创建历史记录"""
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]


# ═══════════════════════════════════════════════════════
# 实验 1：有记忆 vs 无记忆对比
# ═══════════════════════════════════════════════════════

def exp1_memory_vs_no_memory() -> None:
    """实验 1：同一个 Chain，有 Memory 和没有 Memory 的行为差异"""
    print("=" * 60)
    print("实验 1：有记忆 vs 无记忆 —— 行为对比")
    print("=" * 60)

    # 构建有记忆的 Chain
    chain_with_memory = RunnableWithMessageHistory(
        base_chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )

    session_config: RunnableConfig = {"configurable": {"session_id": "exp1"}}

    # 第 1 轮
    resp1: str = chain_with_memory.invoke(
        {"input": "我叫张三，是一名初级测试工程师"},
        config=session_config,
    )
    print(f"第 1 轮: {resp1[:80]}...")

    # 第 2 轮：问"我叫什么"——有记忆的 Chain 应该能回答
    resp2: str = chain_with_memory.invoke(
        {"input": "我叫什么名字？我的职位是什么？"},
        config=session_config,
    )
    print(f"第 2 轮: {resp2[:80]}...")

    # 第 3 轮：继续追问
    resp3: str = chain_with_memory.invoke(
        {"input": "请用一句话回忆我们之前聊了什么"},
        config=session_config,
    )
    print(f"第 3 轮: {resp3[:80]}...")

    # 对比：同一个 Chain 但不传 config（没有 session_id）
    print(f"\n对比 —— 不传 config（无记忆）:")
    resp_no_memory: str = base_chain.invoke({"input": "我叫什么名字？","chat_history": []})
    print(f"  无记忆回答: {resp_no_memory[:80]}...")

    # 清理
    store["exp1"].clear()


# ═══════════════════════════════════════════════════════
# 实验 2：查看历史消息
# ═══════════════════════════════════════════════════════

def exp2_inspect_history() -> None:
    """实验 2：查看 RunnableWithMessageHistory 自动维护的历史消息"""
    print("\n" + "=" * 60)
    print("实验 2：查看自动维护的历史消息")
    print("=" * 60)

    chain_with_memory = RunnableWithMessageHistory(
        base_chain,
        get_session_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )

    session_config: RunnableConfig = {"configurable": {"session_id": "exp2"}}

    # 进行几轮对话
    chain_with_memory.invoke(
        {"input": "什么是等价类划分法？"},
        config=session_config,
    )
    chain_with_memory.invoke(
        {"input": "请举个例子"},
        config=session_config,
    )

    # 查看历史
    history = store["exp2"]
    print(f"历史消息数: {len(history.messages)}")
    for i, msg in enumerate(history.messages):
        role = "👤" if msg.__class__.__name__ == "HumanMessage" else "🤖"
        content = msg.content if isinstance(msg.content, str) else str(msg.content)
        content_preview = content[:80].replace('\n', ' ')
        print(f"  [{i}] {role} {content_preview}...")

    print(f"\n💡 发现：")
    print(f"  - 2 轮对话产生了 {len(history.messages)} 条消息（每轮 Human + AI 各 1 条）")
    print("  - 这些消息是 RunnableWithMessageHistory 自动追加的")
    print("  - 下次 invoke 时，它们会自动填入 {chat_history} 位置")

    store["exp2"].clear()


# ═══════════════════════════════════════════════════════
# 实验 3：历史长度管理
# ═══════════════════════════════════════════════════════

def exp3_history_limit() -> None:
    """实验 3：手动控制历史长度，防止 token 超限

    注意：RunnableWithMessageHistory 本身不限制历史长度，
    需要开发者自己控制（比如只保留最近 N 轮）。
    """
    print("\n" + "=" * 60)
    print("实验 3：历史长度管理 —— 防止无限增长")
    print("=" * 60)

    def get_limited_history(session_id: str) -> BaseChatMessageHistory:
        """自定义 get_session_history：每次自动裁剪到最近 4 条消息"""
        if session_id not in store:
            store[session_id] = InMemoryChatMessageHistory()
        hist = store[session_id]
        # 保留最近 4 条（即最近 2 轮对话）
        if len(hist.messages) > 4:
            hist.messages[:] = hist.messages[-4:]
        return hist

    chain_limited = RunnableWithMessageHistory(
        base_chain,
        get_limited_history,
        input_messages_key="input",
        history_messages_key="chat_history",
    )

    session_config: RunnableConfig = {"configurable": {"session_id": "exp3"}}

    # 多轮对话
    questions = [
        "什么是边界值分析法？",
        "请举例说明",
        "它和等价类划分法有什么区别？",
        "在实际测试中如何应用？",
        "还有什么补充的吗？",
    ]
    for q in questions:
        chain_limited.invoke({"input": q}, config=session_config)
        print(f"问完「{q[:15]}...」后，历史消息数: {len(store['exp3'].messages)}")

    print(f"\n💡 最终历史消息数 ≤ 4（被裁剪过），防止 token 爆炸")

    store["exp3"].clear()


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    # exp1_memory_vs_no_memory()
    # exp2_inspect_history()
    exp3_history_limit()

    print("\n💡 小结：")
    print("  - RunnableWithMessageHistory 自动管理历史的读取和写入")
    print("  - 同一个 Prompt 模板 + Memory = 有记忆的对话系统")
    print("  - store 字典 + session_id = 多用户隔离")
    print("  - 历史消息会无限增长，生产环境需要裁剪策略")
