"""
Day 23 练习 3：参数校验 + 工具异常降级 —— 工具失败时怎么办

三个层次（今天全部覆盖）：
  1. 工具内手动校验：非法参数 → 返回友好错误文本（模型能看到原因并自我修正）
  2. 工具内 try/except：网络/解析异常 → 转错误文本（不让异常炸掉 Agent 循环）
  3. ToolErrorMiddleware（LangChain v1 新 API，2026-08-17 联网确认）：
     工具【抛出】的异常 → 拦截 → 转成 error ToolMessage 喂回模型
     → 模型看到"工具报错"后可换参数重试，Agent 循环不中断

两种降级风格的对比（关键心智模型）：
  风格 A：返回错误文本（推荐）→ 原因对模型可见，模型自己调整
  风格 B：抛异常（不配 middleware → Agent 中断；配 ToolErrorMiddleware → 模型可见）

⚠️ Pyright 注意事项：
  - ToolErrorMiddleware(on_error) 的回调签名：
      def on_error(exc: Exception, request: ToolCallRequest) -> str | None
    request.tool_call 是 ToolCall TypedDict → .get("name") / .get("id") 取值
  - 返回 None 表示"让异常继续传播"（只处理你想处理的异常）
  - ToolCallRequest 构造需要 tool_call 字典 + tool/state/runtime（演示传 None，
    runtime 参数要加 # type: ignore[arg-type]）
  - create_agent 用 FakeChatModel 也能【构建】（构建期不 bind_tools，零 API）

用法：直接运行（零 API：本地演示 + 假模型构建）。
"""

import sys

# Windows 下控制台/重定向输出统一 UTF-8，防止 emoji/中文打印报 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ToolCallRequest,
    ToolErrorMiddleware,
    ToolRetryMiddleware,
)
from langchain_core.language_models.fake_chat_models import FakeChatModel
from langchain_core.tools import tool


# ═══════════════════════════════════════════════════════
# 风格 A：返回错误文本（推荐 —— 原因对模型可见）
# ═══════════════════════════════════════════════════════

@tool
def safe_divide(a: float, b: float) -> str:
    """两个数相除，返回商。b 为 0 时返回错误文本（而不是抛异常）。"""
    if b == 0:
        return "❌ 除数 b 不能为 0，请换一个非零除数"
    return f"{a / b}"


# ═══════════════════════════════════════════════════════
# 风格 B：抛异常（配合 ToolErrorMiddleware 兜底）
# ═══════════════════════════════════════════════════════

@tool
def risky_divide(a: float, b: float) -> str:
    """两个数相除，返回商。b 为 0 时抛 ValueError（由 ToolErrorMiddleware 转错误消息）。"""
    if b == 0:
        raise ValueError("除数 b 不能为 0")
    return f"{a / b}"


def on_error(exc: Exception, request: ToolCallRequest) -> str | None:
    """ToolErrorMiddleware 回调：工具异常 → 错误消息（喂回模型让它修正参数）。

    返回 str → 转成 error ToolMessage；返回 None → 异常继续传播（中断）。
    只处理你关心的异常类型，其余放行（None）。
    """
    if not isinstance(exc, ValueError):
        return None  # 只处理 ValueError，其余异常继续传播
    tool_name: str = str(request.tool_call.get("name", "unknown"))
    return f"工具 {tool_name} 执行失败（{type(exc).__name__}）: {exc}。请检查参数后重试。"


# ═══════════════════════════════════════════════════════
# 实验 1：风格 A —— 返回错误文本（推荐）
# ═══════════════════════════════════════════════════════

def exp1_return_error_text() -> None:
    """实验 1：风格 A —— 错误文本对模型可见，模型能自我修正"""
    print("=" * 60)
    print("实验 1：风格 A —— 返回错误文本")
    print("=" * 60)

    raw: object = safe_divide.invoke({"a": 1, "b": 0})
    text: str = raw if isinstance(raw, str) else str(raw)
    print(f"调用结果: {text}")
    print("💡 模型收到这段文本后，会换一个非零 b 重试（Day 24 真实运行可见）")


# ═══════════════════════════════════════════════════════
# 实验 2：风格 B —— 裸抛异常的后果
# ═══════════════════════════════════════════════════════

def exp2_raise_exception() -> None:
    """实验 2：风格 B —— 不配 middleware 时异常会中断整个 Agent 循环"""
    print("\n" + "=" * 60)
    print("实验 2：风格 B —— 裸抛异常")
    print("=" * 60)

    try:
        risky_divide.invoke({"a": 1, "b": 0})
    except ValueError as exc:
        print(f"⚠️ 抛出的异常: {type(exc).__name__}: {exc}")
        print("   没有 middleware 时，这个异常会直接中断 Agent 循环（模型看不到原因）")


# ═══════════════════════════════════════════════════════
# 实验 3：ToolErrorMiddleware —— 异常转错误消息喂回模型
# ═══════════════════════════════════════════════════════

def exp3_build_agent_with_middleware() -> None:
    """实验 3：create_agent + ToolErrorMiddleware（假模型构建，零 API）"""
    print("\n" + "=" * 60)
    print("实验 3：ToolErrorMiddleware（新 API）")
    print("=" * 60)

    agent = create_agent(
        model=FakeChatModel(),
        tools=[risky_divide],
        middleware=[ToolErrorMiddleware(on_error)],
        system_prompt="你是数学助手。",
    )
    print(f"✅ create_agent + ToolErrorMiddleware 构建成功: {type(agent).__name__}")
    print("   真实运行（Day 24 换真模型）时：b=0 → 模型收到错误消息 → 换参数重试")


# ═══════════════════════════════════════════════════════
# 实验 4：on_error 回调单测（不跑 Agent 也能验证）
# ═══════════════════════════════════════════════════════

def exp4_on_error_unittest() -> None:
    """实验 4：on_error 单测 —— ToolCallRequest 可独立构造"""
    print("\n" + "=" * 60)
    print("实验 4：on_error 回调单测")
    print("=" * 60)

    req = ToolCallRequest(
        tool_call={
            "name": "risky_divide",
            "args": {"a": 1, "b": 0},
            "id": "call_1",
            "type": "tool_call",
        },
        tool=None,
        state=None,
        runtime=None,  # type: ignore[arg-type]
    )

    msg: str | None = on_error(ValueError("除数 b 不能为 0"), req)
    print(f"ValueError → {msg}")
    assert msg is not None and "risky_divide" in msg

    other: str | None = on_error(RuntimeError("网络超时"), req)
    print(f"RuntimeError → {other}（None = 放行，异常继续传播）")
    assert other is None


# ═══════════════════════════════════════════════════════
# 实验 5（进阶）：ToolRetryMiddleware —— 工具失败自动重试
# ═══════════════════════════════════════════════════════

def exp5_retry_middleware() -> None:
    """实验 5：ToolRetryMiddleware —— 指数退避自动重试"""
    print("\n" + "=" * 60)
    print("实验 5：ToolRetryMiddleware（进阶）")
    print("=" * 60)

    agent = create_agent(
        model=FakeChatModel(),
        tools=[safe_divide],
        middleware=[ToolRetryMiddleware(max_retries=2)],
    )
    print(f"✅ ToolRetryMiddleware 构建成功: {type(agent).__name__}")
    print("   参数: max_retries / retry_on / on_failure / backoff_factor / jitter")
    print("   可和 ToolErrorMiddleware 组合：先自动重试，重试仍失败再转错误消息")


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    # exp1_return_error_text()
    # exp2_raise_exception()
    exp3_build_agent_with_middleware()
    # exp4_on_error_unittest()
    # exp5_retry_middleware()

    print("\n✅ 参数校验 + 异常降级完成！")
    print("   首选：工具内校验 + try/except 返回错误文本")
    print("   兜底：ToolErrorMiddleware 把异常转成错误消息喂回模型")
    print("   下一步：把既有模块包装成工具链（练习 4）")