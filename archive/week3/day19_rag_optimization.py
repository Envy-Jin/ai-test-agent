"""
Day 19 练习 4：RAG 检索优化 + 来源追踪

三个实验：
  1. MMR 检索策略 vs similarity（多样性对比）
  2. 带分数检索 + 阈值过滤（只保留高质量片段）
  3. 来源追踪（回答中标注文档来源）

⚠️ Pyright 注意事项：
  - as_retriever(search_type="mmr") 返回类型与 similarity 一致
  - similarity_search_with_score() 返回 list[tuple[Document, float]]
  - 元组解包后 doc: Document, score: float，类型明确

用法：直接运行跑全部实验，或在 main() 中注释掉不想跑的实验函数。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
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

def get_retriever(search_type: str = "similarity", k: int = 3) -> VectorStoreRetriever:
    """建索引并按策略返回检索器。"""
    rag.index()
    return rag.as_retriever(search_type=search_type, k = k)


def format_docs(docs: list[Document]) -> str:
    """把检索到的文档片段拼成一段文本。"""
    return "\n\n".join(doc.page_content for doc in docs)


def source_names(docs: list[Document]) -> list[str]:
    """提取文档来源文件名列表（去重保序）。"""
    names: list[str] = []
    for doc in docs:
        name: str = os.path.basename(str(doc.metadata.get("source", "unknown")))
        if name not in names:
            names.append(name)
    return names


# ═══════════════════════════════════════════════════════
# 实验 1：MMR vs similarity 检索策略
# ═══════════════════════════════════════════════════════

def exp1_mmr_vs_similarity() -> None:
    """实验 1：对比 similarity 和 mmr 两种检索策略的返回结果"""
    print("=" * 60)
    print("实验 1：MMR vs similarity 检索策略")
    print("=" * 60)

    query: str = "登录功能的测试要求"

    for strategy in ["similarity", "mmr"]:
        retriever: VectorStoreRetriever = get_retriever(search_type=strategy, k=3)
        docs: list[Document] = retriever.invoke(query)

        print(f"\n[{strategy}] 返回 {len(docs)} 个片段:")
        for i, doc in enumerate(docs):
            preview: str = doc.page_content[:60].replace("\n", " ")
            print(f"  [{i}] {preview}...")

    print("\n💡 观察：similarity 可能返回同一文档的相邻片段（重复），")
    print("   mmr 会强制多样性，返回不同来源的片段")


# ═══════════════════════════════════════════════════════
# 实验 2：带分数检索 + 阈值过滤
# ═══════════════════════════════════════════════════════

def exp2_score_filter() -> None:
    """实验 2：检索 Top 6 → 过滤低分 → 保留高质量片段"""
    print("\n" + "=" * 60)
    print("实验 2：带分数检索 + 阈值过滤")
    print("=" * 60)

    rag.index()

    query: str = "手机号验证规则"
    print(f"查询: {query}\n")

    # 取 Top 6 的 (Document, distance)
    results: list[tuple[Document, float]] = rag.search_with_scores(query, k=6)

    print("Top 6（distance 越小越相关）:")
    for doc, score in results:
        preview: str = doc.page_content[:50].replace("\n", " ")
        print(f"  score={score:.4f} | {preview}...")

    # 过滤：distance > 1.0 视为低质量（Chroma 默认 L2 距离）
    threshold: float = 1.0
    filtered: list[Document] = [doc for doc, score in results if score <= threshold]

    print(f"\n过滤（distance <= {threshold}）后保留 {len(filtered)} 个片段:")
    for doc in filtered:
        preview_short: str = doc.page_content[:50].replace("\n", " ")
        print(f"  ✅ {preview_short}...")

    print(f"\n💡 阈值过滤的思路：先多取（k=6）再过滤，比直接 k=3 更稳")



# ═══════════════════════════════════════════════════════
# 实验 3：来源追踪 —— 回答中标注出处
# ═══════════════════════════════════════════════════════

def exp3_source_tracking() -> None:
    """实验 3：RAG Chain + 来源标注"""
    print("\n" + "=" * 60)
    print("实验 3：来源追踪 —— 回答中标注出处")
    print("=" * 60)

    # 带"来源清单"的 Prompt：把文件名列表也塞进上下文
    source_prompt = ChatPromptTemplate.from_template(
        """你是测试工程师。根据以下需求文档回答，并在回答末尾列出引用的文档。

需求文档上下文：
{context}

可用文档：{sources}

问题：{question}

要求：回答末尾用「参考文档：」列出实际引用的文档名。""",
    )

    rag.index()

    chain = (
        {
            "context": lambda q: format_docs(get_retriever().invoke(q)),
            "sources": lambda q: ", ".join(source_names(get_retriever().invoke(q))),
            "question": RunnablePassthrough(),
        }
        | source_prompt
        | llm
        | StrOutputParser()
    )

    # ⚠️ Pyright 提示：lambda 的 q 参数类型是 Unknown。
    #   这里 Lambda 只做透传+调用，运行无误；如需严格类型，
    #   可改用具名函数（见下方 build_source_context）。
    question: str = "结算功能支持哪些支付方式？"
    print(f"🔍 问题: {question}")
    answer: str = chain.invoke(question)
    print(f"🤖 回答:\n{answer}")


# def build_source_context(q: str) -> str:
#     """具名函数版：检索 + 格式化 + 来源（类型完全明确，Pyright 友好）。"""
#     docs: list[Document] = get_retriever().invoke(q)
#     return format_docs(docs)


# def build_sources(q: str) -> str:
#     """具名函数版：返回来源文件名列表的文本。"""
#     docs: list[Document] = get_retriever().invoke(q)
#     return ", ".join(source_names(docs))

# ===== 修改点（并发修复 · 方案 2：context/sources 合并为一次检索）=====
# [修改前] build_source_context 和 build_sources 各自调用 get_retriever() 检索一次：
#          - 浪费一次向量查询
#          - 放在 RunnableParallel 字典里时两个函数并发执行，首次还会并发初始化 Chroma
# [修改后] 合并成一个 build_inputs：检索一次，同时产出 context 文本、sources 文本、
#          question 原样透传，直接作为 Prompt 的完整输入 dict → 链中不再有 RunnableParallel 并发
def build_inputs(q: str) -> dict[str, str]:
    """检索一次，同时产出 context 和 sources（并发安全 + 省一次向量查询）。

    返回的 dict 正好就是 source_prompt 需要的三个变量：context / sources / question。
    """
    docs: list[Document] = get_retriever().invoke(q)
    return {
        "context": format_docs(docs),
        "sources": ", ".join(source_names(docs)),
        "question": q,
    }


def exp3_source_tracking_named() -> None:
    """实验 3b：来源追踪（具名函数版，Pyright 零警告）"""
    print("\n" + "=" * 60)
    print("实验 3b：来源追踪 —— 具名函数版")
    print("=" * 60)

    source_prompt = ChatPromptTemplate.from_template(
        """你是测试工程师。根据以下需求文档回答，并在回答末尾列出引用的文档。

需求文档上下文：
{context}

可用文档：{sources}

问题：{question}

要求：回答末尾用「参考文档：」列出实际引用的文档名。""",
    )

    rag.index()

    chain = (
        build_inputs
        | source_prompt
        | llm
        | StrOutputParser()
    )

    question: str = "注册功能如何校验手机号？"
    print(f"🔍 问题: {question}")
    answer: str = chain.invoke(question)
    print(f"🤖 回答:\n{answer}")

    print("\n💡 具名函数 vs lambda：功能相同，但具名函数参数类型明确，")
    print("   Pyright 不会报 Unknown，推荐在 Chain 中使用具名函数")

# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════



if __name__ == "__main__":
    # exp1_mmr_vs_similarity()
    # exp2_score_filter()
    exp3_source_tracking_named()

    print("\n💡 小结：")
    print("  - mmr 检索 → 结果更多样，避免重复片段")
    print("  - 分数过滤 → 先多取再过滤，提升质量")
    print("  - 来源追踪 → 回答可溯源，方便核对")
    print("  - Chain 中的处理函数推荐用具名函数（Pyright 友好）")
