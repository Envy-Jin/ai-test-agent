"""
Day 18 练习 6：Pyright 避坑实战 —— RAG 场景的类型挑战

RAG 场景引入后，有几个新的类型安全问题需要处理。
本练习不调用 API，纯演示类型正确的写法 vs 错误的写法。

⚠️ 所有标注「❌ 错误」的代码行都有注释说明为什么不通过 Pyright，
   以及「✅ 正确」的替代写法。

用法：直接运行，全部是演示性质，不含 API 调用。
"""

import os
from langchain_core.documents import Document


# ═══════════════════════════════════════════════════════
# 坑 1：Document.metadata 取值需要类型注解
# ═══════════════════════════════════════════════════════

def pitfall1_metadata_access() -> None:
    """坑 1：Document.metadata 是 dict[str, Any]，取值需要注解或转换"""

    doc = Document(
        page_content="登录功能需求",
        metadata={"source": "requirement_login.txt", "page": 1},
    )

    # ❌ 错误：metadata.get() 返回 Any
    # source = doc.metadata.get("source")
    # 后续 source.upper() 等操作没有类型检查

    # ✅ 正确：显式转换
    source: str = str(doc.metadata.get("source", "unknown"))
    page: int = int(doc.metadata.get("page", 0))

    print(f"source: {source}, page: {page}")


# ═══════════════════════════════════════════════════════
# 坑 2：Chroma.from_documents 返回类型
# ═══════════════════════════════════════════════════════

def pitfall2_chroma_type() -> None:
    """坑 2：Chroma.from_documents() 返回 Chroma 对象，需要显式注解"""

    # ❌ 错误：不注解类型，返回 Any
    # vs = Chroma.from_documents(docs, embedding)
    # 后续 vs.similarity_search() 失去类型检查

    # ✅ 正确：显式注解
    from langchain_chroma import Chroma
    # vs: Chroma = Chroma.from_documents(docs, embedding)
    # 但因为需要实际 API 调用，这里只做说明

    print("✅ 类型注解: vectorstore: Chroma = Chroma.from_documents(...)")
    print("   后续调用 similarity_search 等都有完整的类型检查")


# ═══════════════════════════════════════════════════════
# 坑 3：similarity_search_with_score 返回的元组
# ═══════════════════════════════════════════════════════

def pitfall3_similarity_with_score() -> None:
    """坑 3：similarity_search_with_score 返回 list[tuple[Document, float]]"""

    # ❌ 错误：不注解返回值类型
    # results = vs.similarity_search_with_score("query")
    # for doc, score in results:  ← Pyright 不知道 doc 和 score 的类型

    from typing import cast

    # ✅ 正确：显式注解（实际上 IDE 会从函数签名推断，但显式写更安全）
    # results: list[tuple[Document, float]] = vs.similarity_search_with_score("query")
    # for doc, score in results:
    #     content: str = doc.page_content  # ✅ 类型明确
    #     score_val: float = score         # ✅ 类型明确

    # 模拟
    mock_results: list[tuple[Document, float]] = [
        (Document(page_content="匹配文本1", metadata={}), 0.95),
        (Document(page_content="匹配文本2", metadata={}), 0.82),
    ]

    for doc, score in mock_results:
        content: str = doc.page_content
        print(f"score={score:.2f}: {content[:40]}...")


# ═══════════════════════════════════════════════════════
# 坑 4：chunk_overlap 不能超过 chunk_size
# ═══════════════════════════════════════════════════════

def pitfall4_chunk_overlap_validation() -> None:
    """坑 4：chunk_overlap 必须 < chunk_size，这是业务约束而非类型约束"""

    # ❌ 错误（运行时可能出错）：
    # splitter = RecursiveCharacterTextSplitter(
    #     chunk_size=200,
    #     chunk_overlap=200,  # 等于 chunk_size！会导致无限循环
    # )

    # ✅ 正确：chunk_overlap < chunk_size
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    chunk_size: int = 500
    chunk_overlap: int = 100

    assert chunk_overlap < chunk_size, (
        f"chunk_overlap ({chunk_overlap}) 必须 < chunk_size ({chunk_size})"
    )

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    print(f"✅ splitter 创建成功: chunk_size={chunk_size}, chunk_overlap={chunk_overlap}")


# ═══════════════════════════════════════════════════════
# 坑 5：pathlib.glob 路径处理
# ═══════════════════════════════════════════════════════

def pitfall5_glob_pattern() -> None:
    """坑 5：pathlib.glob 的 pattern 不要包含完整路径"""

    from pathlib import Path

    # ❌ 错误：在 glob 参数中拼完整路径
    # wrong = Path("C:/some/path").glob("C:/some/path/*.txt")  # ❌

    # ✅ 正确：目录路径传给 Path()，glob 参数只写模式
    # docs_dir = Path("docs/requirements")
    # for filepath in docs_dir.glob("*.txt"):       # 当前目录下的 .txt
    # for filepath in docs_dir.glob("**/*.txt"):   # 递归匹配子目录

    print("✅ pathlib.glob 用法:")
    print("  Path(dir).glob('*.txt')      → 匹配目录下的 .txt 文件")
    print("  Path(dir).glob('**/*.txt')   → 递归匹配所有子目录")
    print("  ⚠️ glob 只写文件名模式，目录路径在 Path() 构造时指定")
    print("  ⚠️ Windows 路径使用 / 或 Path() 自动处理分隔符")


# ═══════════════════════════════════════════════════════
# 坑 6：embeddings 初始化 —— Pyright 与 Pydantic 签名冲突
# ═══════════════════════════════════════════════════════

def pitfall6_embeddings_api_key() -> None:
    """坑 6：GoogleGenerativeAIEmbeddings 的 google_api_key 参数 Pyright 报错"""
    import os

    # ❌ 错误（Pyright 报 No parameter named 'google_api_key'）：
    # embeddings = GoogleGenerativeAIEmbeddings(
    #     model="models/gemini-embedding-001",
    #     google_api_key=os.getenv("GEMINI_API_KEY"),
    # )
    # 原因：GoogleGenerativeAIEmbeddings 继承 Pydantic BaseModel，
    #      __init__ 签名是 (self, /, **data: Any)，
    #      Pyright 静态分析看不到任何具名参数。

    # ✅ 推荐：不显式传参，依赖环境变量自动加载
    # embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
    # 自动读取顺序：GOOGLE_API_KEY → GEMINI_API_KEY

    api_key = os.getenv("GEMINI_API_KEY")
    if api_key:
        print(f"✅ API Key 已配置 (长度 {len(api_key)})")
    else:
        print("⚠️ API Key 未配置，请检查 .env 文件")

    print("✅ 推荐写法：依赖环境变量 GEMINI_API_KEY，不显式传 google_api_key")


# ═══════════════════════════════════════════════════════
# 坑 7：HuggingFaceEmbeddings 首次运行自动下载模型
# ═══════════════════════════════════════════════════════

def pitfall7_hf_first_download() -> None:
    """坑 7：HuggingFaceEmbeddings 首次调用时自动下载模型，需联网"""

    # ⚠️ 首次调用 embed_query 或 embed_documents 时，
    #    HuggingFace 会自动从 huggingface.co 下载模型文件（~80MB）
    #    如果当时没有网络，会抛出 OSError

    # 解决方法：
    # 1. 确保首次运行时网络通畅
    # 2. 或者提前手动下载模型到本地缓存：
    #    model_name="sentence-transformers/all-MiniLM-L6-v2"
    #    缓存路径：~/.cache/huggingface/hub/

    print("✅ HuggingFace 注意事项：")
    print("  首次运行需联网下载模型（~80MB），之后离线使用")
    print("  如需断网运行：先在有网环境跑一次 embed_query('test')，模型会自动缓存")


# ═══════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════

def main() -> None:
    pitfall1_metadata_access()
    pitfall2_chroma_type()
    pitfall3_similarity_with_score()
    pitfall4_chunk_overlap_validation()
    pitfall5_glob_pattern()
    pitfall6_embeddings_api_key()
    pitfall7_hf_first_download()

    print("\n💡 RAG 场景 Pyright 避坑总结：")
    print("  1. metadata.get() 返回 Any，需要显式 str()/int() 转换")
    print("  2. Chroma.from_documents() 结果用 Chroma 类型注解")
    print("  3. similarity_search_with_score() 返回 tuple[Document, float]")
    print("  4. chunk_overlap 必须 < chunk_size（运行时校验）")
    print("  5. pathlib.glob 的 pattern 只写模式，不写路径")
    print("  6. GoogleGenerativeAIEmbeddings 不显式传 google_api_key（避免 Pyright + Pydantic 签名冲突）")
    print("  7. HuggingFaceEmbeddings 首次需联网下模型，之后离线")


if __name__ == "__main__":
    main()
