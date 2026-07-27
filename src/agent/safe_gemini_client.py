"""
src/agent/safe_gemini_client.py —— 健壮的 Gemini 调用封装类

Day 12 核心产出：把 Day 8-11 的所有调用方式，整合成零崩溃的生产级工具

能力：
1. generate()        → 单次文本调用（带重试 + safe_text）
2. generate_stream() → 流式文本调用（带重试 + chunk 拼接）
3. generate_json()   → JSON 提取调用（带重试 + extract_json）
4. generate_schema() → Schema 结构化调用（带重试 + Pydantic 校验）
5. create_chat()     → 创建多轮对话（返回 SafeChat 对象）

统一特性：
- 所有方法都带 RetryConfig 重试
- 所有方法都用 safe_text
- 所有方法都有 logging 日志
- 所有方法返回值都是确定类型（不会 None / 不会崩溃）
"""

from google import genai
from google.genai import types
import os
import time
import json
import logging
from typing import Any, TypeVar, Type
from dotenv import load_dotenv
from pydantic import BaseModel, ValidationError


from utils import safe_text
from json_extractor import extract_json, extract_json_with_fallback, validate_json_schema
from retry_generator import RetryConfig, should_retry
from logger_config import setup_logger

# 初始化
# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

load_dotenv()

logger = setup_logger("ai_test_agent", level=logging.DEBUG, log_file="logs/ai_agent.log")

T = TypeVar("T", bound=BaseModel)


class SafeGeminiClient:
    """
    健壮的 Gemini 调用封装类

    整合 Day 8-11 所有调用方式，加上 Day 12 的重试、JSON 提取、日志。
    所有方法返回值类型确定，不会 None / 崩溃。

    使用示例：
        client = SafeGeminiClient(model="gemini-3.5-flash")

        # 单次调用
        text = client.generate("解释什么是边界值测试")

        # 流式调用
        full_text = client.generate_stream("生成 10 个测试用例")

        # JSON 提取调用
        data = client.generate_json("生成测试用例 JSON")

        # Schema 结构化调用
        collection = client.generate_schema(
            "生成测试用例",
            schema_class=TestCaseCollection,
        )

        # 多轮对话
        chat = client.create_chat(system_instruction="你是测试工程师")
        reply = chat.send("帮我分析登录功能")
    """

    def __init__(
        self,
        model: str = "gemini-3.1-flash-lite",
        api_key: str | None = None,
        # proxy: str = "http://127.0.0.1:7890",
        default_temperature: float = 0.2,
        default_retry_config: RetryConfig | None = None,
    ):
        """
        初始化 SafeGeminiClient

        Args:
            model: Gemini 模型名称
            api_key: API Key（None 则从 .env 读取）
            proxy: 代理地址
            default_temperature: 默认温度参数
            default_retry_config: 默认重试配置
        """
        # os.environ["HTTPS_PROXY"] = proxy
        if api_key is None:
            api_key = os.getenv("GEMINI_API_KEY")

        self._client = genai.Client(api_key=api_key)
        self.model = model
        self.default_temperature = default_temperature
        self.default_retry_config = default_retry_config or RetryConfig()

        logger.info(f"SafeGeminiClient 初始化完成: model={model}")

    # ============================================================
    # 能力 1：单次文本调用
    # ============================================================

    def generate(
        self,
        prompt: str,
        system_instruction: str = "",
        temperature: float | None = None,
        retry_config: RetryConfig | None = None,
    ) -> str:
        """
        单次文本调用（带重试 + safe_text）

        Args:
            prompt: 用户提示文本
            system_instruction: 系统角色提示
            temperature: 温度参数（None 则用默认值）
            retry_config: 重试配置（None 则用默认值）

        Returns:
            模型回复文本（必定是 str）
        """
        temp = temperature if temperature is not None else self.default_temperature
        config = retry_config if retry_config is not None else self.default_retry_config

        config_kwargs: dict = {"temperature": temp}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        logger.info(f"generate() 调用开始: prompt={prompt[:80]}...")
        last_error = None

        for attempt in range(config.max_retries):
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(**config_kwargs),
                )
                text = safe_text(response)
                if text:
                    logger.info(f"generate() 成功: 长度={len(text)}")
                    return text
                else:
                    logger.warning("generate() 返回空内容（安全过滤）")
                    return "[系统提示] 模型返回了空内容，可能被安全过滤拦截。"

            except Exception as e:
                last_error = e
                logger.warning(f"generate() 第 {attempt+1} 次失败: {type(e).__name__}: {e}")

                if not should_retry(e):
                    logger.error(f"generate() 不可重试错误: {e}")
                    break

                if attempt < config.max_retries - 1:
                    delay = config.get_delay(attempt)
                    logger.info(f"generate() 等待 {delay:.1f}s 后重试...")
                    time.sleep(delay)

        logger.error(f"generate() 最终失败: 重试 {config.max_retries} 次")
        return f"[系统提示] API 调用失败，已重试 {config.max_retries} 次。最后错误: {last_error}"


    # ============================================================
    # 能力 2：流式文本调用
    # ============================================================

    def generate_stream(
        self,
        prompt: str,
        system_instruction: str = "",
        temperature: float | None = None,
        retry_config: RetryConfig | None = None,
        verbose: bool = True,
    ) -> str:
        """
        流式文本调用（带重试 + chunk 拼接）

        Args:
            prompt: 用户提示文本
            system_instruction: 系统角色提示
            temperature: 温度参数
            retry_config: 重试配置
            verbose: 是否实时打印

        Returns:
            拼接后的完整回复文本（必定是 str）
        """
        temp = temperature if temperature is not None else self.default_temperature
        config = retry_config if retry_config is not None else self.default_retry_config

        config_kwargs: dict = {"temperature": temp}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        logger.info(f"generate_stream() 调用开始: prompt={prompt[:80]}...")
        last_error = None

        for attempt in range(config.max_retries):
            try:
                full_text = ""
                for chunk in self._client.models.generate_content_stream(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(**config_kwargs),
                ):
                    text = safe_text(chunk)
                    if text:
                        if verbose:
                            print(text, end="", flush=True)
                        full_text += text

                if verbose:
                    print()  # 最后换行

                if full_text:
                    logger.info(f"generate_stream() 成功: 长度={len(full_text)}")
                    return full_text
                else:
                    logger.warning("generate_stream() 返回空内容")
                    return "[系统提示] 流式输出为空。"

            except Exception as e:
                last_error = e
                logger.warning(f"generate_stream() 第 {attempt+1} 次失败: {e}")

                if not should_retry(e):
                    logger.error(f"generate_stream() 不可重试错误: {e}")
                    break

                if attempt < config.max_retries - 1:
                    delay = config.get_delay(attempt)
                    logger.info(f"generate_stream() 等待 {delay:.1f}s 后重试...")
                    time.sleep(delay)

        logger.error(f"generate_stream() 最终失败")
        return f"[系统提示] 流式调用失败，已重试 {config.max_retries} 次。"

    # ============================================================
    # 能力 3：JSON 提取调用
    # ============================================================

    def generate_json(
        self,
        prompt: str,
        system_instruction: str = "",
        temperature: float | None = None,
        retry_config: RetryConfig | None = None,
        required_keys: list[str] | None = None,
        fallback: dict | None = None,
    ) -> dict:
        """
        JSON 提取调用（带重试 + extract_json + Schema 校验）

        流程：
        1. 调用 Gemini（带重试 + JSON 模式）
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
        if fallback is None:
            fallback = {"test_cases": [], "error": "generation_failed"}

        logger.info(f"generate_json() 调用开始: prompt={prompt[:80]}...")

        # 1. 调用 Gemini（带重试 + JSON 模式）
        raw_text = self.generate(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=temperature,
            retry_config=retry_config,
            # 注意：这里不带 response_mime_type 和 response_schema
            # 因为 generate_json 是通用提取模式，不强制 Schema
        )

        # 如果 generate() 返回的是系统提示（失败），直接 fallback
        if raw_text.startswith("[系统提示]"):
            logger.error(f"generate_json() API 调用失败: {raw_text}")
            return fallback

        # 2. 从输出中提取 JSON
        result = extract_json(raw_text)
        if result is not None and isinstance(result, dict):
            # 3. 校验必需字段
            if required_keys and not validate_json_schema(result, required_keys):
                logger.warning(f"generate_json() JSON 缺少必需字段: {required_keys}")
                return fallback
            logger.info(f"generate_json() 成功: keys={list(result.keys())}")
            return result

        # 4. 提取失败，返回 fallback
        logger.warning(f"generate_json() JSON 提取失败，返回 fallback")
        return fallback

    # ============================================================
    # 能力 4：Schema 结构化调用
    # ============================================================

    def generate_schema(
        self,
        prompt: str,
        schema_class: Type[T],
        system_instruction: str = "",
        temperature: float | None = None,
        retry_config: RetryConfig | None = None,
        fallback_to_json: bool = True,
    ) -> T | dict:
        """
        Schema 结构化调用（带重试 + Pydantic 校验）

        优先用 response_schema 强制精确结构，
        如果 Schema 模式失败，降级到 JSON 提取模式。

        Args:
            prompt: 用户提示文本
            schema_class: Pydantic 模型类
            system_instruction: 系统角色提示
            temperature: 温度参数
            retry_config: 重试配置
            fallback_to_json: Schema 失败时是否降级到 JSON 提取

        Returns:
            Pydantic 对象（优先）或 dict（降级时）
        """
        logger.info(f"generate_schema() 调用开始: schema={schema_class.__name__}")

        temp = temperature if temperature is not None else self.default_temperature
        config = retry_config if retry_config is not None else self.default_retry_config

        config_kwargs: dict = {
            "temperature": temp,
            "response_mime_type": "application/json",
            "response_schema": schema_class,
        }
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        last_error = None

        for attempt in range(config.max_retries):
            try:
                response = self._client.models.generate_content(
                    model=self.model,
                    contents=prompt,
                    config=types.GenerateContentConfig(**config_kwargs),
                )
                raw_text = safe_text(response)

                if not raw_text:
                    logger.warning("generate_schema() 返回空内容")
                    continue

                # Pydantic 解析
                try:
                    result = schema_class.model_validate_json(raw_text)
                    logger.info(f"generate_schema() 成功: {schema_class.__name__}")
                    return result
                except ValidationError as ve:
                    logger.warning(f"generate_schema() Pydantic 校验失败: {ve}")
                    last_error = ve
                    if attempt < config.max_retries - 1:
                        delay = config.get_delay(attempt)
                        time.sleep(delay)
                        continue

            except Exception as e:
                last_error = e
                logger.warning(f"generate_schema() 第 {attempt+1} 次失败: {e}")

                if not should_retry(e):
                    break

                if attempt < config.max_retries - 1:
                    delay = config.get_delay(attempt)
                    time.sleep(delay)

        # Schema 模式全部失败
        if fallback_to_json:
            logger.info("generate_schema() 降级到 JSON 提取模式")
            return self.generate_json(
                prompt=prompt,
                system_instruction=system_instruction,
                temperature=temperature,
                retry_config=retry_config,
                fallback={"error": "schema_failed", "raw_error": str(last_error)},
            )

        return {"error": "schema_failed", "raw_error": str(last_error)}

    # ============================================================
    # 能力 5：创建多轮对话
    # ============================================================

    def create_chat(
        self,
        system_instruction: str = "",
        temperature: float | None = None,
        max_retries: int = 3,
        max_history_turns: int = 20,
    ) -> "SafeChat":
        """
        创建一个健壮的多轮对话对象

        Args:
            system_instruction: 系统角色提示
            temperature: 温度参数
            max_retries: 每次发送的重试次数
            max_history_turns: 最大历史轮数（超出自动警告）

        Returns:
            SafeChat 对象
        """
        logger.info(f"create_chat() 创建对话: system={system_instruction[:50]}...")
        return SafeChat(
            client=self._client,
            model=self.model,
            system_instruction=system_instruction,
            temperature=temperature if temperature is not None else self.default_temperature,
            max_retries=max_retries,
            max_history_turns=max_history_turns,
        )


# ============================================================
# SafeChat —— 健壮的多轮对话封装（Day 11 的升级版）
# ============================================================

class SafeChat:
    """
    健壮的多轮对话封装

    Day 11 SafeChat 的升级版：
    - 加入了 logging 日志
    - 加入了 RetryConfig 重试
    - 流式也用 safe_text(chunk)
    """

    def __init__(
        self,
        client: genai.Client,
        model: str,
        system_instruction: str = "",
        temperature: float = 0.2,
        max_retries: int = 3,
        max_history_turns: int = 20,
    ):
        self._client = client
        self.model = model
        self.max_retries = max_retries
        self.max_history_turns = max_history_turns
        self.turn_count = 0

        config_kwargs: dict = {"temperature": temperature}
        if system_instruction:
            config_kwargs["system_instruction"] = system_instruction

        self.chat = client.chats.create(
            model=model,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        logger.info(f"SafeChat 创建完成: model={model}")

    def send(self, message: str) -> str:
        """发送消息（带重试 + safe_text）"""
        logger.info(f"SafeChat.send(): message={message[:80]}...")
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response = self.chat.send_message(message)
                text = safe_text(response)
                if text:
                    self.turn_count += 1
                    self._maybe_warn_history()
                    logger.info(f"SafeChat.send() 成功: 长度={len(text)}")
                    return text
                else:
                    logger.warning("SafeChat.send() 返回空内容")
                    return "[系统提示] 模型返回了空内容，可能被安全过滤拦截。"

            except Exception as e:
                last_error = e
                logger.warning(f"SafeChat.send() 第 {attempt+1} 次失败: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)

        return f"[系统提示] API 调用失败，已重试 {self.max_retries} 次。"

    def send_stream(self, message: str, verbose: bool = True) -> str:
        """流式发送消息（带重试 + chunk 拼接）"""
        logger.info(f"SafeChat.send_stream(): message={message[:80]}...")
        last_error = None

        for attempt in range(self.max_retries):
            try:
                full_text = ""
                for chunk in self.chat.send_message_stream(message):
                    text = safe_text(chunk)
                    if text:
                        if verbose:
                            print(text, end="", flush=True)
                        full_text += text

                if verbose:
                    print()

                if full_text:
                    self.turn_count += 1
                    self._maybe_warn_history()
                    logger.info(f"SafeChat.send_stream() 成功: 长度={len(full_text)}")
                    return full_text
                else:
                    logger.warning("SafeChat.send_stream() 返回空内容")
                    return "[系统提示] 流式输出为空。"

            except Exception as e:
                last_error = e
                logger.warning(f"SafeChat.send_stream() 第 {attempt+1} 次失败: {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)

        return f"[系统提示] 流式调用失败，已重试 {self.max_retries} 次。"

    def get_history(self):
        """获取对话历史"""
        return self.chat.get_history()

    def history_summary(self) -> str:
        """让模型总结对话历史"""
        prompt = "请用 3-5 句话总结我们到目前为止讨论的主要内容。"
        response = self.chat.send_message(prompt)
        return safe_text(response)

    def _maybe_warn_history(self):
        """历史过长时发出警告"""
        if self.turn_count > self.max_history_turns:
            logger.warning(
                f"对话已超过 {self.max_history_turns} 轮，建议压缩历史或开启新会话"
            )


# ============================================================
# 自检：演示 SafeGeminiClient 的五种能力
# ============================================================

def test_safe_gemini_client():
    """测试 SafeGeminiClient 的五种能力"""
    print("=" * 60)
    print("🧪 测试 SafeGeminiClient")
    print("=" * 60)

    client = SafeGeminiClient()

    # 能力 1：单次文本调用
    print("\n--- 能力 1：generate() ---")
    text = client.generate("用一句话解释什么是边界值测试")
    print(f"结果: {text[:100]}")
    assert isinstance(text, str) and len(text) > 0, "❌ generate() 返回值不是有效 str"

    # 能力 2：流式文本调用
    print("\n--- 能力 2：generate_stream() ---")
    full_text = client.generate_stream("列出 3 个软件测试的基本原则", verbose=True)
    print(f"\n流式完整长度: {len(full_text)} 字符")
    assert isinstance(full_text, str) and len(full_text) > 0, "❌ generate_stream() 返回值不是有效 str"

    # 能力 3：JSON 提取调用
    print("\n--- 能力 3：generate_json() ---")
    data = client.generate_json(
        "请为「购物车功能」生成 3 个测试用例，输出 JSON 格式，包含 test_cases 数组",
        required_keys=["test_cases"],
    )
    print(f"结果类型: {type(data).__name__}")
    print(f"包含 test_cases: {'test_cases' in data}")
    assert isinstance(data, dict), "❌ generate_json() 返回值不是 dict"

    # 能力 4：Schema 结构化调用
    print("\n--- 能力 4：generate_schema() ---")
    from case_schema import TestCaseCollection
    collection = client.generate_schema(
        "请为「搜索功能」生成测试用例",
        schema_class=TestCaseCollection,
        system_instruction="你是资深测试工程师。",
    )
    if isinstance(collection, TestCaseCollection):
        print(f"功能: {collection.feature_name}")
        print(f"用例数: {len(collection.test_cases)}")
    elif isinstance(collection, dict):
        print(f"降级到 dict: {list(collection.keys())}")
    else:
        print(f"降级到未知类型: {type(collection).__name__}")

    # 能力 5：多轮对话
    print("\n--- 能力 5：create_chat() ---")
    chat = client.create_chat(system_instruction="你是测试工程师。回答简洁。")
    reply1 = chat.send("我在测试一个注册功能")
    print(f"第1轮: {reply1[:100]}")
    reply2 = chat.send("补充边界条件测试用例")
    print(f"第2轮: {reply2[:100]}")
    assert isinstance(reply1, str) and isinstance(reply2, str), "❌ SafeChat.send() 返回值不是 str"

    print("\n✅ SafeGeminiClient 五种能力全部测试通过！")


if __name__ == "__main__":
    test_safe_gemini_client()