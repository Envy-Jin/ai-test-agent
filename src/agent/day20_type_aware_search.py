"""
Day 20 练习 3：检索层 —— 类型感知检索 + 相似测试用例推荐

基于步骤 1 的 doc_type 元数据，实现：
  1. KnowledgeIndexer：加载三类文档 → 切分 → 建索引（加锁，复用步骤 2 的并发安全设计）
  2. 类型感知检索：Chroma filter 按 doc_type 过滤（只搜 bug / 只搜 test_case）
  3. 相似测试用例推荐：test_case 类型 + 带分数排序，输出 Top N

⚠️ Pyright 注意事项：
  - similarity_search(query, filter=...) 的 filter 传 dict[str, object] 兼容结构
  - search_with_scores 返回 list[tuple[Document, float]]，解包类型明确
  - metadata 取 doc_type 用 str() 转换
  - 建索引流程用 threading.Lock 保护（复用步骤 2 的模式）

用法：直接运行跑全部实验，或在 main() 中注释掉不想跑的实验函数。
"""

from langchain_core.documents.base import Document
import os
import threading
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

# 复用步骤 1 的加载逻辑
from day20_knowledge_loader import (
    KNOWLEDGE_DIR,
    DOC_TYPE_BUG,
    DOC_TYPE_TEST_CASE,
    ensure_sample_data,
    load_knowledge_base,
)

# ═══════════════════════════════════════════════════════
# KnowledgeIndexer：知识库索引器（加锁 + 类型过滤检索）
# ═══════════════════════════════════════════════════════

class KnowledgeIndexer:
    """智能测试知识库的索引器：建索引（带 doc_type）+ 类型感知检索 + 相似推荐。"""

    def __init__(
        self,
        root_dir: str = KNOWLEDGE_DIR,
        chunk_size: int = 300,
        chunk_overlap: int = 50,
    ) -> None:
        self.root_dir: str = root_dir
        self._lock: threading.Lock = threading.Lock()  # 并发安全（步骤 2 的工程模式）
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        self._vectorstore: Chroma | None = None
        self._chunk_size: int = chunk_size
        self._chunk_overlap: int = chunk_overlap

    # ──────────────────────────────────────────
    # 离线：建索引
    # ──────────────────────────────────────────

    def index(self, force: bool = False) -> int:
        """加载全部三类文档 → 切分 → 向量化入库（doc_type 随 metadata 进入向量库）。

        Returns:
            当前索引的记录数（首次 = 新入库片段数；已存在 = 跳过并返回已有数量）
        """
        with self._lock:
            if self._vectorstore is not None and not force:
                print("索引已存在，跳过。如需重建请使用 force=True。")
                count: int = self._vectorstore._collection.count()  # type: ignore[attr-defined]
                return count

            docs: list[Document] = load_knowledge_base(self.root_dir)
            if not docs:
                raise RuntimeError(f"知识库目录为空: {self.root_dir}")

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self._chunk_size,
                chunk_overlap=self._chunk_overlap,
            )
            chunks: list[Document] = splitter.split_documents(docs)
            print(f"切分为 {len(chunks)} 个片段")

            self._vectorstore = Chroma.from_documents(
                documents=chunks,
                embedding=self.embeddings,
                collection_name="knowledge_base",
            )
            print(f"  ✅ 知识库索引完成，共 {len(chunks)} 条片段")
            return len(chunks)

    # ──────────────────────────────────────────
    # 在线：类型感知检索
    # ──────────────────────────────────────────

    def search_by_type(self, query: str, doc_type: str, k: int = 3) -> list[Document]:
        """按文档类型过滤的语义检索。

        Args:
            query: 查询文本
            doc_type: DOC_TYPE_* 常量（requirement / test_case / bug）
            k: 返回数量

        Returns:
            该类型下的相关文档片段
        """
        vs: Chroma | None = self._vectorstore
        if vs is None:
            raise RuntimeError("尚未建索引，请先调用 index()")

        # Chroma 1.x 推荐显式操作符（联网确认）；简写 {"doc_type": doc_type} 也兼容
        filter_dict: dict[str, object] = {"doc_type": {"$eq": doc_type}}
        return vs.similarity_search(query, k=k, filter=filter_dict)  # type: ignore[arg-type]

    # ──────────────────────────────────────────
    # 在线：相似测试用例推荐（带分数）
    # ──────────────────────────────────────────

    def recommend_test_cases(self, description: str, k: int = 3) -> list[tuple[Document, float]]:
        """根据场景描述推荐相似的历史测试用例。

        Args:
            description: 用户描述的场景（如"密码连续输错5次"）
            k: 推荐数量

        Returns:
            (Document, distance) 列表，按距离升序（越小越相似）
        """
        vs: Chroma | None = self._vectorstore
        if vs is None:
            raise RuntimeError("尚未建索引，请先调用 index()")

        filter_dict: dict[str, object] = {"doc_type": {"$eq": DOC_TYPE_TEST_CASE}}
        results: list[tuple[Document, float]] = vs.similarity_search_with_score(
            description, k=k, filter=filter_dict  # type: ignore[arg-type]
        )
        # Chroma 返回按距离升序（已排序），再显式排一次更稳
        results.sort(key=lambda item: item[1])
        return results

# ═══════════════════════════════════════════════════════
# 模块级：共享索引器（懒加载：第一次使用时建索引）
# ═══════════════════════════════════════════════════════

_indexer: KnowledgeIndexer | None = None


def get_indexer() -> KnowledgeIndexer:
    """获取全局索引器（首次调用时建索引）。"""
    global _indexer
    if _indexer is None:
        _indexer = KnowledgeIndexer()
        _indexer.index()
    return _indexer

# ═══════════════════════════════════════════════════════
# 实验 1：全类型检索 vs 类型过滤检索
# ═══════════════════════════════════════════════════════

def exp1_type_filter() -> None:
    """实验 1：对比全类型检索和按 bug 类型过滤检索"""
    print("=" * 60)
    print("实验 1：类型感知检索")
    print("=" * 60)

    indexer: KnowledgeIndexer = get_indexer()
    query: str = "登录失败"

    # 全类型
    vs: Chroma | None = indexer._vectorstore
    if vs is None:
        raise RuntimeError("索引未建立")
    all_results: list[Document] = vs.similarity_search(query, k=3)
    print(f"\n🔍 查询: \"{query}\"")
    print(f"\n【全类型】返回 {len(all_results)} 条:")
    for i, doc in enumerate(all_results):
        doc_type: str = str(doc.metadata.get("doc_type", "unknown"))
        source: str = str(doc.metadata.get("source", "unknown"))
        print(f"  [{i}] ({doc_type}) {os.path.basename(source)}: {doc.page_content[:40].replace(chr(10), ' ')}...")

    # 只搜 bug
    bug_results: list[Document] = indexer.search_by_type(query, DOC_TYPE_BUG, k=3)
    print(f"\n【只看 Bug】返回 {len(bug_results)} 条:")
    for i, doc in enumerate(bug_results):
        source = str(doc.metadata.get("source", "unknown"))
        print(f"  [{i}] {os.path.basename(source)}: {doc.page_content[:40].replace(chr(10), ' ')}...")

    print("\n💡 类型过滤的效果：同样问\"登录失败\"，只看 Bug 时结果全部来自 bugs 目录")


# ═══════════════════════════════════════════════════════
# 实验 2：相似测试用例推荐
# ═══════════════════════════════════════════════════════

def exp2_recommend_cases() -> None:
    """实验 2：根据场景描述推荐相似的历史测试用例（带分数）"""
    print("\n" + "=" * 60)
    print("实验 2：相似测试用例推荐")
    print("=" * 60)

    indexer: KnowledgeIndexer = get_indexer()

    descriptions: list[str] = [
        "密码连续输错5次会怎样",
        "输入不合法手机号时的提示",
    ]

    for desc in descriptions:
        print(f"\n📋 场景: \"{desc}\"")
        ranked: list[tuple[Document, float]] = indexer.recommend_test_cases(desc, k=2)
        for j, (doc, distance) in enumerate[tuple[Document, float]](ranked):
            score: float = 1.0 - min(distance, 1.0)  # 距离 → 直观相似度（0~1）
            source = str(doc.metadata.get("source", "unknown"))
            print(f"  [{j}] 相似度 {score:.2f} | {os.path.basename(source)}")
            print(f"       {doc.page_content[:60].replace(chr(10), ' ')}...")

    print("\n💡 推荐逻辑：用户描述 → 语义检索 test_case 类型 → 距离升序 Top N")


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════

def main() -> None:
    # ensure_sample_data()
    # exp1_type_filter()
    exp2_recommend_cases()

    print("\n✅ 检索层完成！")
    print("   search_by_type(): 按 doc_type 过滤检索")
    print("   recommend_test_cases(): 相似用例推荐（带分数排序）")
    print("   下一步：把检索结果喂给 LLM，构建问答 Chain 和 Bug 分析 Chain")


if __name__ == "__main__":
    main()