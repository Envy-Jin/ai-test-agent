"""
Day 18 练习 4：ChromaDB 向量数据库

掌握 langchain-chroma 的 Chroma 使用：
  - Chroma.from_documents()：从文档列表创建向量库
  - vectorstore.similarity_search()：语义检索
  - persist_directory：持久化到磁盘
  - as_retriever()：转为 LangChain 标准检索器

⚠️ Pyright 注意事项：
  - Chroma.from_documents() 返回 Chroma 对象
  - similarity_search() 返回 list[Document]
  - persist_directory 使用绝对路径更可靠
  - Chroma 初始化时需要传入 embedding_function
  - 重复调用 from_documents 会添加数据（不会自动去重）

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


DOCS_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "requirements")

def _load_docs(directory: str) -> list[Document]:
    """从目录加载所有 .txt 文件为 Document 列表（替代 langchain-community 的 DirectoryLoader）。"""
    docs: list[Document] = []
    for filepath in Path(directory).glob("*"):
        if filepath.suffix not in (".txt", ".md"):
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            docs.append(Document(page_content=f.read(), metadata={"source": str(filepath)}))
    return docs


# ═══════════════════════════════════════════════════════
# 模块级：Embedding 模型（所有实验共用）
# ═══════════════════════════════════════════════════════

embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    # google_api_key 自动从环境变量 GEMINI_API_KEY / GOOGLE_API_KEY 读取
    # 不显式传参：避免 Pyright + Pydantic **kwargs 签名检测冲突
)

# ═══════════════════════════════════════════════════════
# 实验 1：从文档创建向量库
# ═══════════════════════════════════════════════════════

def exp1_create_vectorstore() -> None:
    """实验 1：加载文档 → 切分 → 创建 ChromaDB 向量库"""
    print("=" * 60)
    print("实验 1：从文档创建 ChromaDB 向量库")
    print("=" * 60)

    # 加载文档
    docs: list[Document] = _load_docs(DOCS_DIR)
    print(f"加载了 {len(docs)} 个文档")

    # 切分
    splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    chunks: list[Document] = splitter.split_documents(docs)
    print(f"切分为 {len(chunks)} 个片段")

    # 创建向量库（内存模式，不持久化）
    vectorstore: Chroma = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
    )

    # 查看向量库信息
    # Chroma 使用内部 collection 管理数据
    collection_count: int = vectorstore._collection.count()  # type: ignore[attr-defined]
    print(f"向量库中的文档数: {collection_count}")
    print(f"✅ 向量库创建成功（{collection_count} 个向量）")


# ═══════════════════════════════════════════════════════
# 实验 2：语义检索
# ═══════════════════════════════════════════════════════

def exp2_similarity_search() -> None:
    """实验 2：语义检索 —— 用自然语言查询向量库"""
    print("\n" + "=" * 60)
    print("实验 2：语义检索（similarity_search）")
    print("=" * 60)

    # 构建向量库（复用实验 1 的方法）
    docs: list[Document] = _load_docs(DOCS_DIR)
    splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    chunks: list[Document] = splitter.split_documents(docs)
    vectorstore: Chroma = Chroma.from_documents(documents=chunks, embedding=embeddings)

    # 不同查询的检索结果
    queries: list[str] = [
        "登录功能的安全要求",
        "支付相关的异常处理",
        "测试用例设计方法",
        "手机号验证规则",
    ]

    for query in queries:
        print(f"\n🔍 查询: \"{query}\"")

        results: list[Document] = vectorstore.similarity_search(query, k=2)

        for j, doc in enumerate(results):
            source = os.path.basename(str(doc.metadata.get("source", "unknown")))
            preview: str = doc.page_content[:80].replace("\n", " ")
            print(f"  [{j + 1}] {source}: \"{preview}...\"")
            # ⚠️ 注意：这里的 metadata 可能不含 relevance score，
            # 如需分数用 similarity_search_with_score()

    print(f"\n💡 观察到：查询和返回的文档语义相关（不是关键词匹配！）")


# ═══════════════════════════════════════════════════════
# 实验 3：持久化 —— 存到磁盘，下次重启还在
# ═══════════════════════════════════════════════════════

def exp3_persist_vectorstore() -> None:
    """实验 3：持久化向量库到磁盘"""
    print("\n" + "=" * 60)
    print("实验 3：向量库持久化（磁盘存储）")
    print("=" * 60)

    import tempfile
    import shutil

    # 使用临时目录（实验结束后清理）
    persist_dir: str = os.path.join(tempfile.gettempdir(), "chroma_test_18")

    # 清理旧数据
    if os.path.exists(persist_dir):
        shutil.rmtree(persist_dir)

    # 第 1 步：创建并持久化
    docs: list[Document] = _load_docs(DOCS_DIR)
    splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    chunks: list[Document] = splitter.split_documents(docs)

    vectorstore: Chroma = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=persist_dir,
    )
    print(f"✅ 向量库已持久化到: {persist_dir}")
    print(f"   文档数: {len(chunks)}")

    # 第 2 步：模拟重启 —— 从磁盘重新加载
    del vectorstore  # 释放引用

    loaded_vs: Chroma = Chroma(
        embedding_function=embeddings,
        persist_directory=persist_dir,
    )
    loaded_count: int = loaded_vs._collection.count()  # type: ignore[attr-defined]
    print(f"\n♻️ 重启后重新加载: {loaded_count} 个文档")
    assert loaded_count == len(chunks), "持久化/加载失败！"

    # 验证：检索仍然可用
    results: list[Document] = loaded_vs.similarity_search("登录安全", k=2)
    print(f"   检索测试: 找到 {len(results)} 个相关文档")
    # Windows：必须先释放 Chroma 对文件的占用，再删目录
    del loaded_vs
    try:
        from chromadb.api.shared_system_client import SharedSystemClient
        SharedSystemClient.clear_system_cache()
    except Exception:
        pass
    import gc
    gc.collect()
    shutil.rmtree(persist_dir, ignore_errors=True)
    print(f"\n🧹 已清理临时数据")

# ═══════════════════════════════════════════════════════
# 实验 4：as_retriever —— 转为标准检索器
# ═══════════════════════════════════════════════════════

def exp4_as_retriever() -> None:
    """实验 4：as_retriever() —— 转为 LangChain 标准检索器"""
    print("\n" + "=" * 60)
    print("实验 4：as_retriever() —— 标准检索器接口")
    print("=" * 60)

    docs: list[Document] = _load_docs(DOCS_DIR)
    splitter = RecursiveCharacterTextSplitter(chunk_size=300, chunk_overlap=50)
    chunks: list[Document] = splitter.split_documents(docs)
    vectorstore: Chroma = Chroma.from_documents(documents=chunks, embedding=embeddings)

    # 转为检索器（支持 search_kwargs 配置）
    retriever = vectorstore.as_retriever(
        search_type="similarity",  # 相似度检索
        search_kwargs={"k": 3},    # 返回 Top 3
    )

    # retriever.invoke() 是 LangChain 标准接口
    query: str = "安全相关的测试要求"
    results: list[Document] = retriever.invoke(query)

    print(f"查询: \"{query}\"")
    print(f"返回 Top 3 结果:")

    for i, doc in enumerate(results):
        source = os.path.basename(str(doc.metadata.get("source", "unknown")))
        preview: str = doc.page_content[:100].replace("\n", " ")
        print(f"  [{i + 1}] {source}: \"{preview}...\"")

    print(f"\n💡 retriever.invoke() 返回 list[Document]")
    print("  retriever 就是 RAG Chain 中的\"检索\"环节（Day 19 会用到）")



# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    # exp1_create_vectorstore()
    # exp2_similarity_search()
    # exp3_persist_vectorstore()
    exp4_as_retriever()

    print("\n💡 小结：")
    print("  - Chroma.from_documents() 一步完成：嵌入 + 入库")
    print("  - similarity_search() 返回语义最相关的文档片段")
    print("  - persist_directory 实现持久化，重启不丢失")
    print("  - as_retriever() 转为标准检索器，下一步接入 RAG Chain")
    print("  - 下一步：将完整的「加载→切分→入→检索」封装成 RAG 检索器")
