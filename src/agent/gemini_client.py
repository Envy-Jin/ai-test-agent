"""
src/agent/gemini_client.py —— Gemini API 封装工具

使用新版 google-genai SDK 封装可复用的工具函数。
提供以下能力：
- 简单问答
- 结构化 JSON 输出
- 带重试的健壮调用
- 批量生成
"""

from google import genai
from google.genai import types
import os
import json
import time
# from typing import Optional, Any
from dotenv import load_dotenv

# # 代理配置
# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

# 加载环境变量
load_dotenv()
_api_key = os.getenv("GEMINI_API_KEY")

class GeminiClient:
    """
    Gemini API 封装客户端（新版 google-genai SDK）

    使用示例:
        client = GeminiClient()
        result = client.ask("你好")
        test_cases = client.ask_json("生成登录测试用例")
    """

    def __init__(
        self,
        model_name: str = "gemini-3.1-flash-lite",
        temperature: float = 0.2,
        max_output_tokens: int = 2048,
    ):
        """
        初始化客户端

        Args:
            model_name: 模型名称，如 "gemini-3.5-flash" 或 "gemini-2.5-flash-lite"
            temperature: 温度参数，0.0~2.0，越低越确定
            max_output_tokens: 最大输出 token 数
        """
        if not _api_key:
            raise ValueError(
                "❌ 未找到 GEMINI_API_KEY。请在 .env 文件中设置 GEMINI_API_KEY=你的Key"
            )

        self.model_name = model_name
        self.default_temperature = temperature
        self.default_max_tokens = max_output_tokens
        self.client = genai.Client(api_key=_api_key)

    def _make_config(
        self,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        json_mode: bool = False,
    ) -> types.GenerateContentConfig:
        """构建 GenerateContentConfig"""
        config = types.GenerateContentConfig(
            temperature=temperature if temperature is not None else self.default_temperature,
            max_output_tokens=max_output_tokens if max_output_tokens is not None else self.default_max_tokens,
        )
        if json_mode:
            config.response_mime_type = "application/json"
        return config

    def ask(self, prompt: str) -> str:
        """
        发送简单文本提示，返回文本响应

        Args:
            prompt: 提示文本

        Returns:
            模型的文本回复
        """
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=self._make_config(),
        )
        return response.text

    def ask_json(self, prompt: str) -> dict | list:
        """
        发送提示并强制返回 JSON 格式，自动解析为 Python 对象

        Args:
            prompt: 提示文本

        Returns:
            解析后的 Python 对象（dict/list）

        Raises:
            json.JSONDecodeError: JSON 解析失败
        """
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=self._make_config(json_mode=True),
        )
        return json.loads(response.text)

    def ask_with_retry(
        self,
        prompt: str,
        json_mode: bool = False,
        max_retries: int = 3,
    ) -> str | dict | list:
        """
        带重试机制的调用（应对网络波动和速率限制）

        Args:
            prompt: 提示文本
            json_mode: 是否强制 JSON 输出
            max_retries: 最大重试次数

        Returns:
            str 或 dict（取决于 json_mode）
        """
        last_error = None
        for attempt in range(max_retries):
            try:
                if json_mode:
                    return self.ask_json(prompt)
                else:
                    return self.ask(prompt)
            except Exception as e:
                last_error = e
                print(f"⚠️  第 {attempt + 1} 次调用失败: {type(e).__name__}: {e}")
                if attempt < max_retries - 1:
                    wait_time = 2 ** attempt  # 指数退避：2s, 4s, 8s
                    print(f"   等待 {wait_time}s 后重试...")
                    time.sleep(wait_time)

        raise RuntimeError(
            f"❌ API 调用失败，已重试 {max_retries} 次。最后错误: {last_error}"
        )

    def ask_with_config(
        self,
        prompt: str,
        temperature: float | None = None,
        max_output_tokens: int | None = None,
        json_mode: bool = False,
    ) -> str | dict | list:
        """
        单次调用时临时覆盖默认参数

        Args:
            prompt: 提示文本
            temperature: 临时覆盖的温度值
            max_output_tokens: 临时覆盖的最大 token 数
            json_mode: 是否强制 JSON

        Returns:
            str 或 dict
        """
        config = self._make_config(
            temperature=temperature,
            max_output_tokens=max_output_tokens,
            json_mode=json_mode,
        )
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=config,
        )
        if json_mode:
            return json.loads(response.text)
        return response.text

# ============================================================
# 便捷函数（模块级，快速使用无需创建实例）
# ============================================================

_default_client = None


def _get_client() -> GeminiClient:
    """获取或创建默认客户端（懒加载）"""
    global _default_client
    if _default_client is None:
        _default_client = GeminiClient()
    return _default_client


def quick_ask(prompt: str) -> str:
    """快速问答（使用默认配置）"""
    return _get_client().ask(prompt)


def quick_ask_json(prompt: str) -> dict | list:
    """快速问答并返回 JSON"""
    return _get_client().ask_json(prompt)


# ============================================================
# 自检：模块加载时验证配置
# ============================================================

if __name__ == "__main__":
    print("🧪 测试 GeminiClient...\n")

    client = GeminiClient()

    # 测试 1：简单问答
    print("测试 1：简单问答")
    answer = client.ask("什么是软件测试中的等价类划分？用一句话回答")
    print(f"回答: {answer}\n")

    # 测试 2：JSON 输出
    print("测试 2：JSON 输出")
    result = client.ask_json(
        "生成 2 个登录功能测试用例，每个包含 id, title, priority 字段，以 JSON 格式输出"
    )
    print(f"结果: {json.dumps(result, ensure_ascii=False, indent=2)[:300]}\n")

    # 测试 3：便捷函数
    print("测试 3：便捷函数")
    quick_result = quick_ask("黑盒测试和白盒测试的区别（一句话）")
    print(f"回答: {quick_result}\n")

    print("✅ GeminiClient 测试通过！")