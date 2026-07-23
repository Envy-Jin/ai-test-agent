"""
src/agent/chat_safety.py —— 多轮对话的健壮性封装

Day 11 核心练习：多轮对话中的错误处理
全程使用 safe_text()，杜绝 response.text 的 None 类型错误
"""

from google import genai
from google.genai import types
import os
import time
from typing import Optional
from dotenv import load_dotenv
from utils import safe_text

# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-3.1-flash-lite"

# ============================================================
# 健壮的 Chat 封装
# ============================================================

class SafeChat:
    """
    健壮的对话封装

    解决多轮对话中的常见问题：
    1. response.text 可能为 None（安全过滤）
    2. 网络波动导致调用失败
    3. 过长历史导致 token 超限
    4. 回复为空时的兜底
    """

    def __init__(
        self,
        model: str = MODEL,
        system_instruction: str = "",
        temperature: float = 0.3,
        max_retries: int = 3,
        max_history_turns: int = 20,
    ):
        self.model = model
        self.max_retries = max_retries
        self.max_history_turns = max_history_turns
        self.turn_count = 0

        self.chat = client.chats.create(
            model=model,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction if system_instruction else None,
                temperature=temperature,
            ),
        )

    def send(self, message: str) -> str:
        """
        发送消息（带重试和兜底）

        Args:
            message: 用户消息

        Returns:
            模型回复文本（必定是 str，不会是 None）
        """
        last_error = None

        for attempt in range(self.max_retries):
            try:
                response = self.chat.send_message(message)
                text = safe_text(response)
                if text:  # 有内容
                    self.turn_count += 1
                    self._maybe_truncate()
                    return text
                else:
                    # text 为空（被安全过滤或其他原因）
                    return "[系统提示] 模型返回了空内容，可能是内容被安全过滤拦截。请尝试换一种表述。"

            except Exception as e:
                last_error = e
                print(f"⚠️ 第 {attempt + 1} 次调用失败: {type(e).__name__}: {e}")
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"   等待 {wait_time}s 后重试...")
                    time.sleep(wait_time)

        return f"[系统提示] API 调用失败，已重试 {self.max_retries} 次。最后错误: {last_error}"       

    def send_stream(self, message: str, verbose: bool = True) -> str:
        """
        流式发送消息

        Args:
            message: 用户消息
            verbose: 是否实时打印

        Returns:
            拼接后的完整回复文本
        """
        full_text = ""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                for chunk in self.chat.send_message_stream(message):
                    text = safe_text(chunk)
                    if text:
                        if verbose:
                            print(text, end="", flush=True)
                        full_text += text

                if verbose:
                    print()  # 换行

                if full_text:
                    self.turn_count += 1
                    self._maybe_truncate()
                    return full_text
                else:
                    return "[系统提示] 流式输出为空。请尝试换一种方式提问。"

            except Exception as e:
                last_error = e
                full_text = ""  # 重置
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)

        return f"[系统提示] 流式调用失败，已重试 {self.max_retries} 次。"

    def _maybe_truncate(self):
        """
        当对话轮数过多时，自动压缩历史

        策略：对前 N 轮做摘要，替换原始历史
        （简化版：只做检测提示，实际实现可按需扩展）
        """
        if self.turn_count > self.max_history_turns:
            print(f"⚠️ 对话已超过 {self.max_history_turns} 轮，建议使用摘要压缩或开启新会话")

    def get_history(self):
        """获取对话历史"""
        return self.chat.get_history()

    def history_summary(self) -> str:
        """
        让模型自己总结对话历史（用于压缩长上下文）

        Returns:
            对话摘要文本
        """
        # 注意：这里直接问当前 chat 来总结它自己的历史
        # 实际使用中可能需要一个独立的调用来生成摘要
        summary_prompt = "请用 3-5 句话总结我们到目前为止讨论的主要内容。"
        response = self.chat.send_message(summary_prompt)
        return safe_text(response)

# ============================================================
# 健壮性测试
# ============================================================

def test_safe_chat():
    """测试 SafeChat 的各种场景"""
    print("=" * 60)
    print("🧪 测试 SafeChat 健壮性封装")
    print("=" * 60)

    # 测试 1：正常对话
    print("\n--- 测试 1：正常多轮对话 ---")
    chat = SafeChat(
        system_instruction="你是测试工程师，回答简洁。",
    )
    resp1 = chat.send("我在测试一个搜索功能")
    print(f"第1轮: {resp1[:100]}...")

    resp2 = chat.send("给出3个测试要点")
    print(f"第2轮: {resp2[:100]}...")

    # 测试 2：流式输出
    print("\n--- 测试 2：流式输出 ---")
    chat2 = SafeChat(
        system_instruction="你是测试工程师。",
    )
    resp3 = chat2.send_stream("列3个API测试的最佳实践", verbose=True)
    print(f"\n流式完整长度: {len(resp3)} 字符")

    # 测试 3：历史摘要
    print("\n--- 测试 3：对话历史摘要 ---")
    summary = chat.history_summary()
    print(f"摘要: {summary}")

    # 测试 4：send 返回值的类型安全验证
    print("\n--- 测试 4：类型安全验证 ---")
    result = chat.send("说一个字：好")
    # 验证：result 是 str，可以安全地做字符串操作
    print(f"类型: {type(result).__name__}")
    print(f"长度: {len(result)}")
    print(f"前50字符: {result[:50]}")
    # 这些操作不会因为 None 而崩溃
    print(f"检查 starts: {result.startswith('[系统')}")

    print("\n✅ SafeChat 测试通过！")


if __name__ == "__main__":
    test_safe_chat()
    print("\n✅ 多轮对话健壮性测试全部完成！")