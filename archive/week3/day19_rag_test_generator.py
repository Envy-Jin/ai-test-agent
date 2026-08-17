"""
Day 19 练习 3：RAG 测试用例生成器（⭐ 今日核心产出）

基于文档检索的智能测试用例生成：
  retriever（检索需求文档）→ format_docs → Prompt → LLM → JsonOutputParser → Pydantic 校验

与步骤 2 的区别：
  - 步骤 2：StrOutputParser → 文本回答（给人看）
  - 步骤 3：JsonOutputParser → dict → Pydantic TestSuite（给程序用）

⚠️ Pyright 注意事项：
  - JsonOutputParser 泛型：JsonOutputParser[pydantic 类型] 可返回已校验对象，
    但为了类型安全，这里用「parser 输出 dict → 手动 model_validate」两步走
  - Pydantic v2：model_validate() / model_dump()，不是 v1 的 parse_obj() / dict()
  - retriever | format_docs 的类型链：str → list[Document] → str，全程可推断

用法：直接运行跑全部实验，或在 main() 中注释掉不想跑的实验函数。
"""

import os
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from pydantic import BaseModel, Field
from langchain_core.exceptions import OutputParserException
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever

from day18_rag_retriever import RAGRetriever


# ═══════════════════════════════════════════════════════
# Pydantic 模型：测试用例结构（复用 Day 12-14 的设计思路）
# ═══════════════════════════════════════════════════════

class TestCase(BaseModel):
    """单个测试用例"""
    id: str = Field(description="用例编号，如 TC001")
    title: str = Field(description="用例标题")
    priority: str = Field(description="优先级：P0/P1/P2")
    type: str = Field(description="类型：功能/边界/异常")
    steps: list[str] = Field(description="操作步骤列表")
    expected: str = Field(description="预期结果")


class TestSuite(BaseModel):
    """测试套件：一个功能点的一组用例"""
    feature: str = Field(description="功能名称")
    summary: str = Field(description="根据文档对该功能的简述")
    test_cases: list[TestCase] = Field(description="测试用例列表")


# ═══════════════════════════════════════════════════════
# 模块级：共享资源
# ═══════════════════════════════════════════════════════

DOCS_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "requirements")

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.2,
)

rag: RAGRetriever = RAGRetriever(docs_dir=DOCS_DIR)


def get_retriever() -> VectorStoreRetriever:
    """建索引并返回标准检索器。"""
    rag.index()
    return rag.as_retriever(k=4)  # 测试用例生成需要更多上下文，k=4


def format_docs(docs: list[Document]) -> str:
    """把检索到的文档片段拼成一段文本。"""
    return "\n\n".join(doc.page_content for doc in docs)


# 输出 JSON 的 RAG Prompt（核心产出 🎯）
RAG_TEST_PROMPT = ChatPromptTemplate.from_messages([
    (
        "system",
        """你是一名资深软件测试工程师。请根据需求文档上下文生成测试用例。

需求文档上下文：
{context}

要求：
1. 严格基于上下文内容，不要编造文档中没有的功能
2. 测试用例覆盖：正向功能、边界条件、异常场景
3. 输出必须包含 feature 和 summary 两个顶层字段
4. steps 必须是字符串数组（list），不是单个字符串
5. 如果上下文与问题无关，test_cases 返回空列表

格式示例：
{format_instructions}

请只输出 JSON，不要输出任何其他文字。""",
    ),
    ("human", "请为「{question}」生成测试用例"),
])


def build_rag_test_chain(retriever: VectorStoreRetriever):
    """构建 RAG 测试用例生成 Chain（输出 JSON dict）。"""
    parser = PydanticOutputParser(pydantic_object=TestSuite)
    prompt = RAG_TEST_PROMPT.partial(format_instructions=parser.get_format_instructions())
    return (
        {"context": retriever | format_docs, "question": RunnablePassthrough()}
        | prompt
        | llm
        | parser
    )


# ═══════════════════════════════════════════════════════
# 实验 1：生成 JSON 测试用例（原始输出）
# ═══════════════════════════════════════════════════════

def exp1_raw_json_output() -> None:
    """实验 1：查看 JsonOutputParser 的原始输出（dict）"""
    print("=" * 60)
    print("实验 1：JsonOutputParser 原始输出")
    print("=" * 60)

    retriever: VectorStoreRetriever = get_retriever()
    chain = build_rag_test_chain(retriever)

    question: str = "登录功能"
    print(f"🔍 问题: {question}\n")

    raw: object = chain.invoke(question)
    print(f"返回类型: {type(raw).__name__}")
    print(f"返回内容:")
    print(raw)


# ═══════════════════════════════════════════════════════
# 实验 2：Pydantic 校验（核心流程）
# ═══════════════════════════════════════════════════════

def exp2_pydantic_validation() -> None:
    """实验 2：JSON → Pydantic TestSuite（干净的数据对象）"""
    print("\n" + "=" * 60)
    print("实验 2：Pydantic 校验 —— JSON → TestSuite")
    print("=" * 60)

    retriever: VectorStoreRetriever = get_retriever()
    chain = build_rag_test_chain(retriever)

    question: str = "登录功能"
    try:
        suite: TestSuite = chain.invoke(question)
    except OutputParserException:
        print(f"❌ 模型输出不符合 schema")
        return

    print(f"✅ 解析成功！功能: {suite.feature}")
    print(f"   功能简述: {suite.summary}")
    print(f"   用例数量: {len(suite.test_cases)}\n")

    for tc in suite.test_cases:
        print(f"  [{tc.id}] {tc.title}（{tc.priority}/{tc.type}）")
        print(f"      步骤: {' → '.join(tc.steps[:3])}")
        print(f"      预期: {tc.expected[:40]}...")


# ═══════════════════════════════════════════════════════
# 实验 3：多功能批量生成
# ═══════════════════════════════════════════════════════

def exp3_batch_generate() -> None:
    """实验 3：多个功能点批量生成用例，统计每个功能的用例数"""
    print("\n" + "=" * 60)
    print("实验 3：批量生成（登录/注册/结算/搜索）")
    print("=" * 60)

    retriever: VectorStoreRetriever = get_retriever()
    chain = build_rag_test_chain(retriever)

    features: list[str] = ["登录功能", "注册功能", "结算功能", "搜索功能"]

    summary: list[tuple[str, int]] = []
    for feature in features:
        try:
            suite: TestSuite = chain.invoke(feature)
        except OutputParserException:
            print(f"❌ 模型输出不符合 schema")
            summary.append((feature, 0))
            continue
        count: int = len(suite.test_cases)
        summary.append((feature, count))
        print(f"  ✅ {feature}: {count} 个用例")

    print("\n📊 汇总:")
    total: int = sum(count for _, count in summary)
    print(f"  共生成 {total} 个测试用例")
    print(f"  （每个功能点都基于对应需求文档生成，不混入其他文档内容）")


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    # exp1_raw_json_output()
    # exp2_pydantic_validation()
    exp3_batch_generate()

    print("\n✅ Day 19 核心产出完成！")
    print("   RAG 测试用例生成器 = retriever + format_docs + RAG_TEST_PROMPT")
    print("                       + llm + JsonOutputParser + TestSuite.model_validate")
    print("   效果：问「登录功能」→ 自动检索 login 文档 → 生成结构化测试用例")
