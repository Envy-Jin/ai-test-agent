"""
Day 18 练习 3：文本向量化（Embeddings）

掌握 GoogleGenerativeAIEmbeddings：
  - embed_query()：将单条查询文本转为向量
  - embed_documents()：将文档列表批量转为向量
  - 理解向量维度与语义相似度的关系

⚠️ Pyright 注意事项：
  - embed_query() 返回 list[float]
  - embed_documents() 返回 list[list[float]]
  - GoogleGenerativeAIEmbeddings 初始化需要传入 model 参数
  - API Key 通过环境变量 GOOGLE_API_KEY 传递（已在 .env 中配置）

用法：直接运行跑全部实验，或在 main() 中注释掉不想跑的实验函数。
"""

import os
from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import GoogleGenerativeAIEmbeddings


# ═══════════════════════════════════════════════════════
# 模块级：Embedding 模型（所有实验共用）
# ═══════════════════════════════════════════════════════

embeddings = GoogleGenerativeAIEmbeddings(
    model="models/gemini-embedding-001",
    # google_api_key 自动从环境变量 GEMINI_API_KEY / GOOGLE_API_KEY 读取
    # 不显式传参：避免 Pyright + Pydantic **kwargs 签名检测冲突
)

# ═══════════════════════════════════════════════════════
# 实验 1：单条文本向量化
# ═══════════════════════════════════════════════════════

def exp1_single_embedding() -> None:
    """实验 1：将一条文本转为向量"""
    print("=" * 60)
    print("实验 1：单条文本向量化")
    print("=" * 60)

    text: str = "用户登录功能：支持手机号+密码登录，密码长度8-20位"
    vector: list[float] = embeddings.embed_query(text)

    print(f"输入文本: {text}")
    print(f"文本长度: {len(text)} 字符")
    print(f"向量维度: {len(vector)}")
    print(f"向量前 5 个值: {[round(v, 4) for v in vector[:5]]}")
    print(f"向量最后 5 个值: {[round(v, 4) for v in vector[-5:]]}")

    # 验证
    total: float = sum(v * v for v in vector)  # 向量平方和（通常不为 1，取决于模型）
    print(f"向量平方和（非归一化）: {total:.4f}")



# ═══════════════════════════════════════════════════════
# 实验 2：批量文档向量化
# ═══════════════════════════════════════════════════════

def exp2_batch_embedding() -> None:
    """实验 2：批量将多条文本转为向量"""
    print("\n" + "=" * 60)
    print("实验 2：批量文本向量化")
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
    print("实验 3：语义相似度对比")
    print("=" * 60)

    import math

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

    print(f"\n💡 观察：语义相近的文本（关于登录/测试）相似度高")
    print("  语义无关的文本（天气）相似度明显低 → 这就是语义检索的原理！")



# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    exp1_single_embedding()
    exp2_batch_embedding()
    exp3_semantic_similarity()

    print("\n💡 小结：")
    print("  - embed_query(string) → list[float]（单条转向量）")
    print("  - embed_documents(list[str]) → list[list[float]]（批量转向量）")
    print("  - 余弦相似度衡量语义距离，相近的文本相似度 > 0.8")
    print("  - 下一步：把向量存入 ChromaDB，实现高效检索")



# from google import genai
# from google.genai import types

# import os
# from dotenv import load_dotenv
# load_dotenv()
# client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
# text = "Hello World!"
# result = client.models.embed_content(
#     model="gemini-embedding-001",
#     contents=text,
#     config=types.EmbedContentConfig(output_dimensionality=10),
# )
# print(result.embeddings)
