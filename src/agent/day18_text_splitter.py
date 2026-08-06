"""
Day 18 练习 2：文档切分策略

掌握 RecursiveCharacterTextSplitter：
  - chunk_size：每个片段的最大字符数
  - chunk_overlap：相邻片段的重叠字符数（防止语义断裂）
  - separators：按优先级分隔符列表（段落 > 换行 > 空格 > 字符）

⚠️ Pyright 注意事项：
  - split_documents() 返回 list[Document]，类型明确
  - 切分后每个 Document 的 page_content 仍然是 str
  - metadata 会保留原文档的 source 信息

用法：直接运行跑全部实验，或在 main() 中注释掉不想跑的实验函数。
"""

import os
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document


DOCS_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "requirements")


def _load_file(filepath: str) -> list[Document]:
    """辅助函数：纯 Python 加载文件为 Document 列表（替代 langchain-community 的 TextLoader）"""
    with open(filepath, "r", encoding="utf-8") as f:
        content: str = f.read()
    return [Document(page_content=content, metadata={"source": filepath})]


# ═══════════════════════════════════════════════════════
# 实验 1：RecursiveCharacterTextSplitter 基础
# ═══════════════════════════════════════════════════════

def exp1_basic_splitter() -> None:
    """实验 1：RecursiveCharacterTextSplitter 基础用法"""
    print("=" * 60)
    print("实验 1：RecursiveCharacterTextSplitter 基础")
    print("=" * 60)

    file_path = os.path.join(DOCS_DIR, "login_requirement.md")
    docs: list[Document] = _load_file(file_path)
    original: Document = docs[0]

    print(f"原始文档: {len(original.page_content)} 字符")

    # 创建切分器
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=200,       # 每个片段最多 200 字符
        chunk_overlap=50,     # 相邻片段重叠 50 字符
        separators=["\n\n", "\n", "。", ".", " ", ""],  # 优先级从高到低
    )

    # 切分
    chunks: list[Document] = splitter.split_documents(docs)

    print(f"切分后: {len(chunks)} 个片段\n")

    for i, chunk in enumerate(chunks):
        print(f"--- 片段 {i + 1} ({len(chunk.page_content)} 字符) ---")
        preview: str = chunk.page_content.replace("\n", "↵")
        print(f"  {preview}...")
        print()

    print(f"💡 原始 1 个文档 → {len(chunks)} 个片段（每段 ≤ 200 字符，重叠 50 字符）")


# ═══════════════════════════════════════════════════════
# 实验 2：chunk_size 对切分结果的影响
# ═══════════════════════════════════════════════════════

def exp2_chunk_size_comparison() -> None:
    """实验 2：对比不同 chunk_size 的切分效果"""
    print("\n" + "=" * 60)
    print("实验 2：chunk_size 对比（100 vs 300 vs 500）")
    print("=" * 60)

    file_path = os.path.join(DOCS_DIR, "checkout_requirement.txt")
    docs: list[Document] = _load_file(file_path)

    for chunk_size in [100, 300, 500]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=30,
        )
        chunks: list[Document] = splitter.split_documents(docs)

        # 统计片段长度
        lengths: list[int] = [len(c.page_content) for c in chunks]
        avg_len: float = sum(lengths) / len(lengths) if lengths else 0

        print(f"\nchunk_size={chunk_size}:")
        print(f"  片段数: {len(chunks)}")
        print(f"  平均长度: {avg_len:.0f} 字符")
        print(f"  最短: {min(lengths)} 字符, 最长: {max(lengths)} 字符")

    print(f"\n💡 chunk_size 越大 → 片段数越少、每段越完整，但检索精度可能下降")

# ═══════════════════════════════════════════════════════
# 实验 3：chunk_overlap 的作用
# ═══════════════════════════════════════════════════════

def exp3_chunk_overlap_demo() -> None:
    """实验 3：chunk_overlap 如何防止语义断裂"""
    print("\n" + "=" * 60)
    print("实验 3：chunk_overlap —— 防止语义断裂")
    print("=" * 60)

    # 构造一段"切口处"可能断裂的文本
    sample_text: str = (
        "等价类划分法是软件测试中的一种黑盒测试方法。"
        "它将输入数据划分为若干个等价类，从每个等价类中选取代表性数据进行测试。"
        "等价类分为有效等价类和无效等价类。有效等价类是指符合需求规范的输入，"
        "无效等价类是指不符合需求规范的输入。"
    )

    from langchain_core.documents import Document as Doc
    sample_doc = Doc(page_content=sample_text, metadata={"source": "测试理论"})

    # 不重叠 vs 重叠
    for overlap in [0, 30]:
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=80,
            chunk_overlap=overlap,
        )
        chunks: list[Document] = splitter.split_documents([sample_doc])

        print(f"\nchunk_overlap={overlap}: {len(chunks)} 个片段")
        for i, chunk in enumerate(chunks):
            print(f"  [{i}] {chunk.page_content[:60]}...")

        if overlap == 0:
            print("  ⚠️ 无重叠：可能在句子中间断开，丢失上下文")
        else:
            print("  ✅ 有重叠：相邻片段共享内容，语义更连贯")


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    exp1_basic_splitter()
    # exp2_chunk_size_comparison()
    # exp3_chunk_overlap_demo()

    print("\n💡 小结：")
    print("  - RecursiveCharacterTextSplitter 按优先级分隔符递归切分")
    print("  - chunk_size 控制片段大小，平衡完整性和精度")
    print("  - chunk_overlap 防止切口处语义断裂")
    print("  - 切分后每个片段仍是 Document 对象（保留 metadata）")
    print("  - 下一步：把文本片段向量化（Embedding）")