"""
Day 20 练习 2：RAGRetriever 并发安全改造（Day 19 遗留任务 · 方案 3）

工程级修法（用户指定的 Day 20-21 待办）：
  ① index() 加 threading.Lock —— 并发调用只允许一个线程建索引
  ② get_retriever() 在线路径不再调 index() —— 离线建一次，在线只查询

本练习的 RAGRetrieverV2 就是改造后的完整类（可直接同步到你的
day18_rag_retriever.py，用户自行在 ai_test_agent 项目里替换）。

⚠️ Pyright 注意事项：
  - threading.Lock 用 with self._lock: 进入临界区（类型安全）
  - _vectorstore 仍是 Optional[Chroma]，使用前 if 判空收窄
  - ThreadPoolExecutor.submit() 返回 Future[int]，用 .result() 取值
  - _build_count 计数器在 Lock 内自增，用于验证"只建了一次索引"

用法：直接运行跑全部实验，或在 main() 中注释掉不想跑的实验函数。
"""

import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.vectorstores import VectorStoreRetriever


# ═══════════════════════════════════════════════════════
# RAGRetrieverV2（⭐ 改造版：加锁 + 离线/在线分离）
# ═══════════════════════════════════════════════════════

class RAGRetrieverV2:
    """并发安全的 RAG 检索器（Day 18 RAGRetriever 的工程化改造版）。

    相对 Day 18 版本的三处关键改动（===== 修改点 ===== 标注）：
      1. __init__ 增加 self._lock = threading.Lock()
      2. index() 整个建索引流程包进 with self._lock:
      3. 新增 get_retriever() 在线路径（不再调 index()）
    """

    def __init__(
        self,
        docs_dir: str,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        persist_directory: Optional[str] = None,
    ) -> None:
        self.docs_dir: str = docs_dir
        self.chunk_size: int = chunk_size
        self.chunk_overlap: int = chunk_overlap
        self.persist_directory: Optional[str] = persist_directory

        # ===== 修改点 1：线程锁 =====
        # [修改前] 无锁 → 并发调用 index() 时两个线程同时初始化 Chroma
        # [修改后] 一把可重入无关的互斥锁，保护"检查-创建"非原子流程
        self._lock: threading.Lock = threading.Lock()

        self.embeddings = GoogleGenerativeAIEmbeddings(
            model="models/gemini-embedding-001",
            # google_api_key 自动从环境变量读取（Pydantic 类不显式传参）
        )

        self._vectorstore: Optional[Chroma] = None

        # ===== 修改点 2：建索引次数计数器（仅用于验证并发安全）=====
        self._build_count: int = 0

    # ──────────────────────────────────────────
    # 离线路径：index()（幂等 + 加锁）
    # ──────────────────────────────────────────

    def index(self, force: bool = False) -> int:
        """构建索引（加锁，并发安全）。

        Args:
            force: 是否强制重建（即使已有索引）

        Returns:
            入库的文档片段数
        """
        # ===== 修改点 3：整个"检查-创建"流程放进临界区 =====
        # [修改前] 检查 _vectorstore 和 Chroma.from_documents() 分开执行，
        #          两个线程可同时通过检查 → 并发初始化 Chroma → 报错
        # [修改后] with self._lock: 内完成"检查→建索引"，同一时刻只有一个线程执行
        with self._lock:
            if self._vectorstore is not None and not force:
                print("索引已存在，跳过。如需重建请使用 force=True。")
                count: int = self._vectorstore._collection.count()  # type: ignore[attr-defined]
                return count

            # 1. 加载文档
            docs: list[Document] = []
            for filepath in Path(self.docs_dir).iterdir():
                if filepath.suffix not in (".txt", ".md"):
                    continue
                with open(filepath, "r", encoding="utf-8") as f:
                    docs.append(
                        Document(page_content=f.read(), metadata={"source": str(filepath)})
                    )
            print(f"加载文档: {len(docs)} 个（{self.docs_dir}）")

            # 2. 切分
            splitter = RecursiveCharacterTextSplitter(
                chunk_size=self.chunk_size,
                chunk_overlap=self.chunk_overlap,
            )
            chunks: list[Document] = splitter.split_documents(docs)
            print(f"切分为 {len(chunks)} 个片段")

            # 3. 向量化入库（临界区内唯一执行）
            self._vectorstore = Chroma.from_documents(
                documents=chunks,
                embedding=self.embeddings,
                persist_directory=self.persist_directory,
                collection_name="knowledge_base",
            )
            self._build_count += 1
            print(f"  ✅ 索引完成（第 {self._build_count} 次真正建索引），共 {len(chunks)} 条记录")
            return len(chunks)

    # ──────────────────────────────────────────
    # 在线路径：get_retriever()（只查询，绝不建索引）
    # ──────────────────────────────────────────

    def get_retriever(self, k: int = 3, search_type: str = "similarity") -> VectorStoreRetriever:
        """在线路径：返回标准检索器（不再调 index()）。

        ===== 修改点 4：在线/离线分离 =====
        [修改前] 在线路径每次调 index()（做无用的存在性检查，
                并发首次调用还会触发 Chroma 初始化竞争）
        [修改后] 假设索引已由 index() 离线建好；没建就明确报错，
                绝不在这里隐式建索引（职责分离，杜绝并发问题）

        Args:
            k: 检索数量
            search_type: "similarity"（默认）或 "mmr"

        Returns:
            VectorStoreRetriever 对象
        """
        vs: Optional[Chroma] = self._vectorstore
        if vs is None:
            # 遵循项目规范：要么 raise 要么 return None（这里明确 raise）
            raise RuntimeError("尚未建索引，请先调用 index() 完成离线建索引")

        return vs.as_retriever(
            search_type=search_type,
            search_kwargs={"k": k},
        )

    # ──────────────────────────────────────────
    # 查询接口（复用 Day 18 逻辑）
    # ──────────────────────────────────────────

    def search(self, query: str, k: int = 3) -> list[Document]:
        vs: Optional[Chroma] = self._vectorstore
        if vs is None:
            raise RuntimeError("尚未建索引，请先调用 index()")
        return vs.similarity_search(query, k=k)

    def stats(self) -> dict[str, object]:
        vs: Optional[Chroma] = self._vectorstore
        if vs is None:
            return {"status": "未建索引"}
        count: int = vs._collection.count()  # type: ignore[attr-defined]
        return {
            "status": "已建索引",
            "document_count": count,
            "build_count": self._build_count,
        }


# ═══════════════════════════════════════════════════════
# 模块级：共享资源
# ═══════════════════════════════════════════════════════

KNOWLEDGE_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "requirements")


def get_rag() -> RAGRetrieverV2:
    """创建 RAGRetrieverV2 实例（指向知识库根目录，加载全部类型）。"""
    return RAGRetrieverV2(docs_dir=KNOWLEDGE_DIR)


# ═══════════════════════════════════════════════════════
# 实验 1：幂等验证（index 两次，第二次跳过）
# ═══════════════════════════════════════════════════════

def exp1_idempotent_index() -> None:
    """实验 1：index() 调用两次，第二次应跳过（幂等）"""
    print("=" * 60)
    print("实验 1：index() 幂等验证")
    print("=" * 60)

    rag: RAGRetrieverV2 = get_rag()

    c1: int = rag.index()
    print(f"第 1 次 index() → 入库 {c1} 条")

    c2: int = rag.index()
    print(f"第 2 次 index() → 入库 {c2} 条（应等于第 1 次，且打印'跳过'）")

    print(f"\n📊 真正建索引次数: {rag._build_count}（应为 1）")
    assert rag._build_count == 1, "幂等失败！"


# ═══════════════════════════════════════════════════════
# 实验 2：多线程并发 index()（Lock 保证只建一次）
# ═══════════════════════════════════════════════════════

def exp2_concurrent_index() -> None:
    """实验 2：4 个线程同时 index()，Lock 保证只有一个线程真正建索引"""
    print("\n" + "=" * 60)
    print("实验 2：多线程并发 index()")
    print("=" * 60)

    rag: RAGRetrieverV2 = get_rag()

    def do_index() -> int:
        return rag.index()

    # 4 个线程同时调 index()（模拟 RunnableParallel 并发场景）
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures: list[Future[int]] = [pool.submit(do_index) for _ in range(4)]
        results: list[int] = [f.result() for f in futures]

    print(f"并发返回值: {results}")
    print(f"真正建索引次数: {rag._build_count}（应为 1 —— Lock 生效）")
    assert rag._build_count == 1, "并发安全失败！多个线程同时建了索引"

    print("\n💡 这就是 Day 19 并发报错的根治方案：")
    print("   并发调用 index() → 一个线程进临界区建索引，其余等待后走'跳过'分支")


# ═══════════════════════════════════════════════════════
# 实验 3：离线/在线路径分离
# ═══════════════════════════════════════════════════════

def exp3_offline_online_separation() -> None:
    """实验 3：离线建索引一次，在线 get_retriever() 只查询"""
    print("\n" + "=" * 60)
    print("实验 3：离线/在线路径分离")
    print("=" * 60)

    rag: RAGRetrieverV2 = get_rag()

    # 离线：建索引
    print("【离线】建索引...")
    rag.index()
    before: int = rag._build_count

    # 在线：多次查询，不再触发建索引
    print("【在线】查询 3 次...")
    retriever: VectorStoreRetriever = rag.get_retriever(k=3)
    for q in ["登录功能的测试要求", "密码错误处理", "账号锁定规则"]:
        docs: list[Document] = retriever.invoke(q)
        print(f"  🔍 \"{q}\" → {len(docs)} 条结果")

    after: int = rag._build_count
    print(f"\n建索引次数: {before} → {after}（在线查询不应增加）")
    assert after == before, "在线路径竟然又建了索引！"

    print("\n💡 设计收益：")
    print("  - 并发安全：在线路径根本不含初始化逻辑，天然无竞争")
    print("  - 性能：省去每次查询前的存在性检查")
    print("  - 清晰：离线（慢、一次）/ 在线（快、多次）职责分离")


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    # exp1_idempotent_index()
    # exp2_concurrent_index()
    exp3_offline_online_separation()

    print("\n✅ Day 19 遗留任务（方案 3）完成！")
    print("   index() 加锁 + 离线/在线分离 = 并发安全的 RAG 检索器")
    print("   注意：请将 RAGRetrieverV2 同步到你的 ai_test_agent/day18_rag_retriever.py")

