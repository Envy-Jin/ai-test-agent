"""
src/agent/json_extract_lab.py —— JSON 提取实战实验室

Day 12 核心练习：让 Gemini 生成 JSON（不用 response_schema），然后用 extract_json 提取
对比「有 Schema」和「无 Schema」两种模式下的输出质量和提取难度
"""

from google import genai
from google.genai import types
import os
from dotenv import load_dotenv
from utils import safe_text
from json_extractor import extract_json, extract_json_with_fallback, validate_json_schema

# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-3.1-flash-lite"

# ============================================================
# 实验 1：无 Schema 自由生成 → extract_json 提取
# ============================================================

def experiment_free_json():
    """让 Gemini 自由生成 JSON（不强制 Schema），观察输出格式的不确定性"""
    print("=" * 60)
    print("🧪 实验 1：无 Schema 自由生成 → 提取 JSON")
    print("=" * 60)

    prompt = """请为「用户登录功能」生成 5 个测试用例。
要求以 JSON 格式输出，格式如下：
{"test_cases": [{"id": "TC001", "title": "...", "type": "正向/边界/异常", "priority": "P0/P1/P2"}]}
不要添加任何额外文字。"""

    # 不用 response_schema，只靠 Prompt 要求 JSON
    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            # 注意：没有 response_schema，也没有 response_mime_type
        ),
    )
    raw_text = safe_text(response)
    print(f"原始输出（前 300 字）:\n{raw_text[:300]}...\n")

    # 用 extract_json 提取
    result = extract_json(raw_text)
    if result:
        print(f"✅ 提取成功！")
        print(f"   类型: {type(result).__name__}")
        if isinstance(result, dict) and "test_cases" in result:
            print(f"   用例数: {len(result['test_cases'])}")
            for tc in result['test_cases'][:3]:
                print(f"   {tc.get('id', '?')} [{tc.get('priority', '?')}] {tc.get('title', '?')}")
        else:
            print(f"   内容: {str(result)[:200]}")
    else:
        print("❌ 提取失败！")

    print("-" * 60)
    print("💡 无 Schema 的输出不确定性：")
    print("   - 可能包在代码块里")
    print("   - 可能前后有额外文字")
    print("   - 可能格式不完全符合要求")
    print("   - extract_json 能应对这些不确定性")


# ============================================================
# 实验 2：JSON 模式（response_mime_type）→ extract_json 提取
# ============================================================

def experiment_json_mode():
    """用 response_mime_type='application/json' 强制 JSON，但不用 Schema"""
    print("\n" + "=" * 60)
    print("🧪 实验 2：JSON 模式强制 → 提取 JSON")
    print("=" * 60)

    prompt = """请为「购物车功能」生成 5 个测试用例。
输出 JSON 格式：{"test_cases": [{"id": "...", "title": "...", "priority": "..."}]}"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",  # 强制 JSON，但不定义 Schema
        ),
    )
    raw_text = safe_text(response)
    print(f"原始输出（前 300 字）:\n{raw_text[:300]}...\n")

    # 即使是 JSON 模式，也走 extract_json（更安全）
    result = extract_json(raw_text)
    if result:
        print(f"✅ 提取成功！")
        if isinstance(result, dict) and "test_cases" in result:
            print(f"   用例数: {len(result['test_cases'])}")
    else:
        print("❌ 提取失败！")

    print("-" * 60)
    print("💡 JSON 模式的输出更纯净：")
    print("   - 通常直接返回纯 JSON（不带代码块和前后缀）")
    print("   - 但 JSON 的内部结构不一定完全符合你的要求")
    print("   - extract_json 仍然适用——它对纯 JSON 提取最快")

# ============================================================
# 实验 3：Schema 强制 → 提取对比
# ============================================================

def experiment_schema_mode():
    """用 response_schema 强制精确结构，对比提取难度"""
    from case_schema import TestCaseCollection

    print("\n" + "=" * 60)
    print("🧪 实验 3：Schema 强制 → 最可靠的输出方式")
    print("=" * 60)

    prompt = """请为「搜索功能，支持关键词搜索」生成测试用例"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
            response_schema=TestCaseCollection,
        ),
    )
    raw_text = safe_text(response)

    # Schema 模式下，两种方式都能拿到结果：
    # 方式 A：extract_json（通用提取）
    result_a = extract_json(raw_text)
    if isinstance(result_a, dict):
        fields_a = list(result_a.keys())
    elif isinstance(result_a, list):
        fields_a = f"列表（{len(result_a)} 项）"
    else:
        fields_a = 'None'
    print(f"方式 A（extract_json）: {type(result_a).__name__}, 字段: {fields_a}")

    # 方式 B：Pydantic model_validate_json（精确解析）
    result_b = TestCaseCollection.model_validate_json(raw_text)
    print(f"方式 B（Pydantic）: {result_b.feature_name}, {len(result_b.test_cases)} 个用例")


    print("-" * 60)
    print("💡 Schema 是最可靠的方式：")
    print("   - 输出保证是合法 JSON")
    print("   - 内部结构保证符合 Schema 定义")
    print("   - 可以直接 model_validate_json() 解析")
    print("   - extract_json 仍然适用（作为兜底）")
    print("   - 优先用 Schema，extract_json 作为通用兜底策略")


# ============================================================
# 实验 4：extract_json_with_fallback 兜底实战
# ============================================================

def experiment_fallback():
    """当所有策略都失败时，fallback 保证不崩溃"""
    print("\n" + "=" * 60)
    print("🧪 实验 4：fallback 兜底实战")
    print("=" * 60)

    # 模拟安全过滤拦截（response.text 为空）
    empty_text = ""
    result = extract_json_with_fallback(empty_text, fallback={
        "test_cases": [],
        "error": "empty_response",
        "message": "模型返回了空内容",
    })
    print(f"空文本 → fallback: {result}")

    # 模拟完全无法解析的输出
    garbage_text = "这是一段完全没有 JSON 的自然语言回答。"
    result2 = extract_json_with_fallback(garbage_text, fallback={
        "test_cases": [],
        "error": "no_json_found",
    })
    print(f"无法解析 → fallback: {result2}")

    print("-" * 60)
    print("💡 fallback 的应用价值：")
    print("   - 下游代码永远不会因为「提取失败」而崩溃")
    print("   - fallback 带有 error 字段，方便日志排查")
    print("   - 适合 API 后端、自动化流水线等不允许崩溃的场景")

if __name__ == "__main__":
    # experiment_free_json()
    # experiment_json_mode()
    # experiment_schema_mode()
    experiment_fallback()
    print("\n✅ JSON 提取实战实验全部完成！")