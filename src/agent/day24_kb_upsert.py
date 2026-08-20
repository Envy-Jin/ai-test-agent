"""
Day 24 步骤 0：向量库增量更新修复（Day 22 遗留待办）

背景：Day 22 讨论"向量库增量更新 vs 全量重建 + 过时知识陷阱"→ 结论是知识库
应支持增量导入。Day 21 的 KnowledgeIndexerV2 只有 index(force=) 全量路径，
且 from_documents 对已存在集合是【追加】——同一文件重复导入会记录翻倍。

今天补上三个能力：
  1. KnowledgeUpserter：文件级 upsert（按 source 删旧加新），重复导入不翻倍
  2. metadata 增加 feature 维度（配合 Day 18 的 Chroma filter 使用）
  3. kb_import 工具：把增量导入能力暴露给 Agent（Day 24 练习 3 复用）

核心不变量：同一 source 的文件重复导入 → 集合记录数不变（幂等）。

用法：python day24_kb_upsert.py   （内置自测断言，可独立运行验证）
"""

import hashlib
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.tools import tool
from langchain_text_splitters import RecursiveCharacterTextSplitter

from day20_knowledge_loader import KNOWLEDGE_DIR, ensure_sample_data
from day21_kb_persist import KnowledgeIndexerV2

# ═══════════════════════════════════════════════════════
# 常量（防魔法字符串）
# ═══════════════════════════════════════════════════════

CHROMA_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")

# feature 维度（功能模块）常量
FEATURE_GENERAL: str = "general"
FEATURE_LOGIN: str = "login"
FEATURE_PAYMENT: str = "payment"


# ═══════════════════════════════════════════════════════
# KnowledgeUpserter：增量导入封装
# ═══════════════════════════════════════════════════════

class KnowledgeUpserter:
    """向量库增量更新器：文件级 upsert（幂等）+ feature 维度。

    实现思路（先删后加 = upsert）：
      1. 按 source 过滤出该文件的全部旧块 id（Chroma.get(where=...)）
      2. 删除旧块（Chroma.delete(ids=...)）
      3. 加新块（add_documents(ids=稳定 id)）
    这样：重复导入同一文件 → 先删光再添新，总数不变；文件内容更新后重新导入
    → 旧知识被整体覆盖，解决"过时知识陷阱"。
    """

    def __init__(self, indexer: KnowledgeIndexerV2) -> None:
        self._indexer = indexer

    @staticmethod
    def _stable_id(source: str, doc_type: str, chunk_idx: int) -> str:
        """稳定 doc_id：source + doc_type + 块序号 → sha1（Chroma id 不能含路径特殊字符）。"""
        raw: str = f"{source}|{doc_type}|{chunk_idx}"
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def _ensure_vectorstore(self) -> Chroma:
        """确保索引已加载（首次调用自动建索引）。"""
        vs = self._indexer._vectorstore
        if vs is None:
            self._indexer.index()
            vs = self._indexer._vectorstore
            if vs is None:
                raise RuntimeError("索引初始化失败")
        return vs

    def import_file(self, path: str, doc_type: str, feature: str = FEATURE_GENERAL) -> int:
        """导入单个文件：切分 → 删该 source 旧块 → 加新块（文件级 upsert）。

        参数：
            path: 本地文件路径（.txt / .md）
            doc_type: 文档类型（requirement / test_case / bug）
            feature: 功能模块（login / payment / general）
        返回：本次新增片段数。重复导入同一文件返回新片段数（删旧加新后总数不变）。
        """
        if not os.path.isfile(path):
            raise FileNotFoundError(f"文件不存在: {path}")
        with open(path, "r", encoding="utf-8") as f:
            text: str = f.read()
        splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
        chunks: list[str] = splitter.split_text(text)
        docs: list[Document] = [
            Document(
                page_content=chunk,
                metadata={
                    "source": path,
                    "doc_type": doc_type,
                    "feature": feature,
                },
            )
            for chunk in chunks
        ]
        return self.upsert_documents(docs)

    def upsert_documents(self, docs: list[Document]) -> int:
        """核心：按 source 删旧加新。返回本次写入的片段数。"""
        if not docs:
            return 0
        vs = self._ensure_vectorstore()
        source: str = str(docs[0].metadata.get("source", ""))
        doc_type: str = str(docs[0].metadata.get("doc_type", ""))

        # 1) 查旧：按 source 过滤出该文件所有旧块（Chroma.get 的 where 支持嵌套结构）
        old: dict[str, object] = vs.get(where={"source": source})
        old_ids_obj: object = old.get("ids", [])
        old_ids: list[str] = []
        if isinstance(old_ids_obj, list):
            old_ids = [i for i in old_ids_obj if isinstance(i, str)]

        # 2) 删旧（先删后加 = upsert 语义）
        if old_ids:
            vs.delete(ids=old_ids)

        # 3) 加新（稳定 id：同 source 同块序号的块永远同一个 id）
        ids: list[str] = [
            self._stable_id(source, doc_type, idx) for idx in range(len(docs))
        ]
        vs.add_documents(documents=docs, ids=ids)
        return len(docs)


# ═══════════════════════════════════════════════════════
# 模块级惰性资源（Day 22 的 _get_indexer 模式）
# ═══════════════════════════════════════════════════════

_kb_indexer: KnowledgeIndexerV2 | None = None
_kb_upserter: KnowledgeUpserter | None = None


def _get_upserter() -> KnowledgeUpserter:
    """懒加载（全局一次，避免每个工具调用都重建）。"""
    global _kb_indexer, _kb_upserter
    if _kb_upserter is None:
        ensure_sample_data()
        idx: KnowledgeIndexerV2 = KnowledgeIndexerV2(
            root_dir=KNOWLEDGE_DIR, persist_directory=CHROMA_DIR
        )
        idx.index()
        _kb_indexer = idx
        _kb_upserter = KnowledgeUpserter(idx)
    return _kb_upserter


# ═══════════════════════════════════════════════════════
# kb_import 工具：把增量导入暴露给 Agent（练习 3 复用）
# ═══════════════════════════════════════════════════════

@tool
def kb_import(file_path: str, doc_type: str, feature: str = FEATURE_GENERAL) -> str:
    """将本地文档导入项目测试知识库（幂等：同一文件重复导入不会产生重复记录）。

    Args:
        file_path: 本地文档的绝对路径（支持 .txt / .md）。
        doc_type: 文档类型，只能是 requirement（需求）、test_case（测试用例）、bug（Bug 报告）。
        feature: 所属功能模块，如 login（登录）、payment（支付）；不确定时用 general。
    """
    if doc_type not in ("requirement", "test_case", "bug"):
        return f"导入失败：doc_type 只能是 requirement/test_case/bug，收到：{doc_type}"
    try:
        upserter: KnowledgeUpserter = _get_upserter()
        n: int = upserter.import_file(file_path, doc_type, feature)
        return f"导入成功：{file_path}（{n} 个片段，doc_type={doc_type}，feature={feature}）"
    except Exception as e:
        return f"导入失败：{e}"


# ═══════════════════════════════════════════════════════
# 自测（无 API：用假 Embedding 覆盖真实嵌入）
# ═══════════════════════════════════════════════════════

def _count_all() -> int:
    """当前集合总记录数（验证幂等用）。"""
    upserter: KnowledgeUpserter = _get_upserter()
    vs = upserter._ensure_vectorstore()
    return vs._collection.count()  # type: ignore[attr-defined]


def exp1_idempotent_import() -> None:
    """实验 1：重复导入同一文件 → 记录数不翻倍（核心修复验证）。"""
    print("=" * 60)
    print("实验 1：幂等导入验证（重复导入同一文件）")
    tmp_file: str = os.path.join(os.path.dirname(__file__), "..", "..", "tmp_upsert_demo.md")
    with open(tmp_file, "w", encoding="utf-8") as f:
        f.write("# 登录功能需求\n\n用户可通过手机号和密码登录，密码不少于 8 位。\n\n登录失败 5 次锁定账号 30 分钟。\n")
    try:
        upserter: KnowledgeUpserter = _get_upserter()
        n1: int = upserter.import_file(tmp_file, "requirement", FEATURE_LOGIN)
        c1: int = _count_all()
        n2: int = upserter.import_file(tmp_file, "requirement", FEATURE_LOGIN)
        c2: int = _count_all()
        print(f"首次导入: {n1} 片段，集合总数 {c1}")
        print(f"重复导入: {n2} 片段，集合总数 {c2}")
        assert c2 == c1, f"重复导入后集合条数翻倍！{c1} -> {c2}"
        print("✅ 幂等验证通过：重复导入不翻倍")
    finally:
        if os.path.isfile(tmp_file):
            os.remove(tmp_file)


def exp2_feature_filter() -> None:
    """实验 2：feature 维度可用（Day 18 的 filter 能力配合验证）。"""
    print("=" * 60)
    print("实验 2：feature 过滤检索")
    upserter: KnowledgeUpserter = _get_upserter()
    vs = upserter._ensure_vectorstore()
    # 按 feature 过滤（Chroma.get 的 where 支持嵌套结构）
    rows: dict[str, object] = vs.get(where={"feature": FEATURE_LOGIN})
    ids_obj: object = rows.get("ids", [])
    ids: list[str] = [i for i in ids_obj if isinstance(i, str)] if isinstance(ids_obj, list) else []
    print(f"feature={FEATURE_LOGIN} 的片段数: {len(ids)}")
    assert len(ids) > 0, "feature 过滤没有命中任何记录"
    print("✅ feature 维度验证通过")




if __name__ == "__main__":
    exp1_idempotent_import()
    exp2_feature_filter()
    print("\n💡 要点回顾：")
    print("   upsert = 按 source 删旧加新（Chroma.get 查旧 → delete 删旧 → add_documents 加新）")
    print("   稳定 id = sha1(source|doc_type|chunk_idx)，同块永远同 id")
    print("   feature 字段 = metadata 多一个维度，配合 Chroma filter 过滤检索")
