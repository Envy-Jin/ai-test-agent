"""
Day 24 练习 3：完整测试用例生成 Agent（结构化输出 + 工具链）

场景闭环：
  用户提需求 → Agent 先查知识库历史用例（kb_search）→ 生成新用例（generate_test_cases）
  → 分析关联 Bug（analyze_bug_report）→ 新用例入库（kb_import）→ 最终输出 TestCaseBundle

产出：result["structured_response"] 直接是 TestCaseBundle（Pydantic 嵌套模型），
  无需 JsonOutputParser / json_extractor 清洗（对比 Day 16/23 的脆弱解析）。

⚠️ Pyright 注意事项：
  - result["structured_response"] 取值是 object → isinstance 收窄（extract_bundle）
  - agent.stream 的 chunk 是 object → 逐层 isinstance 校验（Day 22 模式）
  - @tool 产物类型是 BaseTool（不是 StructuredTool）→ 工具列表注解用 list[BaseTool]

用法：python day24_case_agent.py
"""

import os
import sys
from typing import Literal

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()

from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy
from langchain_core.documents import Document
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from day20_knowledge_loader import (
    DOC_TYPE_BUG,
    DOC_TYPE_REQUIREMENT,
    KNOWLEDGE_DIR,
    ensure_sample_data,
)
from day21_kb_persist import KnowledgeIndexerV2
from day23_case_tools import analyze_bug_report, generate_test_cases, run_api_test
from day24_kb_upsert import KnowledgeUpserter, kb_import


# ═══════════════════════════════════════════════════════
# 模块级配置
# ═══════════════════════════════════════════════════════

CHROMA_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.2,
)

# ═══════════════════════════════════════════════════════
# 输出 Schema：嵌套 Pydantic（结构化输出的"模具"）
# ═══════════════════════════════════════════════════════

class TestCaseItem(BaseModel):
    """单条测试用例。"""
    id: str = Field(description="用例编号，如 TC001")
    title: str = Field(description="用例标题，一句话描述验证点")
    priority: Literal["P0", "P1", "P2"] = Field(description="优先级：P0 核心流程，P1 重要，P2 一般")
    case_type: Literal["功能", "边界", "异常"] = Field(description="用例类型")
    steps: list[str] = Field(description="操作步骤，按顺序")
    expected: str = Field(description="预期结果")


class TestCaseBundle(BaseModel):
    """一整套测试用例（练习 3 的最终结构化输出）。"""
    feature: str = Field(description="被测功能模块名")
    summary: str = Field(description="总体说明：覆盖了哪些测试点")
    test_cases: list[TestCaseItem] = Field(description="测试用例列表")


# ═══════════════════════════════════════════════════════
# 知识库工具（复用 Day 22 模式 + 今天修复的 upsert）
# ═══════════════════════════════════════════════════════

_kb_indexer: KnowledgeIndexerV2 | None = None
_kb_upserter: KnowledgeUpserter | None = None


def _get_indexer() -> KnowledgeIndexerV2:
    """懒加载知识库索引器（全局一次，避免每个工具调用都重建）。"""
    global _kb_indexer, _kb_upserter
    if _kb_indexer is None:
        ensure_sample_data()
        idx: KnowledgeIndexerV2 = KnowledgeIndexerV2(
            root_dir=KNOWLEDGE_DIR, persist_directory=CHROMA_DIR
        )
        idx.index()
        _kb_indexer = idx
        _kb_upserter = KnowledgeUpserter(idx)
    return _kb_indexer


def _get_kb_upserter() -> KnowledgeUpserter:
    """懒加载 upsert 器（与 indexer 同实例）。"""
    _get_indexer()
    if _kb_upserter is None:
        raise RuntimeError("upserter 初始化失败")
    return _kb_upserter


def _kb_search_docs(question: str) -> str:
    """检索需求 + Bug 两类文档，格式化为文本（kb_search 工具内部逻辑）。"""
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
# 知识库查询工具
# ═══════════════════════════════════════════════════════

@tool
def kb_search(question: str) -> str:
    """查询项目内部测试知识库（含需求文档、历史测试用例、Bug 报告）。
    当问题涉及本项目的测试知识（如历史 Bug 的处理、需求细节、已有用例）时使用。"""
    return _kb_search_docs(question)

# ═══════════════════════════════════════════════════════
# Agent 构建
# ═══════════════════════════════════════════════════════

def build_case_agent():
    """完整测试用例生成 Agent：5 个工具 + ToolStrategy(TestCaseBundle)。"""
    return create_agent(
        model=llm,
        tools=[generate_test_cases, analyze_bug_report, run_api_test, kb_search, kb_import],
        system_prompt=(
            "你是一名资深软件测试工程师的 AI 助手，负责生成结构化的测试用例。\n"
            "工作流程：\n"
            "1. 如果需求涉及本项目历史知识（历史用例/Bug/需求细节），先用 kb_search 查询参考\n"
            "2. 用 generate_test_cases 生成用例（需求文本较长时）\n"
            "3. 如果用户提到 Bug，用 analyze_bug_report 分析\n"
            "4. 如果用户给了接口地址，可以用 run_api_test 实测\n"
            "5. 用户提供新文档需要入库时，用 kb_import\n"
            "最后：把完整的测试用例整理进 TestCaseBundle 输出（feature 用需求的功能名）"
        ),
        response_format=ToolStrategy(TestCaseBundle),
    )


# ═══════════════════════════════════════════════════════
# 辅助：提取结构化响应
# ═══════════════════════════════════════════════════════

def extract_bundle(result: dict[str, object]) -> TestCaseBundle | None:
    """从 invoke 结果提取 TestCaseBundle（dict 取值是 object，isinstance 收窄）。"""
    raw: object = result.get("structured_response")
    if isinstance(raw, TestCaseBundle):
        return raw
    return None


# ═══════════════════════════════════════════════════════
# 实验
# ═══════════════════════════════════════════════════════

def exp1_generate_direct() -> None:
    """实验 1：不查知识库，直接生成用例（结构化输出）。"""
    print("=" * 60)
    print("实验 1：直接生成登录功能测试用例（结构化输出）")
    agent = build_case_agent()
    result: dict[str, object] = agent.invoke(
        {"messages": [HumanMessage(content="为登录功能生成测试用例：手机号+密码登录，密码不少于8位")]}
    )
    bundle: TestCaseBundle | None = extract_bundle(result)
    if bundle is None:
        print("❌ 未拿到结构化响应")
        return
    print(f"✅ feature={bundle.feature}")
    print(f"   summary={bundle.summary}")
    for tc in bundle.test_cases:
        # print(f"   {tc.id} [{tc.priority}/{tc.case_type}] {tc.title} → {tc.expected}")
        print(f"{tc.model_dump_json(indent=2)}")


def exp2_generate_with_kb() -> None:
    """实验 2：先查知识库历史，再生成用例（Agentic RAG 完整版）。"""
    print("=" * 60)
    print("实验 2：查知识库历史用例后生成（Agent 自主决定检索）")
    agent = build_case_agent()
    result: dict[str, object] = agent.invoke(
        {"messages": [HumanMessage(content="为登录功能生成测试用例，注意参考知识库里已有的登录相关 Bug 和需求")]}
    )
    bundle: TestCaseBundle | None = extract_bundle(result)
    if bundle is None:
        print("❌ 未拿到结构化响应")
        return
    print(f"✅ feature={bundle.feature}, 共 {len(bundle.test_cases)} 条用例")
    for tc in bundle.test_cases:
        print(f"   {tc.id} [{tc.priority}/{tc.case_type}] {tc.title}")


def exp3_stream_observe() -> None:
    """实验 3：流式观察工具调用 + 最终结构化输出。"""
    print("=" * 60)
    print("实验 3：stream(updates) 观察 Agent 决策过程")
    agent = build_case_agent()
    final_bundle: TestCaseBundle | None = None
    for chunk in agent.stream(
        {"messages": [HumanMessage(content="为支付功能生成测试用例")]},
        config=RunnableConfig(),
    ):
        if not isinstance(chunk, dict):
            continue
        for node_name, node_update in chunk.items():
            if not isinstance(node_update, dict):
                continue
            msgs_obj: object = node_update.get("messages", [])
            if not isinstance(msgs_obj, list):
                continue
            for m in msgs_obj:
                if isinstance(m, AIMessage):
                    if m.tool_calls:
                        for tc in m.tool_calls:
                            print(f"  🔧 {node_name} 调工具: {tc.get('name')}({tc.get('args')})")
        raw: object = chunk.get("structured_response")
        if isinstance(raw, TestCaseBundle):
            final_bundle = raw
    if final_bundle is None:
        print("❌ 未拿到最终结构化响应（可能在 stream 的最后一个 chunk 里）")
        return
    print(f"✅ 最终结构化响应: feature={final_bundle.feature}, {len(final_bundle.test_cases)} 条用例")




if __name__ == "__main__":
    # exp1_generate_direct()
    exp2_generate_with_kb()
    # exp3_stream_observe()
    print("\n💡 要点回顾：")
    print("   response_format=ToolStrategy(TestCaseBundle) → 最终输出直接被 Schema 约束")
    print("   kb_search + kb_import = 知识库闭环：先查再用，边用边长（今天修复的增量导入）")
    print("   structured_response 是嵌套 Pydantic（Bundle → list[TestCaseItem]），直接可序列化")
