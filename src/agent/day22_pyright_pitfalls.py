"""
Day 22 练习 5：Pyright 避坑实战 —— Agent 场景

Day 22 引入的新类型陷阱。本练习不调用 API，纯演示
「❌ 错误写法 vs ✅ 正确写法」。

⚠️ 所有标注 ❌ 的代码都在注释里说明原因，✅ 的可以放心照抄。

用法：直接运行，全部是演示性质，不含 API 调用。
"""

import sys

# Windows 下控制台/重定向输出统一 UTF-8，防止 emoji/中文打印报 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.tools import StructuredTool, tool


# ═══════════════════════════════════════════════════════
# 坑 1：StructuredTool.invoke 返回 Any —— 不要裸赋给具体类型
# ═══════════════════════════════════════════════════════

@tool
def sample_tool(word: str) -> int:
    """示例工具：返回字符长度。"""
    return len(word)


def pitfall1_tool_invoke_any() -> None:
    """坑 1：工具 .invoke() 的返回类型是 Any（工具返回值五花八门）"""

    # ❌ 错误：n: int = sample_tool.invoke({"word": "pytest"})
    #    invoke 返回 Any，Pyright 会报 "Any 无法赋给 int"（strict 模式下不可收窄）

    # ✅ 正确：先接 object，再 isinstance 校验 / 显式转换
    raw: object = sample_tool.invoke({"word": "pytest"})
    n: int = raw if isinstance(raw, int) else int(str(raw))
    assert n == 6
    print(f"✅ 工具返回值：object 接收 + isinstance 收窄（n={n}）")
    print("  记忆口诀：tool.invoke 返回 Any → object 接收再校验")


# ═══════════════════════════════════════════════════════
# 坑 2：AIMessage.content 联合类型（口诀 7 的 Agent 版）
# ═══════════════════════════════════════════════════════

def pitfall2_aimessage_content() -> None:
    """坑 2：AIMessage.content 是 str | list[...]，提取回答必须收窄"""

    msg: AIMessage = AIMessage(content="回答文本")

    # ❌ 错误：text: str = msg.content
    #    content 类型是 str | list[str | dict]，直接赋值报 invariant 错误

    # ✅ 正确：isinstance 收窄（Day 21 同款，抽成 message_text 辅助函数更好）
    text: str = msg.content if isinstance(msg.content, str) else str(msg.content)
    assert text == "回答文本"
    print("✅ AIMessage.content：isinstance 收窄后再赋 str")
    print("  记忆口诀：content 是联合类型 → 收窄 or str() 兜底")


# ═══════════════════════════════════════════════════════
# 坑 3：result["messages"] 是 object —— 逐层 isinstance 校验
# ═══════════════════════════════════════════════════════

def pitfall3_result_messages() -> None:
    """坑 3：create_agent 的 invoke 结果是 dict[str, Any] → 消息要逐层校验"""

    # 模拟 agent.invoke 的返回结构
    result: dict[str, object] = {
        "messages": [HumanMessage(content="问题"), AIMessage(content="回答")]
    }

    # ❌ 错误：messages: list[BaseMessage] = result["messages"]
    #    result["messages"] 是 object，直接赋 list 报错

    # ✅ 正确：isinstance(list) 校验 + 元素过滤
    msgs_obj: object = result.get("messages", [])
    messages: list[BaseMessage] = (
        [m for m in msgs_obj if isinstance(m, BaseMessage)]
        if isinstance(msgs_obj, list)
        else []
    )
    assert len(messages) == 2
    print(f"✅ result 消息提取：逐层 isinstance（{len(messages)} 条）")
    print("  记忆口诀：Agent 结果先 object → list → BaseMessage 三层校验")


# ═══════════════════════════════════════════════════════
# 坑 4：tool_calls 是 list[TypedDict] —— 取字段用 .get
# ═══════════════════════════════════════════════════════

def pitfall4_tool_calls() -> None:
    """坑 4：AIMessage.tool_calls 的元素是 ToolCall TypedDict"""

    msg: AIMessage = AIMessage(
        content="",
        tool_calls=[{"name": "duckduckgo_search", "args": {"query": "pytest"}, "id": "call_1", "type": "tool_call"}],
    )

    # ✅ 正确：TypedDict 字段访问 + str() 转换（name 理论上是 str，防御性转换更稳）
    for tc in msg.tool_calls:
        name: str = str(tc.get("name", ""))
        args: object = tc.get("args", {})
        print(f"✅ tool_call 提取: name={name}, args类型={type(args).__name__}")
        break
    print("  记忆口诀：tool_calls 元素是 TypedDict → .get 取值 + str() 转换")


# ═══════════════════════════════════════════════════════
# 坑 5：isinstance 分派顺序 —— 子类在前
# ═══════════════════════════════════════════════════════

def pitfall5_isinstance_order() -> None:
    """坑 5：消息 isinstance 分派时，具体类型在前、基类兜底在后"""

    msg: BaseMessage = AIMessage(content="hi")

    # ❌ 错误：if isinstance(msg, BaseMessage): ... elif isinstance(msg, AIMessage):
    #    BaseMessage 在前 → AIMessage 永远走不到（子类实例也是基类实例）

    # ✅ 正确：具体类型在前（AIMessage/ToolMessage），BaseMessage 兜底
    if isinstance(msg, AIMessage):
        label: str = "AI 消息"
    elif isinstance(msg, ToolMessage):
        label = "工具消息"
    elif isinstance(msg, BaseMessage):
        label = "其他消息"
    print(f"✅ isinstance 分派顺序正确（识别为: {label}）")
    print("  记忆口诀：子类在前，基类兜底 —— isinstance 分派的铁律")


# ═══════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    pitfall1_tool_invoke_any()
    pitfall2_aimessage_content()
    pitfall3_result_messages()
    pitfall4_tool_calls()
    pitfall5_isinstance_order()

    print("\n💡 Day 22 场景 Pyright 避坑总结：")
    print("  1. tool.invoke 返回 Any → object 接收 + isinstance 校验")
    print("  2. AIMessage.content 联合类型 → isinstance 收窄")
    print("  3. Agent 结果 dict → object → list → BaseMessage 三层校验")
    print("  4. tool_calls 元素是 TypedDict → .get 取值")
    print("  5. isinstance 分派：子类在前，基类兜底")
