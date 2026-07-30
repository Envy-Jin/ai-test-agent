"""
src/agent/session_manager.py —— 多会话管理器

Day 11 核心练习：管理多个独立对话，互不干扰
每个会话有自己的模型选择、历史、配置
"""

from google import genai
from google.genai import types
from typing import Any
import os
from dotenv import load_dotenv
from utils import safe_text

# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-3.1-flash-lite"


# ============================================================
# 实验 A：两个独立对话 —— 互不干扰验证
# ============================================================

def demo_independent_sessions():
    """演示两个对话互不干扰"""
    print("=" * 60)
    print("🧪 演示：两个独立对话，互不干扰")
    print("=" * 60)

    # 对话 A：讨论登录功能
    system_a = "你是测试工程师，只讨论登录相关的测试。回答简洁。"
    chat_a = client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=system_a,
            temperature=0.3,
        ),
    )
    chat_a.send_message("我是A组，负责登录功能测试")
    resp_a = chat_a.send_message("你的测试范围是什么？用 1 句话回答")
    print(f"对话A回答：{safe_text(resp_a)}")

    # 对话 B：讨论支付功能（完全独立）
    system_b = "你是测试工程师，只讨论支付相关的测试。回答简洁。"
    chat_b = client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=system_b,
            temperature=0.3,
        ),
    )
    chat_b.send_message("我是B组，负责支付功能测试")
    resp_b = chat_b.send_message("你的测试范围是什么？用 1 句话回答")
    print(f"对话B回答：{safe_text(resp_b)}")

    # 验证互不干扰：再问 A
    resp_a2 = chat_a.send_message("回忆一下，你是哪个组的？")
    print(f"对话A再问：{safe_text(resp_a2)}")

    # 验证互不干扰：再问 B
    resp_b2 = chat_b.send_message("回忆一下，你是哪个组的？")
    print(f"对话B再问：{safe_text(resp_b2)}")

    print("\n" + "-" * 60)
    print("💡 两个对话对象完全独立，各自的上下文互不影响")
    print("   chat_a 和 chat_b 是两个独立的「人格」")


# ============================================================
# 实验 B：用字典管理多个会话
# ============================================================

class SessionManager:
    """
    多会话管理器

    管理多个独立对话，支持：
    - 创建新会话
    - 在指定会话中发送消息
    - 列出所有会话
    - 查看/导出会话历史
    """

    def __init__(self, default_model: str = MODEL):
        self.default_model = default_model
        self.sessions: dict[str, Any] = {}
        self.session_configs: dict[str, dict] = {}

    def create_session(
        self,
        session_id: str,
        system_instruction: str = "",
        temperature: float = 0.3,
    ) -> str:
        """
        创建一个新会话

        Args:
            session_id: 会话唯一标识（如 "login_test_001"）
            system_instruction: 系统角色提示
            temperature: 温度参数

        Returns:
            创建确认消息
        """
        if session_id in self.sessions:
            return f"⚠️ 会话 {session_id} 已存在"

        chat = client.chats.create(
            model=self.default_model,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction if system_instruction else None,
                temperature=temperature,
            ),
        )
        self.sessions[session_id] = chat
        self.session_configs[session_id] = {
            "system_instruction": system_instruction,
            "temperature": temperature,
            "model": self.default_model,
        }
        return f"✅ 会话 {session_id} 已创建"

    def send(self, session_id: str, message: str) -> str:
        """
        向指定会话发送消息并返回回复

        Args:
            session_id: 会话标识
            message: 消息内容

        Returns:
            模型的回复文本
        """
        if session_id not in self.sessions:
            return f"❌ 会话 {session_id} 不存在，请先创建"
        chat = self.sessions[session_id]
        response = chat.send_message(message)
        return safe_text(response)

    def get_history(self, session_id: str) -> list[types.Content] | None:
        """获取指定会话的完整历史"""
        if session_id not in self.sessions:
            return None
        return self.sessions[session_id].get_history()

    def list_sessions(self) -> list[str]:
        """列出所有活跃会话 ID"""
        return list(self.sessions.keys())

    def delete_session(self, session_id: str) -> str:
        """删除指定会话"""
        if session_id not in self.sessions:
            return f"⚠️ 会话 {session_id} 不存在"
        del self.sessions[session_id]
        self.session_configs.pop(session_id, None)
        return f"🗑️ 会话 {session_id} 已删除"

    def get_summary(self, session_id: str) -> str:
        """获取会话摘要"""
        if session_id not in self.sessions:
            return f"❌ 会话 {session_id} 不存在"
        history = self.sessions[session_id].get_history()
        config = self.session_configs.get(session_id, {})
        user_msgs = sum(1 for m in history if m.role == "user")
        model_msgs = sum(1 for m in history if m.role == "model")
        return (
            f"📋 会话 {session_id}\n"
            f"   模型: {config.get('model', 'N/A')}\n"
            f"   温度: {config.get('temperature', 'N/A')}\n"
            f"   用户消息: {user_msgs} 条 | 模型回复: {model_msgs} 条\n"
            f"   角色: {config.get('system_instruction', '(未设置)')[:50]}..."
        )

# ============================================================
# 演示会话管理器
# ============================================================

def demo_session_manager():
    """演示 SessionManager 的使用"""
    print("\n" + "=" * 60)
    print("🧪 演示：SessionManager 多会话管理")
    print("=" * 60)

    mgr = SessionManager()

    # 创建多个会话
    print(mgr.create_session(
        "login_test",
        system_instruction="你是测试工程师，负责登录功能测试。回答简洁。",
    ))
    print(mgr.create_session(
        "pay_test",
        system_instruction="你是测试工程师，负责支付功能测试。回答简洁。",
    ))
    print(mgr.create_session(
        "db_test",
        system_instruction="你是测试工程师，负责数据库测试。回答简洁。",
    ))

    # 在不同会话中发送消息
    print(f"\n已创建 {len(mgr.list_sessions())} 个会话: {mgr.list_sessions()}")

    print("\n--- 登录测试会话 ---")
    resp = mgr.send("login_test", "列3个登录功能的边界测试要点")
    print(f"回答: {resp[:200]}...")

    print("\n--- 支付测试会话 ---")
    resp = mgr.send("pay_test", "列3个支付功能的边界测试要点")
    print(f"回答: {resp[:200]}...")

    # 查看各会话摘要
    print(f"\n{mgr.get_summary('login_test')}")
    print(f"\n{mgr.get_summary('pay_test')}")
    print(f"\n{mgr.get_summary('db_test')}")

    # 删除一个会话
    print(f"\n{mgr.delete_session('db_test')}")
    print(f"剩余会话: {mgr.list_sessions()}")

    print("\n💡 多会话管理的应用场景：")
    print("   - 同时分析多个需求文档")
    print("   - 不同测试类型用不同的 system_instruction")
    print("   - Web 应用中不同用户各自的对话")

    print("\n✅ SessionManager 演示完成！")


if __name__ == "__main__":
    # demo_independent_sessions()
    demo_session_manager()
    print("\n✅ 多会话管理实验全部完成！")