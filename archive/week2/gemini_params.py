"""
src/agent/gemini_params.py —— Gemini API 参数实验

Day 8 核心练习：理解 temperature、max_output_tokens、response_mime_type（JSON 模式）
新版 SDK：使用 genai.types.GenerateContentConfig 配置参数
"""

from google import genai
from google.genai import types
import os
import json
from dotenv import load_dotenv

load_dotenv()

api_key=os.getenv("GEMINI_API_KEY")
if not api_key:
    raise ValueError("❌ 未找到 GEMINI_API_KEY，请检查 .env 文件")

client = genai.Client(api_key=api_key)

MODEL = "gemini-3.1-flash-lite"  # 统一使用的模型

# ============================================================
# 实验 1：temperature 对比 —— 越低越确定，越高越随机
# ============================================================

def experiment_temperature():
    """用同一个 Prompt，观察不同 temperature 下输出的差异"""
    print("=" * 60)
    print("🔬 实验 1：temperature 对输出创造性的影响")
    print("=" * 60)

    prompt = "为一个电商网站的登录功能生成 3 个测试用例标题，每个不超过 20 字"

    for temp in [0.0, 0.3, 0.7, 1.0, 1.5]:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=temp,
                max_output_tokens=300,
            ),
        )
        print(f"\n--- temperature = {temp} ---")
        print(response.text)
        print("-" * 40)

# ============================================================
# 实验 2：max_output_tokens —— 控制输出长度
# ============================================================

def experiment_max_tokens():
    """限制输出长度，观察截断效果"""
    print("\n" + "=" * 60)
    print("🔬 实验 2：max_output_tokens 输出长度限制")
    print("=" * 60)

    prompt = "请详细描述一个完整的软件测试流程，从需求分析到上线发布"

    for max_tok in [50, 150, 500]:
        response = client.models.generate_content(
            model=MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=max_tok,
            ),
        )
        text = response.text
        print(f"\n--- max_output_tokens = {max_tok} ---")
        print(f"实际输出长度: {len(text)} 字符")
        print(text[:200] + ("..." if len(text) > 200 else ""))
        print("-" * 40)


# ============================================================
# 实验 3：response_mime_type —— 强制 JSON 输出
# ============================================================

def experiment_json_mode():
    """使用 response_mime_type 让 Gemini 直接返回合法 JSON"""
    print("\n" + "=" * 60)
    print("🔬 实验 3：response_mime_type 强制 JSON 输出")
    print("=" * 60)

    prompt = (
        "生成 3 个用户登录功能的测试用例。"
        "每个用例包含字段：id, title, priority, type, steps, expected_result"
    )

    # 方式 A：不强制 JSON
    print(f"\n方式 A（不强制 JSON）：")
    response_a = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2),
    )
    text_a = response_a.text
    print(f"原始文本前 200 字符: {text_a[:200]}")

    # 方式 B：强制 JSON（response_mime_type）
    print(f"\n方式 B（response_mime_type='application/json'）：")
    response_b = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )
    text_b = response_b.text
    try:
        data = json.loads(text_b)
        print(f"✅ 解析成功！自动成为 Python dict，无需清洗")
        print(f"类型: {type(data)}")
        print(f"内容: {json.dumps(data, ensure_ascii=False, indent=2)[:300]}")
    except json.JSONDecodeError as e:
        print(f"❌ 解析失败: {e}")

    print(f"\n💡 结论：response_mime_type='application/json' 让 Gemini 直接输出合法 JSON，无需手动清洗 markdown 代码块")


# ============================================================
# 实验 4：temperature 在测试用例场景的最佳实践
# ============================================================

def experiment_best_temperature():
    """寻找测试用例生成场景的最佳 temperature 值"""
    print("\n" + "=" * 60)
    print("🔬 实验 4：测试用例生成场景的 temperature 最佳实践")
    print("=" * 60)

    requirement = "用户注册功能，需输入手机号、密码（不少于8位含数字和字母）、验证码"

    for temp in [0.0, 0.1, 0.2, 0.5]:
        response = client.models.generate_content(
            model=MODEL,
            contents=(
                f"需求：{requirement}\n\n"
                "请生成 3 个测试用例（1个正向、1个边界、1个异常），以 JSON 格式输出"
            ),
            config=types.GenerateContentConfig(
                temperature=temp,
                response_mime_type="application/json",
            ),
        )
        print(f"\n--- temperature = {temp} ---")
        print(f"输出前 250 字符: {response.text[:250]}")
        print("-" * 40)

    print("\n💡 结论提示：temperature = 0.1~0.2 最适合生成结构化测试用例")
    print("   太低(0.0)可能过于死板，太高(>0.5)可能导致格式不稳定")


# ============================================================
# 运行所有实验
# ============================================================

if __name__ == "__main__":
    # experiment_temperature()
    experiment_max_tokens()
    # experiment_json_mode()
    # experiment_best_temperature()
    print("\n✅ 所有实验完成！")