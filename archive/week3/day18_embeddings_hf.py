"""
Day 18 练习 3b：HuggingFace 本地 Embedding（替代 Google API 方案）

掌握 HuggingFaceEmbeddings：
  - model_name 指定本地模型
  - embed_query()：将单条查询文本转为向量
  - embed_documents()：将文档列表批量转为向量
  - 与 Google API 版本代码结构一致，仅 Embedding 实现不同

⚠️ Pyright 注意事项：
  - HuggingFaceEmbeddings 也继承 Pydantic BaseModel，但不传 model_kwargs 时无签名问题
  - 首次运行会自动下载模型（约 80MB），之后离线使用
  - 依赖：pip install langchain-huggingface sentence-transformers

用法：直接运行跑全部实验，或在 main() 中注释掉不想跑的实验函数。
"""

import os
# os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"

import math
from dotenv import load_dotenv

load_dotenv()

from langchain_huggingface import HuggingFaceEmbeddings

# ═══════════════════════════════════════════════════════
# 模块级：Embedding 模型（所有实验共用）
# ═══════════════════════════════════════════════════════

embeddings = HuggingFaceEmbeddings(
    # model_name="models/models/BAAI--bge-small-zh-v1.5/snapshots/master",
    model_name="sentence-transformers/all-MiniLM-L6-v2",
    model_kwargs={"local_files_only": True},
    # 本地运行：无需 API Key，384 维向量
    # 首次运行自动下载 ~80MB，之后离线
)

# ═══════════════════════════════════════════════════════
# 实验 1：单条文本向量化
# ═══════════════════════════════════════════════════════

def exp1_single_embedding() -> None:
    """实验 1：将一条文本转为向量"""
    print("=" * 60)
    print("实验 1：单条文本向量化（HuggingFace）")
    print("=" * 60)

    text: str = "用户登录功能：支持手机号+密码登录，密码长度8-20位"
    vector: list[float] = embeddings.embed_query(text)

    print(f"输入文本: {text}")
    print(f"文本长度: {len(text)} 字符")
    print(f"向量维度: {len(vector)}")       # all-MiniLM-L6-v2 = 384 维
    print(f"向量前 5 个值: {[round(v, 4) for v in vector[:5]]}")
    print(f"向量最后 5 个值: {[round(v, 4) for v in vector[-5:]]}")
    print(f"⚡ 本地推理，无网络延迟")


# ═══════════════════════════════════════════════════════
# 实验 2：批量文档向量化
# ═══════════════════════════════════════════════════════

def exp2_batch_embedding() -> None:
    """实验 2：批量将多条文本转为向量"""
    print("\n" + "=" * 60)
    print("实验 2：批量文本向量化（HuggingFace）")
    print("=" * 60)

    texts: list[str] = [
        "登录功能：手机号+密码验证",
        "注册功能：手机号+验证码注册",
        "支付功能：微信支付和支付宝",
        "测试规范：等价类划分和边界值分析",
    ]

    vectors: list[list[float]] = embeddings.embed_documents(texts)

    for i, (text, vec) in enumerate(zip(texts, vectors)):
        print(f"\n[{i}] \"{text[:30]}...\"")
        print(f"    向量维度: {len(vec)}")
        print(f"    前 3 个值: {[round(v, 4) for v in vec[:3]]}")

    print(f"\n💡 {len(texts)} 条文本 → {len(vectors)} 个 {len(vectors[0])} 维向量")


# ═══════════════════════════════════════════════════════
# 实验 3：语义相似度对比
# ═══════════════════════════════════════════════════════

def exp3_semantic_similarity() -> None:
    """实验 3：计算文本间的语义相似度（余弦相似度）"""
    print("\n" + "=" * 60)
    print("实验 3：语义相似度对比（HuggingFace）")
    print("=" * 60)

    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """计算两个向量的余弦相似度"""
        dot: float = sum(x * y for x, y in zip(a, b))
        norm_a: float = math.sqrt(sum(x * x for x in a))
        norm_b: float = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    # 查询
    query: str = "登录功能的测试用例"
    query_vec: list[float] = embeddings.embed_query(query)

    # 候选文档
    candidates: list[str] = [
        "用户登录功能：手机号+密码验证，连续输错锁定",
        "用户注册功能：手机号+验证码，密码规则",
        "支付功能：微信支付回调验签",
        "登录页面的 UI 自动化测试脚本",
        "今天天气真好，适合出去玩",
    ]

    print(f"查询: \"{query}\"\n")
    print("候选文本的语义相似度:")

    results: list[tuple[str, float]] = []
    for candidate in candidates:
        cand_vec: list[float] = embeddings.embed_query(candidate)
        sim: float = cosine_similarity(query_vec, cand_vec)
        results.append((candidate, sim))

    # 按相似度排序
    results.sort(key=lambda x: x[1], reverse=True)
    for text, sim in results:
        bar: str = "█" * int(sim * 40)
        print(f"  {sim:.3f} {bar} \"{text[:40]}...\"")

    print(f"\n💡 Google API 版本和 HuggingFace 版本的排名应该高度一致")
    print("  → 说明 Embedding 的具体实现可以互换，不影响语义检索效果")


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    exp1_single_embedding()
    exp2_batch_embedding()
    exp3_semantic_similarity()

    print("\n💡 小结：")
    print("  - HuggingFaceEmbeddings 本地运行，无需 API Key")
    print("  - 向量维度 = 384（all-MiniLM-L6-v2） vs 3072（Google gemini-embedding-001）")
    print("  - 底层实现不同，但 LangChain 接口完全一致（embed_query / embed_documents）")
    print("  - 如需更好的中文效果：换用 BAAI/bge-small-zh-v1.5")



# # 一次性脚本：把模型下载到项目目录 ./models/ 下
# from modelscope import snapshot_download

# model_dir = snapshot_download(
#     "BAAI/bge-small-zh-v1.5",
#     cache_dir="./models",
# )
# print(model_dir)  # 打印下载路径，记下来