"""
Day 21 练习 1：索引持久化 —— KnowledgeIndexerV2（落盘 + 重启加载）

Day 20 笔记"还存在的问题"之一：索引未持久化（每次运行重建）。
本练习升级 KnowledgeIndexer → KnowledgeIndexerV2：
  1. 新增 persist_directory 参数（默认 None = 纯内存，行为与 Day 20 一致）
  2. index() 幂等逻辑扩展：优先尝试从磁盘加载已有索引，无则建库落盘
  3. _load_existing()：加载持久化索引并返回记录数；不存在/为空返回 None
  4. _reset_persisted_collection()：force=True 时先删除磁盘旧集合，
     防止 from_documents 往已有集合重复追加（真实工程坑！）

⚠️ Pyright 注意事项：
  - persist_directory 是 Optional[str]，使用前判空（truthiness 收窄）
  - _load_existing() 遵循"要么 raise 要么 return None"规范：返回 None 表示无已有索引
  - 加载已有索引用 Chroma(persist_directory=..., embedding_function=...)，
    注意参数名是 embedding_function（from_documents 里才是 embedding）
  - _collection.count() / _client.delete_collection() 是私有 API → # type: ignore[attr-defined]
  - ⚠️ chromadb 1.5.x 的 Collection.delete() 必须提供 ids/where（无参 delete 抛 ValueError）

用法：直接运行跑全部实验，或在 main() 中注释掉不想跑的实验函数。
"""

import os
import sys
import threading

# Windows 下控制台/重定向输出统一 UTF-8，防止 emoji/中文打印报 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document

from day20_knowledge_loader import (
    KNOWLEDGE_DIR,
    ensure_sample_data,
    load_knowledge_base,
)

# ═══════════════════════════════════════════════════════
# KnowledgeIndexerV2：持久化索引器
# ═══════════════════════════════════════════════════════

class KnowledgeIndexerV2:
    """智能测试知识库的持久化索引器（Day 20 KnowledgeIndexer + 落盘）。

    Day 21 新增能力（===== 修改点 ===== 标注）：
      - persist_directory: 索引落盘目录（None = 纯内存，兼容 Day 20 行为）
      - index() 优先加载已有落盘索引；无则建库并落盘
      - force=True 时先删除磁盘旧集合再重建（防重复入库）
    """

    def __init__(
        self,
        root_dir: str = KNOWLEDGE_DIR,
        chunk_size: int = 300,
        chunk_overlap: int = 50,
        persist_directory: str | None = None,
        collection_name: str = "knowledge_base",
    ) -> None:
        self.root_dir: str = root_dir
        self.persist_directory: str | None = persist_directory
        self.collection_name: str = collection_name
        self._lock: threading.Lock = threading.Lock()  # 并发安全（Day 20 工程模式）
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        self._vectorstore: Chroma | None = None
        self._chunk_size: int = chunk_size
        self._chunk_overlap: int = chunk_overlap
        self._load_count: int = 0  # 验证用：从磁盘加载次数 

    # ──────────────────────────────────────────
    # 离线路径：index()（优先加载已有，无则建库）
    # ──────────────────────────────────────────

    def index(self, force: bool = False) -> int:
        """构建或加载索引。

        Args:
            force: True 时忽略已有索引，强制重建（重建前删除磁盘旧集合）

        Returns:
            当前索引的记录数（加载 = 已有数量；新建 = 新入库数量）
        """
        with self._lock:
            if self._vectorstore is not None and not force:
                count: int = self._vectorstore._collection.count() 
                return count

            if force:
                self._reset_persisted_collection()

            if not force:
                loaded: int | None = self._load_existing()
                if loaded is not None:
                    return loaded

            # 磁盘无索引（或 force）→ 从文档建库并落盘
            docs: list[Document] = load_knowledge_base(self.root_dir)
            if not docs:
                raise RuntimeError(f"知识库目录为空: {self.root_dir}")

            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self._chunk_size,
                chunk_overlap=self._chunk_overlap,
            )
            chunks: list[Document] = splitter.split_documents(docs)
            print(f"切分为 {len(chunks)} 个片段，正在向量化入库...")

            self._vectorstore = Chroma.from_documents(
                documents=chunks,
                embedding=self.embeddings,
                persist_directory=self.persist_directory,
                collection_name=self.collection_name,
            )
            count = self._vectorstore._collection.count()  # type: ignore[attr-defined]
            target: str = self.persist_directory if self.persist_directory else "内存模式（未落盘）"
            print(f"  ✅ 索引已建立（{target}），共 {count} 条片段")
            return count        

    # ──────────────────────────────────────────
    # 磁盘操作辅助（_load_existing / _reset）
    # ──────────────────────────────────────────

    def _load_existing(self) -> int | None:
        """尝试从磁盘加载已有索引。

        Returns:
            已加载索引的记录数；目录不存在或为空集合时返回 None
            （遵循项目规范：本函数只 return None，不 raise）
        """
        persist: str | None = self.persist_directory
        if not persist or not os.path.isdir(persist):
            return None

        vs = Chroma(
            persist_directory=persist,
            embedding_function=self.embeddings,  # ⚠️ 参数名：加载用 embedding_function
            collection_name=self.collection_name,
        )
        count: int = vs._collection.count()  # type: ignore[attr-defined]
        if count == 0:
            return None
        self._vectorstore = vs
        self._load_count += 1
        print(f"  📂 从磁盘加载已有索引（{persist}），共 {count} 条片段")
        return count

    def _reset_persisted_collection(self) -> None:
        """force=True 时删除磁盘上已有的同名集合。

        为什么必须删除？persist_directory 模式下 Chroma 连接的是同一个
        持久化存储，from_documents 对已存在的集合是【追加】而非覆盖，
        不清理会导致重复入库（记录数翻倍）。
        ⚠️ 实测（chromadb 1.5.x）：Collection.delete() 必须提供 ids/where
           （无参 delete 会抛 ValueError），所以用 delete_collection 删整个集合，
           之后 from_documents 会自动重建空集合。
        """
        persist: str | None = self.persist_directory
        if not persist or not os.path.isdir(persist):
            return
        tmp = Chroma(
            persist_directory=persist,
            embedding_function=self.embeddings,
            collection_name=self.collection_name,
        )
        tmp._client.delete_collection(name=self.collection_name)  # type: ignore[attr-defined]
        print("  🧹 已删除磁盘上的旧索引（force=True，防重复入库）")

    # ──────────────────────────────────────────
    # 在线路径（与 Day 20 完全一致）
    # ──────────────────────────────────────────

    def search_by_type(self, query: str, doc_type: str, k: int = 3) -> list[Document]:
        """按文档类型过滤的语义检索（doc_type 用 DOC_TYPE_* 常量）。"""
        vs: Chroma | None = self._vectorstore
        if vs is None:
            raise RuntimeError("尚未建索引，请先调用 index()")
        filter_dict: dict[str, object] = {"doc_type": {"$eq": doc_type}}
        return vs.similarity_search(query, k=k, filter=filter_dict)  # type: ignore[arg-type]

    def recommend_test_cases(self, description: str, k: int = 3) -> list[tuple[Document, float]]:
        """根据场景描述推荐相似的历史测试用例（带距离分数）。"""
        vs: Chroma | None = self._vectorstore
        if vs is None:
            raise RuntimeError("尚未建索引，请先调用 index()")
        filter_dict: dict[str, object] = {"doc_type": {"$eq": "test_case"}}
        results: list[tuple[Document, float]] = vs.similarity_search_with_score(
            description, k=k, filter=filter_dict  # type: ignore[arg-type]
        )
        results.sort(key=lambda item: item[1])
        return results

    def stats(self) -> dict[str, object]:
        vs: Chroma | None = self._vectorstore
        if vs is None:
            return {"status": "未建索引"}
        count: int = vs._collection.count()  # type: ignore[attr-defined]
        return {
            "status": "已建索引",
            "document_count": count,
            "load_count": self._load_count,
        }


# ═══════════════════════════════════════════════════════
# 模块级：演示用落盘目录（相对 src/agent/ 的 ../../chroma_db）
# ═══════════════════════════════════════════════════════

DEMO_CHROMA_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")


def get_demo_indexer() -> KnowledgeIndexerV2:
    """创建演示用持久化索引器。"""
    return KnowledgeIndexerV2(persist_directory=DEMO_CHROMA_DIR)


# ═══════════════════════════════════════════════════════
# 实验 1：落盘建索引（首次运行）
# ═══════════════════════════════════════════════════════

def exp1_build_and_persist() -> None:
    """实验 1：首次建索引并落盘（load_count 应为 0，即不是从磁盘加载）"""
    print("=" * 60)
    print("实验 1：首次建索引并落盘")
    print("=" * 60)

    indexer: KnowledgeIndexerV2 = get_demo_indexer()
    count: int = indexer.index()
    print(f"\n📊 索引记录数: {count}")
    print(f"   从磁盘加载次数: {indexer._load_count}（首次应为 0）")
    print(f"   chroma_db 目录是否生成: {os.path.isdir(DEMO_CHROMA_DIR)}")

    print("\n💡 关键：persist_directory 让 Chroma 使用 PersistentClient 落盘")


# ═══════════════════════════════════════════════════════
# 实验 2：重启后从磁盘加载
# ═══════════════════════════════════════════════════════

def exp2_reload_from_disk() -> None:
    """实验 2：重启后从磁盘加载（load_count 应为 1，不再调用 Embedding API）"""
    print("\n" + "=" * 60)
    print("实验 2：重启后从磁盘加载")
    print("=" * 60)

    # 模拟"新进程"：重新创建 indexer（同一个 persist_directory）
    indexer: KnowledgeIndexerV2 = get_demo_indexer()
    count: int = indexer.index()
    print(f"\n📊 索引记录数: {count}")
    print(f"   从磁盘加载次数: {indexer._load_count}（应为 1 —— 说明加载而非重建）")

    # 在线查询验证加载的索引可用
    docs: list[Document] = indexer.search_by_type("登录失败", "bug", k=2)
    print(f"   加载后立即查询（bug 类型）: {len(docs)} 条结果")

    assert indexer._load_count == 1, "应该从磁盘加载，而不是重建！"
    print("\n💡 收益：重启不重建 = 省掉 Embedding API 调用（慢 + 花钱）")


# ═══════════════════════════════════════════════════════
# 实验 3：force=True 强制重建
# ═══════════════════════════════════════════════════════

def exp3_force_rebuild() -> None:
    """实验 3：force=True 强制重建（先删除旧集合，记录数不翻倍）"""
    print("\n" + "=" * 60)
    print("实验 3：force=True 强制重建")
    print("=" * 60)

    indexer: KnowledgeIndexerV2 = get_demo_indexer()
    count: int = indexer.index(force=True)
    print(f"\n📊 重建后索引记录数: {count}")
    print(f"   从磁盘加载次数: {indexer._load_count}（force 时不应走加载）")

    print("\n💡 使用场景：知识库文档更新后，用 --force 重建索引")
    print("   ⚠️ 若没删旧集合直接 from_documents，记录数会翻倍（重复入库）")


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    # ensure_sample_data()
    # exp1_build_and_persist()
    # exp2_reload_from_disk()
    exp3_force_rebuild()

    print("\n✅ 索引持久化完成！")
    print("   KnowledgeIndexerV2 = Day 20 索引器 + persist_directory 落盘")
    print("   下次 CLI 启动直接加载磁盘索引，不再重建")
