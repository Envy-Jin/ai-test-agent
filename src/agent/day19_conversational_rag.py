"""
Day 19 练习 5：对话式 RAG（Memory + RAG 结合）⭐ 进阶产出

把 Day 17 的 RunnableWithMessageHistory 套在 RAG Chain 外面：
  - 第一轮：正常检索回答
  - 第二轮：能理解"那/它/这个"等指代（因为历史消息被注入 Prompt）

组合方式（官方推荐方案 C：包装器模式，零侵入）：
  rag_chain（内部用 RunnablePassthrough.assign 从 dict 取 question 检索）
    → 包一层 RunnableWithMessageHistory
    → 获得多轮对话能力

⚠️ Pyright 注意事项（Day 17 踩过的坑，今天再复习一遍）：
  - 装消息用 BaseMessage（不要用 HumanMessage | AIMessage 窄 union）
  - config 参数必须显式标注 RunnableConfig
  - ChatPromptTemplate.from_messages 里用 MessagesPlaceholder("chat_history")
  - invoke 时 config={"configurable": {"session_id": ...}} 会报错，必须标注类型
  - ⚠️ 输入是 dict：链的第一环必须用 RunnablePassthrough.assign 从 dict 取 question，
    不能再用 {"context": retriever | format_docs, ...}（retriever 会收到整个 dict）

用法：直接运行跑全部实验，或在 main() 中注释掉不想跑的实验函数。
"""


import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from langchain_core.runnables import RunnablePassthrough
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever

from day18_rag_retriever import RAGRetriever


# ═══════════════════════════════════════════════════════
# 模块级：共享资源
# ═══════════════════════════════════════════════════════

DOCS_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "requirements")

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.2,
)

rag: RAGRetriever = RAGRetriever(docs_dir=DOCS_DIR)

# 会话存储（Day 17 的模式：dict[session_id] -> 历史）
store: dict[str, BaseChatMessageHistory] = {}


def get_session_history(session_id: str) -> BaseChatMessageHistory:
    """按 session_id 获取会话历史（不存在则创建）。"""
    if session_id not in store:
        store[session_id] = InMemoryChatMessageHistory()
    return store[session_id]

def get_retriever(search_type: str = "similarity", k: int = 3) -> VectorStoreRetriever:
    rag.index()
    return rag.as_retriever(search_type=search_type, k=k)

def format_docs(docs: list[Document]) -> str:
    """把检索到的文档片段拼成一段文本。"""
    return "\n\n".join(doc.page_content for doc in docs)

# 带历史占位符的 RAG Prompt
CONVERSATIONAL_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """你是测试工程师。根据需求文档上下文回答问题。

需求文档上下文：
{context}

要求：只根据文档回答，文档没有的信息要明确说明。""",
    ),
    # ⚠️ 关键：聊天历史占位符（Day 17 的知识点）
    MessagesPlaceholder("chat_history"),
    ("human", "{question}"),
])

# ===== 修改点（对话式 RAG 输入结构 bug 修复）=====
# [问题] 原来的链 {"context": retriever | format_docs, "question": RunnablePassthrough()}
#        假设输入是【纯字符串】；但 RunnableWithMessageHistory 会把输入变成 dict
#        {"question": ..., "chat_history": [...]}，于是 context 键把【整个 dict】传给 retriever
#        → retriever.invoke(dict) → similarity_search(query=dict) → embed_query(dict)
#        → Gemini Embedding API 校验失败（Extra inputs / string_type，10 个 validation errors）
# [修复] 改用官方对话式 RAG 写法：RunnablePassthrough.assign(context=build_context)
#        build_context 显式从输入 dict 中取出 question 再检索；
#        assign 把 context 合并回原 dict（question + chat_history 原样保留）继续透传
#        顺带收益：assign 只有单键，无 RunnableParallel 并发
def build_rag_chain(retriever: VectorStoreRetriever):
    """对话式 RAG 链：从输入 dict 中显式取出 question 再检索。

    注意：这里的输入不是纯字符串，而是 {"question": ..., "chat_history": [...]}
    （由 RunnableWithMessageHistory 注入 chat_history），所以不能再用
    {"context": retriever | format_docs, ...} 这种"输入即 question"的映射。
    """

    def build_context(inputs: dict[str, object]) -> str:
        """从输入 dict 中取 question 并检索格式化（对话式 RAG 的输入是 dict）。"""
        question: str = str(inputs.get("question", ""))
        docs: list[Document] = retriever.invoke(question)
        return format_docs(docs)

    return (
        RunnablePassthrough.assign(context=build_context)
        | CONVERSATIONAL_PROMPT
        | llm
        | StrOutputParser()
    )

def build_conversational_rag(retriever: VectorStoreRetriever) -> RunnableWithMessageHistory:
    """给 RAG Chain 套上记忆外壳（方案 C：包装器模式）。"""
    return RunnableWithMessageHistory(
        build_rag_chain(retriever),
        get_session_history,
        input_messages_key="question",
        history_messages_key="chat_history",
    )

# ═══════════════════════════════════════════════════════
# 实验 1：多轮对话 —— 指代消解
# ═══════════════════════════════════════════════════════

def exp1_multi_turn() -> None:
    """实验 1：两轮对话，第二轮用指代词（验证记忆生效）"""
    print("=" * 60)
    print("实验 1：多轮对话 —— 指代消解")
    print("=" * 60)

    retriever: VectorStoreRetriever = get_retriever()
    conversational_rag = build_conversational_rag(retriever)

    # ⚠️ config 必须显式标注 RunnableConfig（Day 17 的坑！）
    session_config: RunnableConfig = {"configurable": {"session_id": "rag_session_1"}}

    # 第一轮
    q1: str = "登录功能支持哪些登录方式？"
    print(f"\n🧑 第 1 轮: {q1}")
    a1: str = conversational_rag.invoke({"question": q1}, config=session_config)
    print(f"🤖 回答: {a1[:100]}...")

    # 第二轮：用指代词"那/这些"
    q2: str = "那密码输错 5 次会怎么样？"
    print(f"\n🧑 第 2 轮: {q2}")
    a2: str = conversational_rag.invoke({"question": q2}, config=session_config)
    print(f"🤖 回答: {a2[:100]}...")

    print("\n💡 验证：如果第 2 轮的回答里出现了\"锁定\"\"连续失败\"等词，")
    print("   说明模型理解\"那\"指代的是\"登录功能\"，记忆生效了")

# ═══════════════════════════════════════════════════════
# 实验 2：会话隔离 —— 不同 session 互不影响
# ═══════════════════════════════════════════════════════

def exp2_session_isolation() -> None:
    """实验 2：不同 session_id 的对话互不干扰"""
    print("\n" + "=" * 60)
    print("实验 2：会话隔离")
    print("=" * 60)

    retriever: VectorStoreRetriever = get_retriever()
    conversational_rag = build_conversational_rag(retriever)

    config_a: RunnableConfig = {"configurable": {"session_id": "session_A"}}
    config_b: RunnableConfig = {"configurable": {"session_id": "session_B"}}

    # 会话 A 问登录
    conversational_rag.invoke({"question": "登录功能支持哪些登录方式？"}, config=config_a)

    # 会话 B 直接问指代 —— 应该"接不上"（因为 B 没有历史）
    q_b: str = "那密码规则是什么？"
    print(f"🧑 会话 B 第 1 问: {q_b}")
    a_b: str = conversational_rag.invoke({"question": q_b}, config=config_b)
    print(f"🤖 回答: {a_b[:120]}...")

    # 会话 A 继续追问 —— 应该能接上
    q_a: str = "密码规则呢？"
    print(f"\n🧑 会话 A 第 2 问: {q_a}")
    a_a: str = conversational_rag.invoke({"question": q_a}, config=config_a)
    print(f"🤖 回答: {a_a[:120]}...")

    print("\n💡 观察：B 的回答是\"文档里没有明确密码规则\"之类（未接上），")
    print("   A 的回答带出密码规则（接上了）→ 会话隔离生效")


# ═══════════════════════════════════════════════════════
# 实验 3：流式多轮输出
# ═══════════════════════════════════════════════════════

def exp3_stream_multi_turn() -> None:
    """实验 3：带记忆的流式输出"""
    print("\n" + "=" * 60)
    print("实验 3：带记忆的流式输出")
    print("=" * 60)

    retriever: VectorStoreRetriever = get_retriever()
    conversational_rag = build_conversational_rag(retriever)

    session_config: RunnableConfig = {"configurable": {"session_id": "rag_session_3"}}

    q1: str = "注册功能怎么校验手机号？"
    print(f"🧑 第 1 轮: {q1}")
    print("🤖 ", end="", flush=True)
    for chunk in conversational_rag.stream({"question": q1}, config=session_config):
        print(chunk, end="", flush=True)
    print("\n")

    q2: str = "格式不对会提示什么？"
    print(f"🧑 第 2 轮: {q2}")
    print("🤖 ", end="", flush=True)
    for chunk in conversational_rag.stream({"question": q2}, config=session_config):
        print(chunk, end="", flush=True)
    print("\n")


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    exp1_multi_turn()
    exp2_session_isolation()
    exp3_stream_multi_turn()

    print("\n✅ 对话式 RAG 完成！")
    print("   RunnableWithMessageHistory 包装 RAG Chain = 短期记忆 + 长期知识")
    print("   → AI 助手既能记住对话，又能查文档，这是 Day 20-21 智能知识库的基础")