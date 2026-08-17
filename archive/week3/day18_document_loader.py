"""
Day 18 练习 1：文档对象创建与加载

掌握 LangChain Document 对象 + 纯 Python 文件 I/O：
  - Document(page_content=..., metadata={...}) 创建文档对象
  - open() + .read() 加载单个文本文件
  - pathlib.Path.glob() 批量加载目录下所有文件

  为什么不用 langchain-community 的 TextLoader？
  - langchain-community 已于 2026-05 被官方 sunset
  - TextLoader 本质上就是 open() + Document() 的封装
  - 纯 Python 写法更简单、零额外依赖、不受废弃影响

⚠️ Pyright 注意事项：
  - Document.page_content 是 str，不是 str | None
  - Document.metadata 是 dict[str, Any]，取值需要 str() 转换
  - 文件路径使用绝对路径或基于 __file__ 的相对路径

用法：直接运行跑全部实验，或在 main() 中注释掉不想跑的实验函数。
"""

import os
from pathlib import Path
from typing import Any
from langchain_core.documents import Document

from dotenv import load_dotenv
load_dotenv()


# ═══════════════════════════════════════════════════════
# 模块级：文档目录路径（所有实验共用）
# ═══════════════════════════════════════════════════════

DOCS_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "requirements")


# ═══════════════════════════════════════════════════════
# 辅助函数：加载单个文件（纯 Python 实现，替代 langchain-community 的 TextLoader）
# ═══════════════════════════════════════════════════════

def load_text_file(filepath: str) -> list[Document]:
    """加载单个文本文件为 Document 对象列表。

    等价于 langchain_community 的 TextLoader(filepath, encoding='utf-8').load()
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content: str = f.read()
    return [Document(page_content=content, metadata={"source": filepath})]


def load_text_directory(directory: str, extensions: tuple[str, ...] = (".txt", ".md")) -> list[Document]:
    """批量加载目录下的文本文件为 Document 对象列表。

    等价于 langchain_community 的 DirectoryLoader(directory, glob=glob_pattern, ...).load()
    """
    docs: list[Document] = []
    for filepath in Path(directory).iterdir():
        if not filepath.suffix in extensions:
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        docs.append(Document(page_content=content, metadata={"source": str(filepath)}))
    return docs

# ═══════════════════════════════════════════════════════
# 实验 1：加载单个文件
# ═══════════════════════════════════════════════════════

def exp1_load_single_file() -> None:
    """实验 1：用纯 Python open() + Document() 加载单个需求文档"""
    print("=" * 60)
    print("实验 1：纯 Python 加载单个文档")
    print("=" * 60)

    file_path = os.path.join(DOCS_DIR, "checkout_requirement.txt")
    docs: list[Document] = load_text_file(file_path)

    print(f"加载了 {len(docs)} 个 Document 对象")
    print(f"内容长度: {len(docs[0].page_content)} 字符")
    print(f"元数据: {docs[0].metadata}")
    print(f"\n内容预览（前 200 字符）:")
    print(docs[0].page_content[:200])
    print("...")


# ═══════════════════════════════════════════════════════
# 实验 2：批量加载目录
# ═══════════════════════════════════════════════════════

def exp2_batch_load_directory() -> None:
    """实验 2：用 pathlib.glob() + Document() 批量加载目录"""
    print("\n" + "=" * 60)
    print("实验 2：pathlib.glob() 批量加载目录")
    print("=" * 60)

    docs: list[Document] = load_text_directory(DOCS_DIR)

    print(f"加载了 {len(docs)} 个文档")
    for i, doc in enumerate(docs):
        source: str = str(doc.metadata.get("source", "unknown"))
        print(f"  [{i}] {os.path.basename(source)}: {len(doc.page_content)} 字符")

    # 统计总内容量
    total_chars: int = sum(len(d.page_content) for d in docs)
    print(f"\n📊 总计: {total_chars} 字符，{len(docs)} 个文档")


# ═══════════════════════════════════════════════════════
# 实验 3：Document 对象深入 —— 元数据与内容
# ═══════════════════════════════════════════════════════

def exp3_document_metadata() -> None:
    """实验 3：探索 Document 对象的 page_content 与 metadata"""
    print("\n" + "=" * 60)
    print("实验 3：Document 对象深入 —— page_content 与 metadata")
    print("=" * 60)

    file_path = os.path.join(DOCS_DIR, "checkout_requirement.txt")
    docs: list[Document] = load_text_file(file_path)
    doc: Document = docs[0]

    # 元数据字段
    print("--- 元数据 ---")
    for key, value in doc.metadata.items():
        print(f"  {key}: {value}")

    # ⚠️ Pyright 友好：doc.page_content 是 str 类型
    content: str = doc.page_content

    # 统计
    lines: list[str] = content.split("\n")
    print(f"\n--- 内容统计 ---")
    print(f"  行数: {len(lines)}")
    print(f"  字符数: {len(content)}")
    print(f"  非空行数: {len([l for l in lines if l.strip()])}")

    # Document 的 type 属性
    print(f"\n  Document type: {doc.type}")
    print(f"  Document id: {doc.id}")


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    exp1_load_single_file()
    exp2_batch_load_directory()
    exp3_document_metadata()

    print("\n💡 小结：")
    print("  - Document(page_content=..., metadata=...) 创建文档对象")
    print("  - open() + .read() 加载单个文件 → list[Document]")
    print("  - pathlib.Path.glob() 批量加载目录文件")
    print("  - Document 包含 page_content（文本）+ metadata（元数据）")
    print("  - 下一步：把长文档切成小片段，便于检索")
