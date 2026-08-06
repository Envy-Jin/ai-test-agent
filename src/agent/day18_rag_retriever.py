"""
Day 18 练习 5：RAG 检索器封装（⭐ 今日核心产出）

把文档加载、切分、嵌入、存储、检索封装成一个完整的 RAGRetriever 类。

核心能力：
  - index()：离线建索引（加载文档 → 切分 → 向量化 → 存入 ChromaDB）
  - search()：在线语义检索
  - search_with_scores()：带相似度分数的检索
  - stats()：查看索引统计信息

⚠️ Pyright 注意事项：
  - Chroma.from_documents() 返回 Chroma 类型
  - similarity_search() 返回 list[Document]
  - similarity_search_with_score() 返回 list[tuple[Document, float]]
  - _collection.count() 访问需要 type: ignore（内部实现细节）
  - search_kwargs 中 k 的值是 int

用法：直接运行跑全部实验，或在 main() 中注释掉不想跑的实验函数。
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever
from langchain_core.embeddings import Embeddings


# ═══════════════════════════════════════════════════════
# RAGRetriever 类（⭐ 今日核心产出）
# ═══════════════════════════════════════════════════════

class RAGRetriever:
    """
    RAG 检索器：文档 → 切分 → 向量化 → 存储 → 检索

    特性：
      - 一键建索引（index）
      - 语义检索（search / search_with_scores）
      - 持久化支持
      - 统计信息

    使用示例：
      rag = RAGRetriever(docs_dir="docs/requirements")
      rag.index()
      results = rag.search("登录功能的安全测试")
    """

    def __init__(
        self,
        docs_dir: str,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        persist_directory: str | None = None,
        embeddings: Embeddings | None = None,
    ):
        """
        Args:
            docs_dir: 文档目录路径
            chunk_size: 切分片段大小
            chunk_overlap: 片段重叠大小
            persist_directory: 持久化目录（None = 仅内存）
            embeddings: Embedding 实例（GoogleGenerativeAIEmbeddings 或 HuggingFaceEmbeddings）
                       默认使用 Google gemini-embedding-001
        """
        self.docs_dir: str = docs_dir
        self.chunk_size: int = chunk_size
        self.chunk_overlap: int = chunk_overlap
        self.persist_directory: str | None = persist_directory

        # Embedding 模型（接受外部传入，支持 Google API 和 HuggingFace 两种实现）
        if embeddings is not None:
            self.embeddings = embeddings
        else:
            # 默认使用 Google Embedding API
            from langchain_google_genai import GoogleGenerativeAIEmbeddings
            self.embeddings = GoogleGenerativeAIEmbeddings(
                model="models/gemini-embedding-001",
            )

        # Vector store（index() 后初始化）
        self._vectorstore: Chroma | None = None

    # ═══════════════════════════════════════════════════════
    # 公共方法
    # ═══════════════════════════════════════════════════════

    def index(self, force: bool = False) -> int:
        """
        构建索引：加载文档 → 切分 → 向量化 → 存入 ChromaDB。

        Args:
            force: 是否强制重建（即使已有索引）

        Returns:
            入库的文档片段数
        """
        if self._vectorstore is not None and not force:
            print("索引已存在，跳过。使用 force=True 强制重建。")
            count: int = self._vectorstore._collection.count()  # type: ignore[attr-defined]
            return count

        # 1. 加载文档
        print(f"加载文档: {self.docs_dir}")
        docs: list[Document] = []
        for filepath in Path(self.docs_dir).glob("*.txt"):
            with open(filepath, "r", encoding="utf-8") as f:
                docs.append(Document(page_content=f.read(), metadata={"source": str(filepath)}))
        print(f"  加载了 {len(docs)} 个文档")

        # 2. 切分文档
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
        )
        chunks: list[Document] = splitter.split_documents(docs)
        print(f"  切分为 {len(chunks)} 个片段")

        # 3. 向量化并存入 ChromaDB
        print("向量化并存入 ChromaDB...")
        self._vectorstore = Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory=self.persist_directory,
        )
        print(f"  ✅ 索引完成，共 {len(chunks)} 条记录")

        return len(chunks)


    def search(self, query: str, k: int = 3) -> list[Document]:
        """
        语义检索：返回最相关的 k 个文档片段。

        Args:
            query: 查询文本（自然语言）
            k: 返回结果数量

        Returns:
            相关文档片段列表
        """
        if self._vectorstore is None:
            raise RuntimeError("尚未建索引，请先调用 index()")

        results: list[Document] = self._vectorstore.similarity_search(query, k=k)
        return results

    def search_with_scores(self, query: str, k: int = 3) -> list[tuple[Document, float]]:
        """
        带分数的语义检索：返回文档片段 + 相似度分数。

        Args:
            query: 查询文本
            k: 返回结果数量

        Returns:
            (Document, similarity_score) 元组列表，分数越高越相关
        """
        if self._vectorstore is None:
            raise RuntimeError("尚未建索引，请先调用 index()")

        results: list[tuple[Document, float]] = self._vectorstore.similarity_search_with_score(query, k=k)
        return results

        
    def as_retriever(self, k: int = 3) -> VectorStoreRetriever:
        """
        转为 LangChain 标准检索器（用于 Day 19 的 RAG Chain）。

        Args:
            k: 检索数量

        Returns:
            VectorStoreRetriever 对象
        """
        if self._vectorstore is None:
            raise RuntimeError("尚未建索引，请先调用 index()")

        return self._vectorstore.as_retriever(search_kwargs={"k": k})


    def stats(self) -> dict[str, object]:
        """返回索引统计信息"""
        if self._vectorstore is None:
            return {"status": "未建索引"}

        count: int = self._vectorstore._collection.count()  # type: ignore[attr-defined]
        return {
            "status": "已建索引",
            "document_count": count,
            "chunk_size": self.chunk_size,
            "chunk_overlap": self.chunk_overlap,
            "embedding_model": str(type(self.embeddings).__name__),
            "persist_directory": self.persist_directory or "（仅内存）",
        }


# ═══════════════════════════════════════════════════════
# 实验 1：RAGRetriever 基本使用
# ═══════════════════════════════════════════════════════

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "requirements")


def exp1_basic_usage() -> None:
    """实验 1：RAGRetriever 基本使用流程"""
    print("=" * 60)
    print("实验 1：RAGRetriever 基本使用")
    print("=" * 60)

    rag = RAGRetriever(docs_dir=DOCS_DIR)

    # 建索引
    count: int = rag.index()
    print(f"\n📊 索引统计: {rag.stats()}\n")

    # 检索
    queries: list[str] = [
        "登录功能的安全要求有哪些？",
        "支付异常怎么处理？",
        "测试用例的设计原则",
    ]

    for q in queries:
        results: list[Document] = rag.search(q, k=2)
        print(f"🔍 \"{q}\"")
        for j, doc in enumerate(results):
            source = os.path.basename(str(doc.metadata.get("source", "unknown")))
            preview: str = doc.page_content[:100].replace("\n", " ")
            print(f"  [{j + 1}] {source}: \"{preview}...\"")
        print()


# ═══════════════════════════════════════════════════════
# 实验 2：带分数的检索
# ═══════════════════════════════════════════════════════

def exp2_search_with_scores() -> None:
    """实验 2：带相似度分数的检索"""
    print("\n" + "=" * 60)
    print("实验 2：search_with_scores —— 查看相似度分数")
    print("=" * 60)

    rag = RAGRetriever(docs_dir=DOCS_DIR)
    rag.index()

    query: str = "注册功能的验证码规则"
    results: list[tuple[Document, float]] = rag.search_with_scores(query, k=4)

    print(f"\n查询: \"{query}\"\n")
    print("结果（分数越低越相关，ChromaDB 使用距离而非余弦相似度）:")

    for j, (doc, score) in enumerate(results):
        source = os.path.basename(str(doc.metadata.get("source", "unknown")))
        preview: str = doc.page_content[:80].replace("\n", " ")
        bar: str = "█" * max(1, int((1.0 - min(score, 1.0)) * 30))
        print(f"  [{j + 1}] score={score:.4f} {bar}")
        print(f"       {source}: \"{preview}...\"")

    print(f"\n💡 注意：ChromaDB 默认的 score 是 L2 距离（越小越相似）")


# ═══════════════════════════════════════════════════════
# 实验 3：不同 chunk_size 对检索质量的影响
# ═══════════════════════════════════════════════════════

def exp3_chunk_size_impact() -> None:
    """实验 3：对比不同 chunk_size 对检索结果的影响"""
    print("\n" + "=" * 60)
    print("实验 3：chunk_size 对检索质量的影响")
    print("=" * 60)

    query: str = "登录功能的安全要求"

    for chunk_size in [200, 500, 1000]:
        rag = RAGRetriever(docs_dir=DOCS_DIR, chunk_size=chunk_size, chunk_overlap=50)
        rag.index()

        results: list[Document] = rag.search(query, k=2)

        print(f"\nchunk_size={chunk_size}:")
        for j, doc in enumerate(results):
            print(f"  [{j + 1}] {len(doc.page_content)} 字符: \"{doc.page_content[:80].replace(chr(10), ' ')}...\"")

    print(f"\n💡 观察：chunk_size 过小 → 片段可能不完整")
    print("  chunk_size 过大 → 冗余信息多，精准度下降")
    print("  通常 300-500 是个不错的平衡点")


# ═══════════════════════════════════════════════════════
# 实验 4：获取 retriever 对象（为 Day 19 做准备）
# ═══════════════════════════════════════════════════════

def exp4_retriever_for_chain() -> None:
    """实验 4：as_retriever() —— 为 Day 19 的 RAG Chain 做准备"""
    print("\n" + "=" * 60)
    print("实验 4：as_retriever() —— 为 Day 19 的 RAG Chain 做准备")
    print("=" * 60)

    rag = RAGRetriever(docs_dir=DOCS_DIR)
    rag.index()

    # 获取 LangChain 标准检索器
    retriever: VectorStoreRetriever = rag.as_retriever(k=3)

    # retriever.invoke() 接收 str，返回 list[Document]
    result: list[Document] = retriever.invoke("支付安全")

    print(f"retriever.invoke(\"支付安全\") 返回 {len(result)} 个文档:")
    for j, doc in enumerate(result):
        source = os.path.basename(str(doc.metadata.get("source", "unknown")))
        preview: str = doc.page_content[:100].replace("\n", " ")
        print(f"  [{j + 1}] {source}: \"{preview}...\"")

    print(f"\n💡 retriever 就是 RAG Chain 的\"检索\"环节：")
    print("  Day 19 将用它构建: retriever | format_docs | prompt | LLM | parser")
    print("  实现完整的「检索 → 生成」流水线！")


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    exp1_basic_usage()
    exp2_search_with_scores()
    exp3_chunk_size_impact()
    exp4_retriever_for_chain()

    print("\n✅ Day 18 核心产出完成！")
    print("   RAGRetriever = Document Loader + Splitter + Embeddings + ChromaDB 的封装")
    print("   特性：一键建索引、语义检索、带分数检索、持久化、标准 retriever 接口")
    print("   后续：Day 19 将用 retriever 构建完整的 RAG Chain")


