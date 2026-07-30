"""
src/agent/gemini_requirement_parser.py —— 用 AI 分析需求文档

Day 8 综合练习：对比「正则解析」和「AI 解析」的差异
"""

import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

# # 代理配置
# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

def parse_requirement_with_ai(requirement_text: str) -> dict:
    """
    使用 Gemini AI 解析需求文档

    Args:
        requirement_text: 需求文档文本

    Returns:
        结构化解析结果
    """
    prompt = f"""
你是一名资深软件测试工程师。请分析以下需求文档，提取结构化的测试信息。

需求文档：
{requirement_text}

请以 JSON 格式输出，结构如下：
{{
  "features": [
    {{
      "feature_name": "功能名称",
      "sub_features": ["子功能1", "子功能2"],
      "constraints": ["约束条件1", "约束条件2"],
      "suggested_test_types": ["推荐的测试类型"]
    }}
  ],
  "summary": "整体分析摘要"
}}
"""

    response = client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.1,
            response_mime_type="application/json",
        ),
    )
    return json.loads(response.text or "")


def compare_parsers():
    """
    对比「正则解析器（Day 6）」和「AI 解析器（Day 8）」的结果
    """
    print("=" * 60)
    print("🔬 对比实验：正则解析 vs AI 解析")
    print("=" * 60)

    # 用 Day 7 测试用的需求文档
    try:
        with open("docs/requirement.txt", "r", encoding="utf-8") as f:
            requirement_text = f.read()
    except FileNotFoundError:
        # 如果 docs/requirement.txt 不存在，用示例文本
        requirement_text = (
            "用户登录功能：支持手机号和邮箱登录，"
            "密码不少于8位且必须包含数字和字母，"
            "登录失败超过5次锁定账号30分钟。\n"
            "用户注册功能：需要手机号验证码，"
            "用户名长度3-20个字符，同一手机号不可重复注册。"
        )
        print("⚠️  docs/requirement.txt 不存在，使用内置示例\n")

    print(f"需求文本：\n{requirement_text}\n")
    print("-" * 40)

    # AI 解析
    print("🤖 AI 解析结果：")
    try:
        ai_result = parse_requirement_with_ai(requirement_text)
        print(json.dumps(ai_result, ensure_ascii=False, indent=2))
    except Exception as e:
        print(f"❌ AI 解析失败: {e}")

    print("\n" + "-" * 40)

    # 正则解析（如果模块可用）
    print("📐 正则解析结果（Day 6）：")
    try:
        from requirement_parser import parse_requirement
        regex_result = parse_requirement(requirement_text)
        print(f"功能数: {regex_result.total_features}")
        for f in regex_result.features:
            print(f"  功能: {f.feature}")
            print(f"  子功能: {f.sub_features}")
            print(f"  约束: {f.constraints}")
    except ImportError:
        print("（正则解析器未在 src/agent/ 下找到，请检查文件路径）")

    # print("\n💡 思考题：")
    # print("1. AI 解析和正则解析的结果有什么不同？")
    # print("2. 哪种方式更适合处理表述不规范的文本？")
    # print("3. 两种方式的成本和速度有什么区别？")
    # print("4. 什么时候应该用正则，什么时候应该用 AI？")

if __name__ == "__main__":
    compare_parsers()