"""
Day 21 练习 3：对话式问答 —— 手动记忆模式（InMemoryChatMessageHistory）

Day 20 笔记"还存在的问题"之二：对话式问答（带记忆的问答 Chain）。

⚠️ 技术选型说明（2026-08-10 联网 + 已装包源码确认）：
  你 Day 17/19 用的 RunnableWithMessageHistory 在 langchain-core 1.5.x 已被标记弃用
  （运行时报 LangChainDeprecationWarning："Use LangGraph's built-in persistence instead"，
  官方推荐 LangGraph checkpointer，Day 26 会学）。
  本练习改用【手动记忆模式】—— 手动完成 RunnableWithMessageHistory 内部做的三件事：
    ① 取历史：get_session_history(session_id)
    ② 注入历史：ChatPromptTemplate.format_messages(chat_history=history.messages, ...)
    ③ 回写新对话：history.add_user_message() / add_ai_message()
  好处：零弃用 API、代码路径一目了然、Pyright 完全可控；
  而且 LangGraph checkpointer 本质也是这套逻辑，Day 26 迁移时概念无缝衔接。

⚠️ Pyright 注意事项：
  - AIMessage.content 类型是 str | list[str | dict]，赋给 str 前必须 isinstance 收窄
  - format_messages() 返回 list[BaseMessage]（口诀 8：ChatPromptTemplate.invoke 返回基类，
    要用 format_messages 拿消息列表）
  - 历史消息容器一律 BaseMessage（口诀 4）
  - metadata 取值用 str() 显式转换（Day 20 坑 1）

用法：直接运行跑全部实验，或在 main() 中注释掉不想跑的实验函数。
"""

import os
import sys

# Windows 下控制台/重定向输出统一 UTF-8，防止 emoji/中文打印报 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()

from langchain_core.chat_history import InMemoryChatMessageHistory
from langchain_core.documents import Document
from langchain_core.messages import BaseMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from day20_knowledge_loader import (
    KNOWLEDGE_DIR,
    DOC_TYPE_BUG,
    DOC_TYPE_REQUIREMENT,
    ensure_sample_data,
)
from day21_kb_persist import KnowledgeIndexerV2



# ═══════════════════════════════════════════════════════
# 模块级：共享资源 + 配置
# ═══════════════════════════════════════════════════════

CHROMA_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.2,
)


def format_docs(docs: list[Document]) -> str:
    """把检索到的文档片段拼成一段文本（含类型前缀，与 day21_kb_cli 同款）。"""
    parts: list[str] = []
    for doc in docs:
        doc_type: str = str(doc.metadata.get("doc_type", "unknown"))
        source: str = str(doc.metadata.get("source", "unknown"))
        parts.append(f"[{doc_type} | {os.path.basename(source)}]\n{doc.page_content}")
    return "\n\n".join(parts)

# ═══════════════════════════════════════════════════════
# 对话 Prompt（历史槽位 + 上下文）
# ═══════════════════════════════════════════════════════

CHAT_PROMPT = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            "你是一名测试知识库助手。回答时遵循以下优先级：\n"
            "1. 对话历史优先：用户在第一轮明确提供的信息（如名字、偏好）直接使用，不要重复询问\n"
            "2. 知识库内容用于回答领域知识，与历史冲突时以用户最新说法为准\n"
            "3. 历史与知识库都没有相关信息时，才说明知识库中没有相关资料\n"
            "4. 回答末尾用「参考来源：」列出引用文件（如无引用可不列）\n"
            "5. 知识库上下文与问题无关时忽略它，只回答对话",
        ),
        ("placeholder", "{chat_history}"),
        ("human", "问题：{question}\n\n知识库上下文：\n{context}"),
    ]
)


def build_chat_context(question: str, indexer: KnowledgeIndexerV2) -> str:
    """按问题检索知识库（需求 + Bug 两类）并格式化为上下文。"""
    req_docs: list[Document] = indexer.search_by_type(question, DOC_TYPE_REQUIREMENT, k=2)
    bug_docs: list[Document] = indexer.search_by_type(question, DOC_TYPE_BUG, k=3)
    return format_docs(req_docs + bug_docs)


# ═══════════════════════════════════════════════════════
# 会话历史（模块级 store，多会话隔离）
# ═══════════════════════════════════════════════════════

SESSIONS: dict[str, InMemoryChatMessageHistory] = {}


def get_session_history(session_id: str) -> InMemoryChatMessageHistory:
    """按 session_id 返回会话历史（不存在则创建）。

    返回具体类型（而非基类 BaseChatMessageHistory），方便练习 4 直接
    调用 add_user_message / add_ai_message 恢复历史。
    """
    if session_id not in SESSIONS:
        SESSIONS[session_id] = InMemoryChatMessageHistory()
    return SESSIONS[session_id]


# ═══════════════════════════════════════════════════════
# 核心：chat_turn 单轮对话（手动记忆模式）
# ═══════════════════════════════════════════════════════

def chat_turn(indexer: KnowledgeIndexerV2, session_id: str, question: str) -> str:
    """单轮对话：检索 → 组装消息（历史+问题+上下文）→ LLM → 回写历史。

    手动完成 RunnableWithMessageHistory 内部做的三件事（见模块 docstring）：
      ① 取历史 → ② format_messages 注入 → ③ add_* 回写
    """
    history: InMemoryChatMessageHistory = get_session_history(session_id)
    context: str = build_chat_context(question, indexer)

    # ② 把历史（list[BaseMessage]）注入 placeholder 槽位
    messages: list[BaseMessage] = CHAT_PROMPT.format_messages(
        chat_history=history.messages,
        question=question,
        context=context,
    )
    response = llm.invoke(messages)  # AIMessage

    # ⚠️ AIMessage.content 类型是 str | list[...] → isinstance 收窄后再赋值
    # answer: str = response.content if isinstance(response.content, str) else str(response.content)
    answer: str = (
    response.content
    if isinstance(response.content, str)
    else "".join(part.get("text", "") for part in response.content if isinstance(part, dict))
    )

    # ③ 回写历史（下一轮才能"记得"）
    history.add_user_message(question)
    history.add_ai_message(answer)
    return answer


# ═══════════════════════════════════════════════════════
# 实验 1：同一 session 多轮对话（验证记忆）
# ═══════════════════════════════════════════════════════

def exp1_two_turns() -> None:
    """实验 1：同一 session 两轮问答，验证模型记得第一轮内容。"""
    print("=" * 60)
    print("实验 1：多轮对话记忆")
    print("=" * 60)

    indexer: KnowledgeIndexerV2 = KnowledgeIndexerV2(
        root_dir=KNOWLEDGE_DIR, persist_directory=CHROMA_DIR
    )
    indexer.index()

    q1: str = "登录相关的历史 Bug 有哪些？"
    print(f"\n🧑 第一轮: {q1}")
    a1: str = chat_turn(indexer, "demo-s1", q1)
    print(f"🤖 {a1}")

    q2: str = "其中最严重的是哪个？"
    print(f"\n🧑 第二轮（追问）: {q2}")
    a2: str = chat_turn(indexer, "demo-s1", q2)
    print(f"🤖 {a2}")

    print("\n💡 如果第二轮能答出「最严重」的 Bug，说明历史生效了（模型记得第一轮聊的是哪些 Bug）")


# ═══════════════════════════════════════════════════════
# 实验 2：不同 session 隔离
# ═══════════════════════════════════════════════════════

def exp2_session_isolation() -> None:
    """实验 2：不同 session_id 互不干扰。"""
    print("\n" + "=" * 60)
    print("实验 2：多会话隔离")
    print("=" * 60)

    indexer: KnowledgeIndexerV2 = KnowledgeIndexerV2(
        root_dir=KNOWLEDGE_DIR, persist_directory=CHROMA_DIR
    )
    indexer.index()

    print("\n🧑 会话 A 第一轮: 你好，我是 Alice")
    chat_turn(indexer, "demo-sA", "你好，我是 Alice")

    print("🧑 会话 A 第二轮: 我叫什么？")
    a: str = chat_turn(indexer, "demo-sA", "我叫什么？")
    print(f"🤖 {a}（预期：能答出 Alice —— 记忆生效）")

    print("\n🧑 会话 B（全新会话）: 我叫什么？")
    b: str = chat_turn(indexer, "demo-sB", "我叫什么？")
    print(f"🤖 {b}（预期：答不出 Alice —— 会话隔离生效）")


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    # ensure_sample_data()
    exp1_two_turns()
    exp2_session_isolation()

    print("\n✅ 对话式问答完成！")
    print("   手动记忆模式 = 取历史 + 注入 + 回写（RunnableWithMessageHistory 的替代）")
    print("   下一步：包成交互式 chat 子命令 + 会话历史持久化（练习 4）")
