"""
Day 20 练习 4：生成层 —— 知识库问答 Chain + Bug 分析 Chain（⭐ 今日核心产出）

两个生产级 Chain：
  1. 问答 Chain（StrOutputParser）：
     "登录相关的历史 Bug 有哪些？" → 基于 bugs 类型检索 → 文本回答 + 来源标注
  2. Bug 分析 Chain（JsonOutputParser + Pydantic）：
     检索 Bug 报告 → 结构化分析（bug_summary / severity / root_cause / 建议用例）

⚠️ Pyright 注意事项：
  - format_docs 标注 list[Document] -> str
  - Chain 内处理逻辑用具名函数（不用 lambda）
  - JsonOutputParser 输出 dict → 手动 Pydantic model_validate（两步走）
  - Optional[BugAnalysis] 用 if is not None 收窄
  - Prompt 中 JSON 示例花括号必须双写 {{ }}（ChatPromptTemplate 转义）

用法：直接运行跑全部实验，或在 main() 中注释掉不想跑的实验函数。
"""

import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from langchain_core.exceptions import OutputParserException
from pydantic import BaseModel, Field

from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import JsonOutputParser, PydanticOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.documents import Document

from day20_knowledge_loader import DOC_TYPE_BUG, DOC_TYPE_REQUIREMENT, ensure_sample_data
from day20_type_aware_search import KnowledgeIndexer, get_indexer


# ═══════════════════════════════════════════════════════
# Pydantic 模型：Bug 结构化分析
# ═══════════════════════════════════════════════════════

class BugAnalysis(BaseModel):
    """Bug 报告的结构化分析结果"""
    bug_summary: str = Field(description="一句话总结该 Bug")
    bug_type: str = Field(description="缺陷类型：功能缺陷/性能问题/UI问题/安全漏洞/兼容性问题")
    severity: str = Field(description="严重程度：致命/严重/一般/轻微")
    root_cause_analysis: str = Field(description="根因分析")
    test_cases_to_add: list[str] = Field(description="建议补充的测试用例标题列表")


# ═══════════════════════════════════════════════════════
# 模块级：共享资源（所有实验共用）
# ═══════════════════════════════════════════════════════

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.2,
    # google_api_key 自动从环境变量读取
)


def format_docs(docs: list[Document]) -> str:
    """把检索到的文档片段拼成一段文本（含类型前缀，方便 LLM 区分来源）。"""
    parts: list[str] = []
    for doc in docs:
        doc_type: str = str(doc.metadata.get("doc_type", "unknown"))
        source: str = str(doc.metadata.get("source", "unknown"))
        parts.append(f"[{doc_type} | {os.path.basename(source)}]\n{doc.page_content}")
    return "\n\n".join(parts)

# ═══════════════════════════════════════════════════════
# Chain 1：知识库问答 Chain（带来源标注）
# ═══════════════════════════════════════════════════════

QA_PROMPT = ChatPromptTemplate.from_template(
    """你是一名测试知识库助手。请根据以下知识库内容回答问题。

知识库上下文：
{context}

问题：
{question}

要求：
1. 只根据知识库内容回答，不要编造
2. 区分信息来源类型（需求/历史用例/Bug 报告）
3. 回答末尾用「参考来源：」列出引用文件
4. 如果知识库中没有相关信息，请明确说明
"""
)


def build_context(q: str) -> str:
    """检索全部类型文档并格式化为上下文（具名函数，Pyright 友好）。"""
    indexer: KnowledgeIndexer = get_indexer()
    docs: list[Document] = indexer.search_by_type(q, DOC_TYPE_REQUIREMENT, k=2)
    bug_docs: list[Document] = indexer.search_by_type(q, DOC_TYPE_BUG, k=3)
    return format_docs(docs + bug_docs)


def build_qa_chain():
    """问答 Chain：检索（需求+bug）→ Prompt → LLM → 纯文本。"""
    return (
        {"context": build_context, "question": RunnablePassthrough()}
        | QA_PROMPT
        | llm
        | StrOutputParser()
    )

# ═══════════════════════════════════════════════════════
# Chain 2：Bug 分析 Chain（结构化输出）
# ═══════════════════════════════════════════════════════

BUG_ANALYSIS_PROMPT = ChatPromptTemplate.from_template(
    """你是一名资深测试工程师。请根据以下 Bug 报告内容生成结构化分析。

Bug 报告内容：
{context}

要求：
1. 严格基于报告内容，不要编造
2. 输出 JSON 格式必须严格如下（test_cases_to_add 是字符串数组）：
{format_instructions}

请只输出 JSON，不要输出任何其他文字。"""
)


def build_bug_context(q: str) -> str:
    """只检索 Bug 类型文档并格式化为上下文。"""
    indexer: KnowledgeIndexer = get_indexer()
    docs: list[Document] = indexer.search_by_type(q, DOC_TYPE_BUG, k=3)
    return format_docs(docs)


def parse_bug_analysis(raw: object) -> Optional[BugAnalysis]:
    """把 JsonOutputParser 的输出解析为 BugAnalysis（容错 + 校验）。

    遵循项目规范：要么 raise 要么 return None（这里选 return None）。
    """
    if not isinstance(raw, dict):
        print("⚠️ 输出不是 dict，跳过校验")
        return None
    try:
        analysis: BugAnalysis = BugAnalysis.model_validate(raw)
        return analysis
    except Exception as exc:
        print(f"⚠️ Pydantic 校验失败: {exc}")
        return None


def build_bug_chain():
    """Bug 分析 Chain：检索 bug 类型 → Prompt → LLM → JSON dict。"""
    # parser = JsonOutputParser()
    parser = PydanticOutputParser(pydantic_object=BugAnalysis)
    prompt = BUG_ANALYSIS_PROMPT.partial(format_instructions=parser.get_format_instructions())
    return (
        {"context": build_bug_context, "question": RunnablePassthrough()}
        | prompt
        | llm
        | parser
    )

# ═══════════════════════════════════════════════════════
# 实验 1：知识库问答
# ═══════════════════════════════════════════════════════

def exp1_qa() -> None:
    """实验 1：问答 Chain —— 问知识库里的内容"""
    print("=" * 60)
    print("实验 1：知识库问答")
    print("=" * 60)

    chain = build_qa_chain()

    question: str = "登录相关的历史 Bug 有哪些？"
    print(f"🔍 问题: {question}\n")

    answer: str = chain.invoke(question)
    print(f"🤖 回答:\n{answer}")

    print("\n💡 注意回答末尾的「参考来源：」—— 知识库回答可溯源")


# ═══════════════════════════════════════════════════════
# 实验 2：Bug 分析（结构化输出）
# ═══════════════════════════════════════════════════════

def exp2_bug_analysis() -> None:
    """实验 2：Bug 分析 Chain —— 检索到 Bug 报告后输出结构化分析"""
    print("\n" + "=" * 60)
    print("实验 2：Bug 分析（结构化输出）")
    print("=" * 60)

    chain = build_bug_chain()

    question: str = "登录后跳转空白页"
    try:
        analysis: BugAnalysis = chain.invoke(question)
    except OutputParserException:
        print(f"❌ 模型输出不符合 schema")
        return
    print(f"🔍 场景: {question}")
    print(f"原始输出类型: {type(analysis).__name__}\n")
    print(f"原始输出: {analysis}")
    # analysis: Optional[BugAnalysis] = parse_bug_analysis(raw)
    # if analysis is None:
    #     print("❌ 解析失败")
    #     return

    print(f"✅ 结构化分析结果：")
    print(f"  摘要: {analysis.bug_summary}")
    print(f"  类型: {analysis.bug_type}")
    print(f"  严重度: {analysis.severity}")
    print(f"  根因: {analysis.root_cause_analysis}")
    print(f"  建议补充用例:")
    for tc in analysis.test_cases_to_add:
        print(f"    - {tc}")


# ═══════════════════════════════════════════════════════
# 实验 3：流式输出问答
# ═══════════════════════════════════════════════════════

def exp3_stream_qa() -> None:
    """实验 3：问答 Chain 流式输出（chunk 是 str，直接打印）"""
    print("\n" + "=" * 60)
    print("实验 3：问答 Chain 流式输出")
    print("=" * 60)

    chain = build_qa_chain()

    print("🔍 问题: 密码输错会被锁定吗？")
    print("🤖 ", end="", flush=True)
    for chunk in chain.stream("密码输错会被锁定吗？"):
        print(chunk, end="", flush=True)
    print("\n")


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    # ensure_sample_data()
    # exp1_qa()
    exp2_bug_analysis()
    # exp3_stream_qa()

    print("\n✅ Day 20 核心产出完成！")
    print("   问答 Chain（给人看）+ Bug 分析 Chain（给程序用）")
    print("   知识库核心引擎 = 导入 → 检索 → 生成 全流程跑通")
    print("   Day 21 将把这些 Chain 包装成命令行工具")