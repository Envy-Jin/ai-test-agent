"""
src/agent/hello_gemini.py —— Gemini API 初次调用

Day 8 核心练习：新版 google-genai SDK 的首次调用
新版 SDK 变化：不再用 genai.configure() + GenerativeModel，改用 genai.Client()
"""

from google import genai
import os
from dotenv import load_dotenv

# 1. 加载环境变量
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise ValueError("❌ 未找到 GEMINI_API_KEY，请检查 .env 文件")

# 2. 新版 SDK 创建客户端
client = genai.Client(api_key=api_key)

# # 3. 第一次调用——最简单的方式
# print("=" * 60)
# print("🔹 基础对话测试")
# print("=" * 60)


# response = client.models.generate_content(
#     model="gemini-3.5-flash",
#     contents="你好，请用一句话介绍你自己"
# )
# print(f"\nGemini 回答：\n{response.text}\n")

# # 4. 测试一个和测试相关的 Prompt
# print("=" * 60)
# print("🔹 测试领域问题测试")
# print("=" * 60)

# response2 = client.models.generate_content(
#     model="gemini-3.5-flash",
#     contents="作为一名测试工程师，请用 3 句话说明什么是「边界值测试」"
# )
# print(f"\nGemini 回答：\n{response2.text}\n")

# 5. 探索新版 response 对象的内容
print("=" * 60)
print("🔹 探索 response 对象结构")
print("=" * 60)

test_response = client.models.generate_content(
    model="gemini-3.1-flash-lite",
    contents="说一个字：好",
)

print(f"类型: {type(test_response)}")
print(f"text 属性: {test_response.text}")

# 候选结果
print(f"\ncandidates 数量: {len(test_response.candidates)}")
candidate = test_response.candidates[0]
print(f"finish_reason: {candidate.finish_reason}")
print(f"token_count: {candidate.token_count}")  # 新版可能不在 candidate 上
print(f"safety_ratings: {candidate.safety_ratings}")

# 使用统计
if hasattr(test_response, 'usage_metadata') and test_response.usage_metadata:
    usage = test_response.usage_metadata
    print(f"\nToken 使用统计:")
    print(f"  prompt_token_count: {usage.prompt_token_count}")
    print(f"  candidates_token_count: {usage.candidates_token_count}")
    print(f"  total_token_count: {usage.total_token_count}")
else:
    print("\nToken 使用统计: 当前响应中未包含")

# 模型反馈
print(f"\nmodel_version: {test_response.model_version}")