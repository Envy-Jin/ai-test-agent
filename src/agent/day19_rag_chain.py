"""
Day 19 练习 2：标准 RAG Chain（⭐ 今日第一个可运行的 RAG 应用）

把 Day 18 的 RAGRetriever 接入 LCEL 链条，实现「检索 → 格式化 → Prompt → LLM → 解析」。

数据流：
  {"context": retriever | format_docs, "question": RunnablePassthrough()}
  | rag_prompt | llm | StrOutputParser()

⚠️ Pyright 注意事项：
  - format_docs 参数标注 list[Document]，返回 str
  - retriever.invoke() 返回 list[Document]，类型明确
  - StrOutputParser 输出 str，无 None 问题
  - llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite")
    （google_api_key 不显式传，依赖环境变量，避免 Pyright + Pydantic 签名冲突）

用法：直接运行跑全部实验，或在 main() 中注释掉不想跑的实验函数。
"""

import os
import sys

# 让脚本能 import 同目录的 day18_rag_retriever
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
# 模块级：共享资源（所有实验共用）
# ═══════════════════════════════════════════════════════

DOCS_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "requirements")

# LLM：gemini-3.1-flash-lite（Day 15+ 一直在用的模型）
llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.2,
    # google_api_key 自动从环境变量 GOOGLE_API_KEY / GEMINI_API_KEY 读取
)

# RAG 检索器（复用 Day 18 的封装）
rag: RAGRetriever = RAGRetriever(docs_dir=DOCS_DIR)

def get_retriever() -> VectorStoreRetriever:
    """建索引并返回标准检索器（懒加载：第一次调用时建索引）。"""
    rag.index()
    return rag.as_retriever(k=3)

def format_docs(docs: list[Document]) -> str:
    """把检索到的文档片段拼成一段文本。"""
    return "\n\n".join(doc.page_content for doc in docs)

# RAG Prompt：核心是「先给上下文，再问问题，禁止编造」
RAG_PROMPT_TEMPLATE = ChatPromptTemplate.from_template(
    """你是一名资深软件测试工程师。请根据以下需求文档内容回答问题。

需求文档上下文：
{context}

问题：
{question}

要求：
1. 只根据上面的文档内容回答，不要编造文档中没有的信息
2. 如果文档中没有相关信息，请明确说明"根据现有文档无法回答该问题"
3. 回答要具体、完整，直接列出测试要点
"""
)

def build_rag_chain(retriever: VectorStoreRetriever):
    """构建标准 RAG Chain（LCEL 一条链）。"""
    return (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | RAG_PROMPT_TEMPLATE
        | llm
        | StrOutputParser()
    )


# ═══════════════════════════════════════════════════════
# 实验 1：基础 RAG 问答
# ═══════════════════════════════════════════════════════

def exp1_basic_rag_qa() -> None:
    """实验 1：构建 RAG Chain 并回答测试相关问题"""
    print("=" * 60)
    print("实验 1：基础 RAG 问答")
    print("=" * 60)

    retriever: VectorStoreRetriever = get_retriever()
    rag_chain = build_rag_chain(retriever)

    questions: list[str] = [
        "登录功能需要测试哪些测试点？",
        "注册功能的密码规则是什么？",
    ]

    for question in questions:
        print(f"\n🔍 问题: {question}")
        answer: str = rag_chain.invoke(question)
        print(f"🤖 回答:\n{answer}")
        print("-" * 60)


# ═══════════════════════════════════════════════════════
# 实验 2：文档中没有的内容（验证"不编造"）
# ═══════════════════════════════════════════════════════

def exp2_out_of_context() -> None:
    """实验 2：问文档之外的问题，验证模型不乱编"""
    print("=" * 60)
    print("实验 2：文档之外的问题（验证不编造）")
    print("=" * 60)

    retriever: VectorStoreRetriever = get_retriever()
    rag_chain = build_rag_chain(retriever)

    question: str = "2026年世界杯在哪里举办？"
    print(f"🔍 问题: {question}（文档中不存在此信息）")
    print(f"🤖 回答:")
    answer: str = rag_chain.invoke(question)
    print(answer)

    print("\n💡 对比：如果不加 RAG，直接问 LLM 它会凭训练数据回答；")
    print("   加了 RAG 后，Prompt 明确要求'只根据文档回答'，模型会如实说不知道")

# ═══════════════════════════════════════════════════════
# 实验 3：流式输出
# ═══════════════════════════════════════════════════════

def exp3_stream_output() -> None:
    """实验 3：chain.stream() 流式输出（逐 token 打印）"""
    print("=" * 60)
    print("实验 3：流式输出（chain.stream()）")
    print("=" * 60)

    retriever: VectorStoreRetriever = get_retriever()
    rag_chain = build_rag_chain(retriever)

    print("🔍 问题: 结算功能要测什么？")
    print("🤖 流式回答: ", end="", flush=True)

    # ⚠️ 注意：RAG Chain 的流式输出是 str chunk（不是 SDK 的 GenerateContentResponse）
    #   所以不需要 safe_text()，直接打印即可
    for chunk in rag_chain.stream("结算功能要测什么？"):
        assert isinstance(chunk, str), f"chunk 类型应为 str，实际: {type(chunk)}"
        print(chunk, end="", flush=True)

    print("\n" + "-" * 60)
    print("💡 流式输出的 chunk 都是 str，Pyright 不会报 None 错误")


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    # exp1_basic_rag_qa()
    exp2_out_of_context()
    # exp3_stream_output()

    # print("\n✅ RAG Chain 构建完成！")
    # print("   rag_chain = {\"context\": retriever | format_docs, \"question\": RunnablePassthrough()}")
    # print("              | rag_prompt | llm | StrOutputParser()")
    # print("   下一步：让 RAG Chain 输出结构化 JSON 测试用例")
