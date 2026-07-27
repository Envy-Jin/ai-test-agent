"""
src/agent/json_extractor.py —— LLM 输出的 JSON 提取器

Day 12 核心工具：从 LLM 的不确定输出中，可靠地提取 JSON
三重策略：直接解析 → 代码块提取 → 正则兜底
辅以 fallback 机制和 Schema 校验
"""

import json
import re
from typing import Any

def extract_json(text: str) -> dict | list | None:
    """
    从文本中提取 JSON 对象或数组。

    按优先级尝试三种策略：
    1. 直接解析（最理想：text 本身就是纯 JSON）→ 对应场景 1
    2. 代码块提取（最常见：JSON 被 ```json ... ``` 包裹）→ 对应场景 2
    3. 正则兜底（最顽固：JSON 混在自由文字中）→ 对应场景 3

    Args:
        text: LLM 的输出文本

    Returns:
        解析后的 dict 或 list，提取失败返回 None

    Examples:
        >>> extract_json('{"name": "test"}')
        {"name": "test"}

        >>> extract_json('结果如下：\\n```json\\n{"name": "test"}\\n```')
        {"name": "test"}

        >>> extract_json('无效内容')
        None
    """
    if not text or not text.strip():
        return None

    # 策略 1：直接解析（最快）→ 场景 1
    result = _try_direct_parse(text)
    if result is not None:
        return result

    # 策略 2：代码块提取（最常见）→ 场景 2
    result = _try_code_block_parse(text)
    if result is not None:
        return result

    # 策略 3：正则兜底（最顽固）→ 场景 3
    result = _try_regex_parse(text)
    if result is not None:
        return result

    return None

def _try_direct_parse(text: str) -> dict | list | None:
    """策略 1：直接 json.loads"""
    try:
        return json.loads(text.strip())
    except json.JSONDecodeError:
        return None

def _try_code_block_parse(text: str) -> dict | list | None:
    """策略 2：从 ```json ... ``` 或 ``` ... ``` 代码块中提取"""
    # 优先匹配 ```json 代码块
    pattern_json = r'```(?:json)?\s*\n?(.*?)\n?\s*```'
    match = re.search(pattern_json, text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass

    return None

def _try_regex_parse(text: str) -> dict | list | None:
    """策略 3：用正则匹配 { ... } 或 [ ... ] 结构"""
    # 匹配 JSON 对象（以 { 开头，以 } 结尾）
    pattern_obj = r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}'
    # 匹配 JSON 数组（以 [ 开头，以 ] 结尾）
    pattern_arr = r'$$[^\[$$]*(?:$$[^\[$$]*\][^$$$$]*)*\]'

    for pattern in [pattern_obj, pattern_arr]:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                continue

    return None

def extract_json_with_fallback(text: str, fallback: dict | list | None = None) -> dict | list | None:
    """
    从文本中提取 JSON，失败时返回指定的兜底值。

    配合 safe_text() 使用：safe_text 处理 None → ""，
    extract_json 处理 "" → None，fallback 处理 None → 兜底值。
    三层防护，全程不崩溃。

    Args:
        text: LLM 的输出文本
        fallback: 提取失败时的兜底值（默认空 dict）

    Returns:
        解析后的 dict/list，或兜底值（不会返回 None）

    Examples:
        >>> extract_json_with_fallback('{"name": "test"}')
        {"name": "test"}

        >>> extract_json_with_fallback('无效内容', fallback={"error": "parse_failed"})
        {"error": "parse_failed"}
    """
    result = extract_json(text)
    if result is not None:
        return result
    return fallback if fallback is not None else {}

def validate_json_schema(data: dict, required_keys: list[str]) -> bool:
    """
    校验 JSON 数据是否包含必需的字段。

    Args:
        data: 待校验的 dict
        required_keys: 必需字段列表

    Returns:
        是否包含所有必需字段

    Examples:
        >>> validate_json_schema({"test_cases": []}, ["test_cases"])
        True

        >>> validate_json_schema({"name": "test"}, ["test_cases"])
        False
    """
    if not isinstance(data, dict):
        return False
    return all(key in data for key in required_keys)

# ============================================================
# 自检：6 种场景逐一测试（对应 2.1 的场景 1-5 + 辅助测试）
# ============================================================

def test_json_extractor():
    """测试所有 JSON 提取策略"""
    print("=" * 60)
    print("🧪 测试 JSON 提取器")
    print("=" * 60)

    # --- 场景 1：纯 JSON → 策略 1（直接解析）---
    print("\n--- 场景 1：纯 JSON（策略 1：直接解析）---")
    text1 = '{"test_cases": [{"id": "TC001", "title": "登录测试"}]}'
    result1 = extract_json(text1)
    print(f"输入: {text1[:80]}")
    print(f"提取: {result1}")
    assert result1 is not None and "test_cases" in result1, "❌ 纯 JSON 提取失败"

    # --- 场景 2：代码块包裹 → 策略 2（代码块提取）---
    print("\n--- 场景 2：代码块包裹（策略 2：代码块提取）---")
    text2 = '以下是测试用例：\n```json\n{"test_cases": [{"id": "TC001"}]}\n```\n希望有帮助！'
    result2 = extract_json(text2)
    print(f"输入: {text2[:80]}...")
    print(f"提取: {result2}")
    assert result2 is not None and "test_cases" in result2, "❌ 代码块提取失败"

    # --- 场景 3：前后缀文字（无代码块）→ 策略 3（正则兜底）---
    print("\n--- 场景 3：前后缀文字（策略 3：正则兜底）---")
    text3 = '分析结果如下：{"test_cases": [{"id": "TC001"}]} 以上是分析结果。'
    result3 = extract_json(text3)
    print(f"输入: {text3[:80]}...")
    print(f"提取: {result3}")
    assert result3 is not None, "❌ 正则兜底提取失败"

    # --- 场景 4：JSON 语法微错 → extract_json 的边界 ---
    print("\n--- 场景 4：JSON 语法微错（extract_json 的边界）---")
    text4 = '{"test_cases": [{"id": "TC001" "title": "登录测试"}]}'  # 缺少逗号
    result4 = extract_json(text4)
    print(f"输入: {text4[:80]}...")
    print(f"提取: {result4}")
    print("💡 extract_json 无法修复语法错误，这是它的能力边界")
    print("   → 后续用 generate_schema() + Pydantic 校验来兜底")
    assert result4 is None, "❌ 语法错误的 JSON 应返回 None（边界测试）"

    # --- 场景 5：空文本 / fallback → 对应 2.1 场景 5 的链路 ---
    print("\n--- 场景 5：空文本 + fallback 兜底 ---")
    text5 = ""  # 模拟 safe_text 返回空字符串（response.text 为 None 时）
    result5a = extract_json(text5)
    print(f"输入: (空文本)")
    print(f"extract_json 结果: {result5a}")
    assert result5a is None, "❌ 空文本应返回 None"

    result5b = extract_json_with_fallback(text5, fallback={"error": "empty_response"})
    print(f"extract_json_with_fallback 结果: {result5b}")
    assert result5b == {"error": "empty_response"}, "❌ fallback 未生效"

    # --- 辅助测试：纯文字无 JSON → fallback 兜底 ---
    print("\n--- 辅助测试：纯文字无 JSON → fallback ---")
    text6 = "这是普通文字，没有 JSON"
    result6 = extract_json_with_fallback(text6, fallback={"error": "no_json_found"})
    print(f"输入: {text6}")
    print(f"提取（兜底）: {result6}")
    assert result6 == {"error": "no_json_found"}, "❌ fallback 未生效"

    # --- 辅助测试：validate_json_schema ---
    print("\n--- 辅助测试：Schema 校验 ---")
    data7 = {"test_cases": [{"id": "TC001"}], "feature_name": "登录"}
    valid7 = validate_json_schema(data7, ["test_cases", "feature_name"])
    print(f"数据: {data7}")
    print(f"必需字段: ['test_cases', 'feature_name']")
    print(f"校验结果: {valid7}")
    assert valid7 is True, "❌ Schema 校验失败"

    invalid7 = validate_json_schema({"name": "test"}, ["test_cases"])
    print(f"不完整数据校验: {invalid7}")
    assert invalid7 is False, "❌ 不完整数据应校验失败"

    print("\n✅ JSON 提取器全部测试通过！")


if __name__ == "__main__":
    test_json_extractor()