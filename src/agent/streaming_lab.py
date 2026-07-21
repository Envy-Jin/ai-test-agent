"""
src/agent/streaming_lab.py —— 流式输出实验室

Day 10 核心练习：掌握 stream=True 流式输出
让长内容实时打印，不再卡顿等待
"""

from google import genai
from google.genai import types
import os
import time
from dotenv import load_dotenv

# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-3.1-flash-lite"



# ============================================================
# 实验 1：非流式 vs 流式 —— 直观对比
# ============================================================

def compare_stream_vs_normal():
    """对比非流式和流式输出的体验差异"""
    print("=" * 60)
    print("🧪 实验 1：非流式 vs 流式输出对比")
    print("=" * 60)

    prompt = "请详细描述软件测试的 5 个阶段，每个阶段 2-3 句话。"

    # 方式 A：非流式（等全部生成完才返回）
    print("\n--- 方式 A：非流式（一次性返回） ---")
    start_a = time.time()
    resp = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.3),
    )
    elapsed_a = time.time() - start_a
    print(f"⏱️  等待 {elapsed_a:.2f}s 后一次性输出：")
    print(resp.text[:300] + "..." if resp.text else "没有内容")

    # 方式 B：流式（边生成边打印）
    print("\n--- 方式 B：流式（实时打印） ---")
    start_b = time.time()
    first_chunk_time = None
    print("⏱️  实时输出：")
    for chunk in client.models.generate_content_stream(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.3),
    ):
        if first_chunk_time is None:
            first_chunk_time = time.time() - start_b
            print(f"\n   （首字延迟 {first_chunk_time:.2f}s）")
        print(chunk.text, end="", flush=True)  # 实时打印，不换行
    elapsed_b = time.time() - start_b
    print(f"\n\n   总耗时 {elapsed_b:.2f}s")

    print("\n" + "-" * 60)
    print("💡 对比结论：")
    print(f"   - 非流式：等 {elapsed_a:.2f}s 才看到任何输出")
    print(f"   - 流式：{first_chunk_time:.2f}s 就开始看到输出")
    print(f"   - 总耗时差不多，但流式的「首字延迟」更小，体验更好")
    print(f"   - 生成内容越长，流式的体验优势越明显")


# ============================================================
# 实验 2：流式生成测试用例 —— 长内容不卡顿
# ============================================================

def stream_test_cases():
    """流式生成大量测试用例"""
    print("\n" + "=" * 60)
    print("🧪 实验 2：流式生成测试用例")
    print("=" * 60)

    prompt = """你是资深测试工程师。为「电商购物车功能」生成至少 15 个测试用例。
每个用例包含：编号、标题、类型（正向/边界/异常）、优先级、预期结果。
用 Markdown 表格格式输出。"""

    print("流式输出中（像打字机一样实时显示）...\n")
    print("-" * 60)

    full_text = ""
    chunk_count = 0
    for chunk in client.models.generate_content_stream(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.3),
    ):
        text = chunk.text
        if text:
            print(text, end="", flush=True)
            full_text += text
            chunk_count += 1

    print(f"\n\n{'-' * 60}")
    print(f"💡 共收到 {chunk_count} 个 chunk，总长度 {len(full_text)} 字符")
    print("   流式输出适合：长文档生成、实时聊天、进度反馈")


# ============================================================
# 实验 3：带 system_instruction 的流式输出
# ============================================================

def stream_with_system_prompt():
    """流式输出也支持 system_instruction"""
    print("\n" + "=" * 60)
    print("🧪 实验 3：带角色设定的流式输出")
    print("=" * 60)

    system_prompt = (
        "你是一名有 10 年经验的资深软件测试工程师。"
        "回答专业、简洁、有结构。"
    )

    print("问题：什么是探索性测试？如何有效开展？\n")
    print("-" * 60)

    for chunk in client.models.generate_content_stream(
        model=MODEL,
        contents="什么是探索性测试？如何有效开展？请给出实操建议。",
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.4,
        ),
    ):
        print(chunk.text, end="", flush=True)

    print(f"\n{'-' * 60}")
    print("💡 流式输出 + system_instruction 完美配合")


# ============================================================
# 实验 4：流式 + 结构化输出（JSON 拼接技巧）
# ============================================================

# 导入 Day 9 的 Schema
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from case_schema import TestCaseCollection


def stream_with_schema():
    """流式输出 + JSON Schema：边打印边拼接，最后解析"""
    print("\n" + "=" * 60)
    print("🧪 实验 4：流式 + 结构化输出")
    print("=" * 60)

    system_prompt = "你是一名资深软件测试工程师。"

    prompt = """请为以下需求生成测试用例，覆盖正向、边界、异常场景。

需求：用户注册功能，需要手机号验证码，密码不少于8位且含数字和字母，用户名3-20个字符。"""

    print("流式生成中（同时拼接 JSON）...\n")

    # 流式输出时，JSON 是分片返回的
    full_text = ""
    chunk_count = 0

    for chunk in client.models.generate_content_stream(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
            response_mime_type="application/json",
            response_schema=TestCaseCollection,  # 配合 Schema
        ),
    ):
        text = chunk.text
        if text:
            print(text, end="", flush=True)  # 实时打印 JSON 片段
            full_text += text  # 关键：拼接完整文本
            chunk_count += 1

    print(f"\n\n{'-' * 60}")
    print(f"共收到 {chunk_count} 个 chunk")

    # 关键：拼接完整后再解析
    print("\n🔧 拼接完整后解析 JSON...")
    collection = TestCaseCollection.model_validate_json(full_text)

    print(f"✅ 解析成功！")
    print(f"   功能名：{collection.feature_name}")
    print(f"   用例数：{len(collection.test_cases)}")
    for tc in collection.test_cases:
        print(f"   {tc.id} [{tc.priority}] [{tc.type}] {tc.title}")

    print("\n💡 流式 + 结构化输出的要点：")
    print("   1. 每个 chunk.text 是 JSON 片段，不能单独解析")
    print("   2. 必须拼接所有 chunk 后再 model_validate_json()")
    print("   3. 适合：需要实时展示进度 + 最终拿到结构化数据的场景")


# ============================================================
# 实验 5：封装一个流式结构化输出工具函数
# ============================================================

def stream_and_parse(prompt: str, schema_class, system_instruction: str = ""):
    """
    流式输出并最终解析为结构化对象

    Args:
        prompt: 提示文本
        schema_class: Pydantic 模型类
        system_instruction: 系统提示

    Returns:
        解析后的 Pydantic 对象
    """
    config_kwargs = {
        "temperature": 0.2,
        "response_mime_type": "application/json",
        "response_schema": schema_class,
    }
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction

    full_text = ""
    for chunk in client.models.generate_content_stream(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(**config_kwargs),
    ):
        if chunk.text:
            print(chunk.text, end="", flush=True)
            full_text += chunk.text

    return schema_class.model_validate_json(full_text)


def demo_stream_and_parse():
    """演示封装的流式解析工具函数"""
    print("\n" + "=" * 60)
    print("🧪 实验 5：封装的 stream_and_parse 工具函数")
    print("=" * 60)

    print("\n流式生成 + 自动解析中...\n")

    collection = stream_and_parse(
        prompt="为「搜索功能，支持关键词搜索，结果分页每页20条」生成测试用例",
        schema_class=TestCaseCollection,
        system_instruction="你是资深测试工程师，生成覆盖正向/边界/异常的测试用例。",
    )

    print(f"\n\n✅ 自动解析完成：{collection.feature_name}，{len(collection.test_cases)} 个用例")


if __name__ == "__main__":
    # compare_stream_vs_normal()
    # stream_test_cases()
    # stream_with_system_prompt()
    # stream_with_schema()          
    demo_stream_and_parse()       
    print("\n✅ 流式输出实验完成！")