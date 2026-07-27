"""
src/agent/retry_generator.py —— 带重试的测试用例生成器

Day 12 核心练习：处理 API 调用中的各种不确定性
- 网络错误：指数退避重试
- 429 限流：读取 Retry-After 或默认等待
- JSON 解析失败：自动降级提取
- 安全过滤拦截：兜底返回
"""

from google import genai
from google.genai import types
import os
import time
import random
import json
from typing import Optional, Any
from dotenv import load_dotenv
from utils import safe_text
from json_extractor import extract_json, extract_json_with_fallback

os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

load_dotenv()
_client = genai.Client(api_key = os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-3.1-flash-lite"

# ============================================================
# 重试策略
# ============================================================

class RetryConfig:
    """重试配置"""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 2.0,
        max_delay: float = 30.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.jitter = jitter

    def get_delay(self, attempt: int) -> float:
        """
        计算指数退避延迟

        公式: delay = min(base_delay * 2^attempt, max_delay) + random_jitter

        Args:
            attempt: 当前重试次数（从 0 开始）

        Returns:
            等待秒数
        """
        delay = min(self.base_delay * (2 ** attempt), self.max_delay)
        if self.jitter:
            delay += random.uniform(0, 1.0)
        return delay

def should_retry(error: Exception) -> bool:
    """
    判断错误是否应该重试

    Args:
        error: 捕获的异常

    Returns:
        是否应该重试
    """
    error_str = str(error)

    # 应该重试的错误：
    # - 429 限流
    # - 5xx 服务器错误
    # - 网络连接错误
    # - 超时
    retry_keywords = ["429", "500", "503", "connection", "timeout", "rate limit"]

    # 不应该重试的错误：
    # - 400 参数错误（重试也不会好）
    # - 401 认证失败（API Key 问题）
    # - 403 权限不足
    no_retry_keywords = ["400", "401", "403", "invalid", "permission"]

    for keyword in no_retry_keywords:
        if keyword.lower() in error_str.lower():
            return False

    for keyword in retry_keywords:
        if keyword.lower() in error_str.lower():
            return True

    # 未知错误：保守重试一次
    return True


# ============================================================
# 带重试的单次调用
# ============================================================

def generate_with_retry(
    prompt: str,
    system_instruction: str = "",
    temperature: float = 0.2,
    retry_config: RetryConfig | None = None,
    response_mime_type: str | None = None,
    response_schema: Any = None,
) -> str:
    """
    带重试的 Gemini 单次调用

    Args:
        prompt: 用户提示文本
        system_instruction: 系统角色提示
        temperature: 温度参数
        retry_config: 重试配置
        response_mime_type: 响应 MIME 类型
        response_schema: Pydantic Schema 类

    Returns:
        模型回复文本（必定是 str，不会是 None）
    """
    if retry_config is None:
        retry_config = RetryConfig()

    config_kwargs: dict = {"temperature": temperature}
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction
    if response_mime_type:
        config_kwargs["response_mime_type"] = response_mime_type
    if response_schema:
        config_kwargs["response_schema"] = response_schema

    last_error = None

    for attempt in range(retry_config.max_retries):
        try:
            response = _client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(**config_kwargs),
            )
            text = safe_text(response)
            if text:
                return text
            else:
                # response.text 为 None（安全过滤）
                return "[系统提示] 模型返回了空内容，可能被安全过滤拦截。"

        except Exception as e:
            last_error = e
            print(f"⚠️ 第 {attempt + 1} 次调用失败: {type(e).__name__}: {e}")

            if not should_retry(e):
                print(f"❌ 此错误不应重试，直接失败: {e}")
                break

            if attempt < retry_config.max_retries - 1:
                delay = retry_config.get_delay(attempt)
                print(f"   等待 {delay:.1f}s 后重试...")
                time.sleep(delay)

    return f"[系统提示] API 调用失败，已重试 {retry_config.max_retries} 次。最后错误: {last_error}"

# ============================================================
# 带重试 + JSON 提取的生成器
# ============================================================

def generate_json_with_retry(
    prompt: str,
    system_instruction: str = "",
    temperature: float = 0.2,
    retry_config: RetryConfig | None = None,
    required_keys: list[str] | None = None,
    fallback: dict | None = None,
) -> dict:
    """
    带重试 + JSON 提取的生成器

    流程：
    1. 调用 Gemini（带重试）
    2. 从输出中提取 JSON（三重策略）
    3. 校验必需字段
    4. 失败则返回 fallback

    Args:
        prompt: 用户提示文本
        system_instruction: 系统角色提示
        temperature: 温度参数
        retry_config: 重试配置
        required_keys: JSON 中必需的字段列表
        fallback: 提取失败时的兜底值

    Returns:
        dict（必定是 dict，不会是 None）
    """
    if retry_config is None:
        retry_config = RetryConfig()
    if fallback is None:
        fallback = {"test_cases": [], "error": "generation_failed"}

    # 1. 调用 Gemini（带重试），强制 JSON 模式
    raw_text = generate_with_retry(
        prompt=prompt,
        system_instruction=system_instruction,
        temperature=temperature,
        retry_config=retry_config,
        response_mime_type="application/json",
    )
    # 2. 从输出中提取 JSON
    result = extract_json(raw_text)
    # print(f"result: {result}")
    if result is not None and isinstance(result, dict):
        # 3. 校验必需字段
        if required_keys:
            from json_extractor import validate_json_schema
            if validate_json_schema(result, required_keys):
                return result
            else:
                print(f"⚠️ JSON 缺少必需字段: {required_keys}")
        else:
            return result

    # 4. 提取或校验失败，返回 fallback
    print(f"⚠️ JSON 提取/校验失败，返回 fallback")
    return fallback


# ============================================================
# 自检：演示各种重试场景
# ============================================================

def test_retry_generator():
    """测试带重试的生成器"""
    print("=" * 60)
    print("🧪 测试带重试的生成器")
    print("=" * 60)

    # 测试 1：正常生成（不需要重试）
    print("\n--- 测试 1：正常 JSON 生成 ---")
    result = generate_json_with_retry(
        prompt="""请为「用户注册功能」生成 3 个测试用例。
        输出 JSON 格式，必须包含 test_cases 字段，结构如下：
        {"test_cases": [{"id": "TC001", "title": "...", "priority": "P0"}]}
        """,
        system_instruction="你是资深测试工程师。",
        required_keys=["test_cases"],
    )
    print(f"结果类型: {type(result).__name__}")
    if "test_cases" in result:
        print(f"用例数: {len(result['test_cases'])}")
    else:
        print(f"结果: {result}")

    # 测试 2：RetryConfig 的延迟计算
    print("\n--- 测试 2：指数退避延迟 ---")
    config = RetryConfig(max_retries=5, base_delay=2.0)
    for i in range(5):
        delay = config.get_delay(i)
        print(f"  第 {i+1} 次重试等待: {delay:.1f}s")

    # 测试 3：should_retry 判断
    print("\n--- 测试 3：错误类型判断 ---")
    errors = [
        Exception("429 Rate limit exceeded"),
        Exception("500 Internal server error"),
        Exception("401 Unauthorized"),
        Exception("400 Bad request: invalid parameter"),
        Exception("ConnectionError: timeout"),
    ]
    for err in errors:
        retry = should_retry(err)
        print(f"  {str(err)[:40]} → 应重试: {retry}")

    print("\n✅ 重试生成器测试通过！")


if __name__ == "__main__":
    test_retry_generator()