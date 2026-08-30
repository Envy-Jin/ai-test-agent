"""
Day 25 避坑实战：LangSmith + middleware 场景的 Pyright / 运行时陷阱

坑 1：LANGCHAIN_TRACING_V2 判断 —— 字符串 "true" vs 布尔 True（运行时坑）
坑 2：os.getenv 返回 str | None → 用 or 兜底（Pyright）
坑 3：on_error 处理器签名（exc, request: ToolCallRequest）→ 返回 str | None（Pyright）
坑 4：fallback 模型字符串必须带 provider 前缀（运行时坑，这里用常量演示约定）
坑 5：RunnableConfig 显式注解（Pyright：不注解会被推断为 dict，赋值可能不匹配）

用法：python day25_pyright_pitfalls.py（纯本地逻辑，无 API）
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from langchain.agents.middleware import ToolCallRequest
from langchain_core.messages import ToolCall
from langchain_core.runnables import RunnableConfig
from langgraph.prebuilt.tool_node import ToolRuntime


# ── 坑 1 + 坑 2：环境变量读取 ──────────────────────────────

def demo_env_bool() -> None:
    """坑 1：LANGCHAIN_TRACING_V2 是字符串，判断要转小写比较。"""
    raw: str | None = os.getenv("LANGCHAIN_TRACING_V2")  # getenv 返回 str | None
    tracing_on: bool = (raw or "").lower() == "true"  # None 用 or 兜底成 ""
    print(f"✅ 字符串判断: raw={raw!r} → tracing_on={tracing_on}（布尔 True 直接比较会失效）")
    assert isinstance(tracing_on, bool)


def demo_env_key() -> None:
    """坑 2：两个 key 变量二选一（新名优先，旧名兜底）。"""
    key: str = os.getenv("LANGSMITH_API_KEY") or os.getenv("LANGCHAIN_API_KEY") or ""
    has_key: bool = bool(key)
    print(f"✅ key 兜底读取: has_key={has_key}（LANGSMITH_API_KEY 优先，LANGCHAIN_API_KEY 兜底）")


# ── 坑 3：on_error 处理器签名 ──────────────────────────────

def on_error(exc: Exception, request: ToolCallRequest) -> str | None:
    """签名必须 (Exception, ToolCallRequest) -> str | None。
    返回 str → 转错误消息给模型；返回 None → 异常继续传播。"""
    name: str = str(request.tool_call.get("name", "unknown"))
    if isinstance(exc, ValueError):
        return f"工具 {name} 失败（{type(exc).__name__}），请修正参数重试"
    return None


def demo_on_error_signature() -> None:
    """坑 3：on_error 的返回类型收窄（None 分支明确）。

    ToolCallRequest 是 dataclass（4 字段：tool_call / tool / state / runtime），
    runtime 用 ToolRuntime.__new__ 拿空壳实例即可（只演示签名，不执行工具）。
    """
    tc: ToolCall = {"name": "strict_tool", "args": {}, "id": "1"}
    request = ToolCallRequest(
        tool_call=tc,
        tool=None,
        state={},
        runtime=ToolRuntime.__new__(ToolRuntime),  # 空壳实例（仅演示用）
    )
    msg: str | None = on_error(ValueError("bad"), request)
    if msg is None:
        print("❌ 不应走到这里")
    else:
        print(f"✅ on_error 返回 str: {msg}")
    propagated: str | None = on_error(KeyError("x"), request)
    print(f"✅ 未处理异常返回 None（原样传播）: {propagated}")


# ── 坑 4：fallback provider 前缀 ───────────────────────────

def demo_fallback_prefix() -> None:
    """坑 4：fallback 模型字符串必须带 provider 前缀（约定常量，防手滑）。"""
    # ❌ 裸名（会炸）：FALLBACK_BAD = "gemini-3.1-flash"
    #    → init_chat_model 误判 provider → 试图 import vertexai → ModuleNotFoundError
    FALLBACK_OK: str = "google_genai:gemini-3.1-flash"  # ✅ 显式 provider
    print(f"✅ fallback 模型字符串带 provider 前缀: {FALLBACK_OK}")


# ── 坑 5：RunnableConfig 显式注解 ──────────────────────────

def demo_config_annotation() -> None:
    """坑 5：config 显式标注 RunnableConfig（Day 19 口诀复用）。"""
    config: RunnableConfig = {"recursion_limit": 25}  # ✅ 显式注解，Pyright 不报
    limit_obj: object = config.get("recursion_limit", 0)
    limit: int = limit_obj if isinstance(limit_obj, int) else 0
    print(f"✅ config 显式 RunnableConfig 注解: recursion_limit={limit}")


def main() -> None:
    demo_env_bool()
    demo_env_key()
    demo_on_error_signature()
    demo_fallback_prefix()
    demo_config_annotation()
    print("\n💡 坑位回顾：")
    print("   1. LANGCHAIN_TRACING_V2 是字符串，用 (raw or '').lower() == 'true' 判断")
    print("   2. os.getenv 返回 str | None → or 兜底")
    print("   3. on_error 签名 (Exception, ToolCallRequest) -> str | None")
    print("   4. fallback 模型字符串必须带 provider 前缀（google_genai:）")
    print("   5. config 显式 RunnableConfig 注解")


if __name__ == "__main__":
    main()
