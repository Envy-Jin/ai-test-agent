"""
Day 17 练习 3：多会话隔离实践

验证不同 session_id 的对话互不干扰。

模拟场景：两个测试工程师同时使用同一个 AI 助手，
分别分析"登录功能"和"支付功能"的需求。

⚠️ Pyright 注意事项：
  - store 值类型用 BaseChatMessageHistory（抽象类），方便扩展
  - config 中的 session_id 是纯字符串类型
  - 验证隔离性的 assert 语句有助于发现内存混串的 bug

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
    temperature=0.2,
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

test_prompt = ChatPromptTemplate.from_messages([
    ("system", "你是专业的软件测试工程师。记住用户正在分析的功能需求，回答时结合之前的上下文。"),
    MessagesPlaceholder(variable_name="chat_history"),
    ("human", "{input}"),
])

base_chain = test_prompt | llm | StrOutputParser()

store: dict[str, BaseChatMessageHistory] = {}

def get_session_history(session_id: str) -> BaseChatMessageHistory:
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]

chain_with_memory = RunnableWithMessageHistory(
    base_chain,
    get_session_history,
    input_messages_key="input",
    history_messages_key="chat_history",
)


# ═══════════════════════════════════════════════════════
# 实验 1：两用户并行分析不同需求
# ═══════════════════════════════════════════════════════

def exp1_two_users_parallel() -> None:
    """实验 1：两个用户并行对话，验证互不干扰"""
    print("=" * 60)
    print("实验 1：两个用户并行分析不同需求")
    print("=" * 60)

    config_a: RunnableConfig = {"configurable": {"session_id": "tester_zhang"}}
    config_b: RunnableConfig = {"configurable": {"session_id": "tester_li"}}

    # 用户 A（张）：第 1 轮
    resp_a1: str = chain_with_memory.invoke(
        {"input": "我在分析登录功能的需求，请帮我列出需要关注的测试点"},
        config=config_a,
    )

    # 用户 B（李）：第 1 轮
    resp_b1: str = chain_with_memory.invoke(
        {"input": "我在分析支付功能的需求，请帮我列出关键的安全测试点"},
        config=config_b,
    )

    # 用户 A：第 2 轮 —— 应该继续登录的上下文
    resp_a2: str = chain_with_memory.invoke(
        {"input": "我现在在分析什么功能？请回顾一下"},
        config=config_a,
    )

    # 用户 B：第 2 轮 —— 应该继续支付的上下文
    resp_b2: str = chain_with_memory.invoke(
        {"input": "我现在在分析什么功能？请回顾一下"},
        config=config_b,
    )

    print(f"用户张的第 1 轮回答（前60字符）:\n  {resp_a1[:60]}...")
    print(f"用户李的第 1 轮回答（前60字符）:\n  {resp_b1[:60]}...")
    print()
    print(f"用户张的第 2 轮回顾（应该提到登录）:\n  {resp_a2[:100]}...")
    print(f"用户李的第 2 轮回顾（应该提到支付）:\n  {resp_b2[:100]}...")

    # 验证隔离性
    hist_a = store["tester_zhang"]
    hist_b = store["tester_li"]
    print(f"\n用户张的历史消息数: {len(hist_a.messages)}")
    print(f"用户李的历史消息数: {len(hist_b.messages)}")
    print(f"store 中总会话数: {len(store)}")



# ═══════════════════════════════════════════════════════
# 实验 2：同一用户的多次独立对话
# ═══════════════════════════════════════════════════════

def exp2_same_user_different_sessions() -> None:
    """实验 2：同一用户开多个 session，验证不同 session 完全独立"""
    print("\n" + "=" * 60)
    print("实验 2：同一用户不同 session — 每次 generate 一个独立对话 ID")
    print("=" * 60)

    import uuid

    def new_session() -> RunnableConfig:
        """模拟一次新的对话：生成新 session_id"""
        sid = str(uuid.uuid4())[:8]
        return {"configurable": {"session_id": sid}}

    def get_session_id(cfg: RunnableConfig, default: str = "") -> str:
        """从 RunnableConfig 安全提取 session_id"""
        configurable = cfg.get("configurable", {})
        if isinstance(configurable, dict):
            sid = configurable.get("session_id", default)
            return sid if isinstance(sid, str) else default
        return default

    # 对话 1：分析登录
    cfg1: RunnableConfig = new_session()
    chain_with_memory.invoke(
        {"input": "分析登录功能的正向测试用例"},
        config=cfg1,
    )

    # 对话 2：分析支付（新的 session_id，完全独立）
    cfg2: RunnableConfig = new_session()
    chain_with_memory.invoke(
        {"input": "分析支付功能的异常测试用例"},
        config=cfg2,
    )

    # 回到对话 1（同一个 session_id）
    chain_with_memory.invoke(
        {"input": "补充安全测试用例"},
        config=cfg1,
    )

    # 检查
    sid1 = get_session_id(cfg1)
    sid2 = get_session_id(cfg2)
    print(f"对话 1 (session={sid1}) 消息数: {len(store[sid1].messages)}")
    print(f"对话 2 (session={sid2}) 消息数: {len(store[sid2].messages)}")
    print(f"✅ 对话 1 仍然是登录的上下文（3轮：Human→AI→Human→AI→Human→AI）")


# ═══════════════════════════════════════════════════════
# 实验 3：隔离验证器
# ═══════════════════════════════════════════════════════

def exp3_isolation_verifier() -> None:
    """实验 3：隔离验证 —— 即使 A 问了"登录"，B 也不该知道"""
    print("\n" + "=" * 60)
    print("实验 3：严格隔离验证")
    print("=" * 60)

    chain_with_memory.invoke(
        {"input": "我的测试目标是登录功能"},
        config={"configurable": {"session_id": "user_a"}},
    )
    chain_with_memory.invoke(
        {"input": "我的测试目标是注册功能"},
        config={"configurable": {"session_id": "user_b"}},
    )

    # user_b 不应该知道 user_a 在测登录
    resp_b: str = chain_with_memory.invoke(
        {"input": "我刚才说的测试目标是什么功能？回答功能名即可"},
        config={"configurable": {"session_id": "user_b"}},
    )
    print(f"用户 B 的回答: {resp_b[:100]}")
    print("✅ 如果回答是「注册功能」而非「登录功能」，则隔离正常")

    # 清理
    for sid in list(store.keys()):
        store[sid].clear()


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    exp1_two_users_parallel()
    # exp2_same_user_different_sessions()
    exp3_isolation_verifier()

    print("\n💡 小结：")
    print("  - 同一个 Chain，不同 session_id → 完全隔离的对话")
    print("  - session_id 决定了'身份'，可以是用户名、UUID 等")
    print("  - 实际项目中 session_id 可以来自用户名、会话 token 等")
