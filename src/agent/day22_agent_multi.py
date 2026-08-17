"""
Day 22 练习 4：多工具 Agent + 流式观察

三个能力：
  1. 多工具箱：搜索（联网）+ 状态统计（本地）+ 知识库查询（复用 Day 20-21 引擎）
  2. 观察模型怎么"选工具"（docstring 匹配）
  3. agent.stream(stream_mode="updates") 实时观察每步决策（替代旧 verbose=True）

⚠️ Pyright 注意事项：
  - stream(chunk) 的 chunk 是 object → isinstance(dict) 校验后再取值
  - 知识库工具内部复用 KnowledgeIndexerV2（Day 21 持久化版，重启不重建）
  - updates 模式下 chunk 结构: {节点名: {"messages": [增量消息]}}，逐层校验

用法：直接运行（实验 1 涉及 LLM + 联网；知识库工具首次运行会自动建索引）。
"""

import os
import sys

# Windows 下控制台/重定向输出统一 UTF-8，防止 emoji/中文打印报 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()

from langchain.agents import create_agent
from langchain_core.documents import Document
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool, tool
from langchain_google_genai import ChatGoogleGenerativeAI

from day20_knowledge_loader import (
    DOC_TYPE_BUG,
    DOC_TYPE_REQUIREMENT,
    KNOWLEDGE_DIR,
    ensure_sample_data,
)
from day21_kb_persist import KnowledgeIndexerV2
from day22_ddg_search import duckduckgo_search
from day22_first_agent import message_text
from day22_tool_basics import count_status

# ═══════════════════════════════════════════════════════
# 模块级配置
# ═══════════════════════════════════════════════════════

CHROMA_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.2,
)

# ═══════════════════════════════════════════════════════
# 工具 3：知识库查询（包装 Day 20-21 的知识库引擎）
# ═══════════════════════════════════════════════════════

# 模块级惰性索引器（首次调用工具时才建索引/加载；Day 21 持久化版）
_kb_indexer: KnowledgeIndexerV2 | None = None


def _get_indexer() -> KnowledgeIndexerV2:
    """懒加载知识库索引器（全局一次，避免每个工具调用都重建）。"""
    global _kb_indexer
    if _kb_indexer is None:
        ensure_sample_data()
        idx: KnowledgeIndexerV2 = KnowledgeIndexerV2(
            root_dir=KNOWLEDGE_DIR, persist_directory=CHROMA_DIR
        )
        idx.index()
        _kb_indexer = idx
    return _kb_indexer


@tool
def kb_search(question: str) -> str:
    """查询项目内部测试知识库（含需求文档、历史测试用例、Bug 报告）。
    当问题涉及本项目的测试知识（如历史 Bug 的处理、需求细节、已有用例）时使用。
    不要用它查询公开网络信息（网络信息请用 duckduckgo_search）。"""
    indexer: KnowledgeIndexerV2 = _get_indexer()
    req_docs: list[Document] = indexer.search_by_type(question, DOC_TYPE_REQUIREMENT, k=2)
    bug_docs: list[Document] = indexer.search_by_type(question, DOC_TYPE_BUG, k=3)

    parts: list[str] = []
    for doc in req_docs + bug_docs:
        doc_type: str = str(doc.metadata.get("doc_type", "unknown"))
        source: str = str(doc.metadata.get("source", "unknown"))
        parts.append(f"[{doc_type} | {os.path.basename(source)}]\n{doc.page_content}")
    if not parts:
        return "知识库中没有找到相关内容"
    return "\n\n".join(parts)


# ═══════════════════════════════════════════════════════
# 构建：多工具 Agent
# ═══════════════════════════════════════════════════════

def build_multi_tool_agent():
    """三个工具的测试助手：联网搜索 / 本地统计 / 内部知识库。"""
    return create_agent(
        model=llm,
        tools=[duckduckgo_search, count_status, kb_search],
        system_prompt=(
            "你是一名资深测试工程师的 AI 助手，可以使用多个工具完成任务。\n"
            "工具选择规则：\n"
            "1. 涉及最新公开信息（新版本/新闻）→ duckduckgo_search\n"
            "2. 涉及本项目内部知识（历史 Bug/需求/已有用例）→ kb_search\n"
            "3. 需要统计测试结果状态数量 → count_status\n"
            "4. 用中文回答，基于工具返回的真实结果，不要编造"
        ),
    )


# ═══════════════════════════════════════════════════════
# 辅助：从 updates 流提取增量消息
# ═══════════════════════════════════════════════════════

def extract_update_messages(chunk: object) -> list[BaseMessage]:
    """从 stream(updates) 的 chunk 中提取消息（isinstance 逐层校验）。"""
    if not isinstance(chunk, dict):
        return []
    messages: list[BaseMessage] = []
    for node_update in chunk.values():
        if not isinstance(node_update, dict):
            continue
        msgs_obj: object = node_update.get("messages", [])
        if isinstance(msgs_obj, list):
            for m in msgs_obj:
                if isinstance(m, BaseMessage):
                    messages.append(m)
    return messages


# ═══════════════════════════════════════════════════════
# 实验 1：流式观察 —— 问题 1 走知识库（不该联网）
# ═══════════════════════════════════════════════════════

def exp1_kb_stream() -> None:
    """实验 1：stream(updates) 实时观察工具选择（知识库问题）。"""
    print("=" * 60)
    print("实验 1：流式观察（知识库问题 → 预期选 kb_search）")
    print("=" * 60)

    agent = build_multi_tool_agent()
    question: str = "我们项目里登录相关的历史 Bug 有哪些？"
    config: RunnableConfig = {"recursion_limit": 25}

    print(f"\n🧑 问题: {question}\n")
    final_answer: str = ""
    for chunk in agent.stream(
        {"messages": [HumanMessage(content=question)]},
        config=config,
        stream_mode="updates",
    ):
        for msg in extract_update_messages(chunk):
            if isinstance(msg, HumanMessage):
                continue  # updates 流里一般不含原始问题，防御性跳过
            elif isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    print(f"  🤔 [决策] 调用 {str(tc.get('name', ''))} 参数: {tc.get('args', {})}")
            elif isinstance(msg, ToolMessage):
                print(f"  👀 [观察] {message_text(msg)[:60]}...")
            elif isinstance(msg, AIMessage):
                final_answer = message_text(msg)
                print("  🤖 [最终回答生成完毕]")

    print(f"\n🎯 回答预览: {final_answer[:150]}...")
    print("💡 预期：模型选 kb_search（内部知识），而不是 duckduckgo_search")


# ═══════════════════════════════════════════════════════
# 实验 2：本地统计（选 count_status，零网络依赖）
# ═══════════════════════════════════════════════════════

def exp2_count_stream() -> None:
    """实验 2：统计问题 → 预期选 count_status（本地工具）。"""
    print("\n" + "=" * 60)
    print("实验 2：统计问题 → 预期选 count_status")
    print("=" * 60)

    agent = build_multi_tool_agent()
    question: str = (
        "帮我把这轮回归的结果统计一下：pass, pass, fail, skip, pass, fail。"
        "各状态多少条？通过率是多少？"
    )
    config: RunnableConfig = {"recursion_limit": 25}

    print(f"\n🧑 问题: {question}\n")
    final_answer: str = ""
    for chunk in agent.stream(
        {"messages": [HumanMessage(content=question)]},
        config=config,
        stream_mode="updates",
    ):
        for msg in extract_update_messages(chunk):
            if isinstance(msg, AIMessage) and msg.tool_calls:
                for tc in msg.tool_calls:
                    print(f"  🤔 [决策] 调用 {str(tc.get('name', ''))} 参数: {tc.get('args', {})}")
            elif isinstance(msg, AIMessage):
                final_answer = message_text(msg)

    print(f"\n🎯 回答预览: {final_answer[:200]}...")
    print("💡 预期：模型把状态列表作为参数传给 count_status，再基于结果算通过率")


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    # exp1_kb_stream()
    exp2_count_stream()

    print("\n✅ 多工具 Agent 完成！")
    print("   模型按 docstring 匹配选工具；stream(updates) 看每步决策")
    print("   知识库从『链里写死的检索』升级为『Agent 自主调用的工具』")
