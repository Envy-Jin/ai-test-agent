"""
Day 21 练习 2：CLI 骨架 —— argparse 子命令（import / query / recommend / analyze-bug）

把 Day 20 的核心引擎（KnowledgeIndexer / 两个 Chain）包装成命令行工具：
  python day21_kb_cli.py import --force              # 离线建索引（持久化落盘）
  python day21_kb_cli.py query "登录相关的历史 Bug 有哪些？" --type bug --k 3
  python day21_kb_cli.py recommend "密码连续输错5次" --k 2
  python day21_kb_cli.py analyze-bug "登录后跳转空白页"

设计原则：
  1. CLI 是"薄外壳"：不做业务逻辑，只做参数解析 + 调用引擎函数
  2. 引擎依赖注入：链的构建函数接收 indexer 参数（不依赖模块级全局单例）
  3. 索引器统一用练习 1 的 KnowledgeIndexerV2（持久化版本，重启不重建）

⚠️ Pyright 注意事项：
  - 子命令处理函数签名统一为 def handle_xxx(args: argparse.Namespace) -> None
  - args.xxx 是 Any（argparse 动态属性），用 str()/int() 显式转换后再传业务函数
  - subparsers.required = True 保证无子命令时报错而不是静默
  - LCEL 链的返回类型复杂 → 构建函数不写返回注解（让 Pyright 推断，Day 20 同款）
  - handlers 字典用 collections.abc.Callable 标注，get() 结果判空再调用

用法：命令行直接运行（见顶部示例）。
"""

import argparse
import os
import sys
from collections.abc import Callable

# Windows 下控制台/重定向输出统一 UTF-8，防止 emoji/中文打印报 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()

from pydantic import BaseModel, Field

from langchain_core.documents import Document
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
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

ALLOWED_TYPES: tuple[str, ...] = ("requirement", "test_case", "bug", "all")

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.2,
)

def get_indexer() -> KnowledgeIndexerV2:
    """CLI 统一入口：持久化索引器（首次自动建库落盘，之后从磁盘加载）。"""
    ensure_sample_data()
    indexer: KnowledgeIndexerV2 = KnowledgeIndexerV2(
        root_dir=KNOWLEDGE_DIR,
        persist_directory=CHROMA_DIR,
    )
    indexer.index()
    return indexer

def format_docs(docs: list[Document]) -> str:
    """把检索到的文档片段拼成一段文本（含类型前缀，方便 LLM 区分来源）。"""
    parts: list[str] = []
    for doc in docs:
        doc_type: str = str(doc.metadata.get("doc_type", "unknown"))
        source: str = str(doc.metadata.get("source", "unknown"))
        parts.append(f"[{doc_type} | {os.path.basename(source)}]\n{doc.page_content}")
    return "\n\n".join(parts)

# ═══════════════════════════════════════════════════════
# 引擎：问答 Chain（接收 indexer 依赖，Day 20 逻辑参数化）
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


def build_context(indexer: KnowledgeIndexerV2, q: str, doc_type: str, k: int = 3) -> str:
    """按指定类型检索并格式化（--type / --k 的核心实现）。"""
    if doc_type == "all":
        req_docs: list[Document] = indexer.search_by_type(q, DOC_TYPE_REQUIREMENT, k=k)
        bug_docs: list[Document] = indexer.search_by_type(q, DOC_TYPE_BUG, k=k)
        return format_docs(req_docs + bug_docs)
    docs: list[Document] = indexer.search_by_type(q, doc_type, k=k)
    return format_docs(docs)


def build_qa_chain(indexer: KnowledgeIndexerV2, doc_type: str = "all", k: int = 3):
    """问答 Chain（StrOutputParser，给人看的文本回答）。"""
    def _retrieve(q: str) -> str:
        return build_context(indexer, q, doc_type, k)

    return (
        {"context": _retrieve, "question": RunnablePassthrough()}
        | QA_PROMPT
        | llm
        | StrOutputParser()
    )

# ═══════════════════════════════════════════════════════
# 引擎：Bug 分析 Chain（接收 indexer 依赖，Day 20 逻辑参数化）
# ═══════════════════════════════════════════════════════

class BugAnalysis(BaseModel):
    """Bug 报告的结构化分析结果"""
    bug_summary: str = Field(description="一句话总结该 Bug")
    bug_type: str = Field(description="缺陷类型：功能缺陷/性能问题/UI问题/安全漏洞/兼容性问题")
    severity: str = Field(description="严重程度：致命/严重/一般/轻微")
    root_cause_analysis: str = Field(description="根因分析")
    test_cases_to_add: list[str] = Field(description="建议补充的测试用例标题列表")


BUG_ANALYSIS_PROMPT = ChatPromptTemplate.from_template(
    """你是一名资深测试工程师。请根据以下 Bug 报告内容生成结构化分析。

Bug 报告内容：
{context}

要求：
1. 严格基于报告内容，不要编造
2. 只输出【一个】JSON 对象，不要输出数组，不要对每条 Bug 报告分别分析
3. 输出 JSON 格式必须严格如下（test_cases_to_add 是字符串数组）：
{{
  "bug_summary": "一句话总结",
  "bug_type": "功能缺陷/性能问题/UI问题/安全漏洞/兼容性问题",
  "severity": "致命/严重/一般/轻微",
  "root_cause_analysis": "根因分析",
  "test_cases_to_add": ["建议补充的测试用例标题1", "标题2"]
}}

请只输出 JSON，不要输出任何其他文字。"""
)


def build_bug_chain(indexer: KnowledgeIndexerV2):
    """Bug 分析 Chain：检索 bug 类型 → Prompt → LLM → JSON dict。"""
    def _retrieve(q: str) -> str:
        docs: list[Document] = indexer.search_by_type(q, DOC_TYPE_BUG, k=3)
        return format_docs(docs)

    parser = JsonOutputParser()
    return (
        {"context": _retrieve, "question": RunnablePassthrough()}
        | BUG_ANALYSIS_PROMPT
        | llm
        | parser
    )


def parse_bug_analysis(raw: object) -> BugAnalysis | None:
    """把 JsonOutputParser 的输出解析为 BugAnalysis（容错 + 校验，Day 20 同款）。

    遵循项目规范：要么 raise 要么 return None（这里选 return None）。
    """
    if isinstance(raw, list):
        first: object = raw[0] if raw else None
        raw = first if isinstance(first, dict) else None
    if not isinstance(raw, dict):
        print("⚠️ 输出不是 dict（且无法从 list 提取），跳过校验")
        return None
    try:
        return BugAnalysis.model_validate(raw)
    except Exception as exc:
        print(f"⚠️ Pydantic 校验失败: {exc}")
        return None



# ═══════════════════════════════════════════════════════
# 子命令处理函数（统一签名：args -> None）
# ═══════════════════════════════════════════════════════

def handle_import(args: argparse.Namespace) -> None:
    """import：离线建索引（--force 强制重建）。"""
    ensure_sample_data()
    indexer: KnowledgeIndexerV2 = KnowledgeIndexerV2(
        root_dir=KNOWLEDGE_DIR,
        persist_directory=CHROMA_DIR,
    )
    count: int = indexer.index(force=bool(args.force))
    print(f"✅ 知识库索引就绪，共 {count} 条片段（存储于 {CHROMA_DIR}）")


def handle_query(args: argparse.Namespace) -> None:
    """query：知识库问答（--type 类型过滤，--k 返回数量）。"""
    question: str = str(args.question)
    doc_type: str = str(args.type)
    k: int = int(args.k)

    if doc_type not in ALLOWED_TYPES:
        print(f"⚠️ 无效的 --type: {doc_type}（可选: {'/'.join(ALLOWED_TYPES)}）")
        return

    indexer: KnowledgeIndexerV2 = get_indexer()
    chain = build_qa_chain(indexer, doc_type=doc_type, k=k)
    answer: str = chain.invoke(question)
    print(answer)


def handle_recommend(args: argparse.Namespace) -> None:
    """recommend：相似测试用例推荐（带相似度分数）。"""
    description: str = str(args.desc)
    k: int = int(args.k)

    indexer: KnowledgeIndexerV2 = get_indexer()
    ranked: list[tuple[Document, float]] = indexer.recommend_test_cases(description, k=k)
    if not ranked:
        print("⚠️ 没有找到相似用例")
        return

    print(f"📋 场景: {description}\n")
    for i, (doc, distance) in enumerate(ranked):
        score: float = 1.0 - min(distance, 1.0)  # 距离 → 直观相似度（0~1）
        source: str = str(doc.metadata.get("source", "unknown"))
        print(f"  [{i + 1}] 相似度 {score:.2f} | {os.path.basename(source)}")
        print(f"      {doc.page_content[:80].replace(chr(10), ' ')}...")


def handle_analyze_bug(args: argparse.Namespace) -> None:
    """analyze-bug：Bug 结构化分析（JSON 字段展示）。"""
    scene: str = str(args.text)

    indexer: KnowledgeIndexerV2 = get_indexer()
    chain = build_bug_chain(indexer)
    raw: object = chain.invoke(scene)

    analysis: BugAnalysis | None = parse_bug_analysis(raw)
    if analysis is None:
        print("❌ 解析失败")
        return

    print(f"✅ Bug 结构化分析（场景: {scene}）")
    print(f"  摘要: {analysis.bug_summary}")
    print(f"  类型: {analysis.bug_type}")
    print(f"  严重度: {analysis.severity}")
    print(f"  根因: {analysis.root_cause_analysis}")
    print(f"  建议补充用例:")
    for tc in analysis.test_cases_to_add:
        print(f"    - {tc}")


# ═══════════════════════════════════════════════════════
# argparse 解析器构建
# ═══════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    """构建 argparse 解析器：子命令 import / query / recommend / analyze-bug。"""
    parser = argparse.ArgumentParser(
        prog="kb-cli",
        description="智能测试知识库命令行工具（Day 21）",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # import：离线建索引
    p_import = subparsers.add_parser("import", help="离线构建/加载知识库索引")
    p_import.add_argument("--force", action="store_true", help="强制重建索引（忽略已有落盘数据）")

    # query：知识库问答
    p_query = subparsers.add_parser("query", help="知识库问答")
    p_query.add_argument("question", help="要问的问题")
    p_query.add_argument("--type", default="all", help="文档类型过滤: requirement/test_case/bug/all（默认 all）")
    p_query.add_argument("--k", type=int, default=3, help="检索返回数量（默认 3）")

    # recommend：相似测试用例推荐
    p_rec = subparsers.add_parser("recommend", help="相似测试用例推荐")
    p_rec.add_argument("desc", help="场景描述，如：密码连续输错5次")
    p_rec.add_argument("--k", type=int, default=3, help="推荐数量（默认 3）")

    # analyze-bug：Bug 结构化分析
    p_bug = subparsers.add_parser("analyze-bug", help="Bug 结构化分析")
    p_bug.add_argument("text", help="Bug 现象描述，如：登录后跳转空白页")

    return parser



if __name__ == "__main__":
    parser = build_parser()
    args: argparse.Namespace = parser.parse_args()

    # 子命令分发（command 由 subparsers 的 dest="command" 注入）
    handlers: dict[str, Callable[[argparse.Namespace], None]] = {
        "import": handle_import,
        "query": handle_query,
        "recommend": handle_recommend,
        "analyze-bug": handle_analyze_bug,
    }
    handler: Callable[[argparse.Namespace], None] | None = handlers.get(str(args.command))
    if handler is None:
        parser.print_help()
        sys.exit(1)  # type: ignore[reportUnreachable]
    handler(args)