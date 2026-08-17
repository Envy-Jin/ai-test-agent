"""
Day 22 练习 3：create_agent —— 第一个有工具的 Agent

用 LangChain v1 的 create_agent 构建能自主联网搜索的测试助手。
对比学习计划的旧代码（create_react_agent + AgentExecutor，已弃用）：
  - 输入：{"messages": [HumanMessage(...)]}（不是 {"input": ...}）
  - 输出：result["messages"][-1].content（不是 result["output"]）
  - system_prompt 参数（不是 prompt + 手写 ReAct 模板）
  - 防死循环：config={"recursion_limit": 25}（不是 max_iterations）

⚠️ Pyright 注意事项：
  - result 是 dict[str, object]：取 "messages" 后用 isinstance(list) 校验，
    元素再用 isinstance 分派（HumanMessage/AIMessage/ToolMessage）
  - AIMessage.content 是 str | list[...] 联合类型（口诀 7 同款）→ isinstance 收窄
  - AIMessage.tool_calls 是 list[ToolCall]，ToolCall 是 TypedDict：
    取值用 .get("name")/["name"]，name 字段是 str
  - create_agent 返回类型复杂 → 变量不写返回注解，让 Pyright 推断

用法：直接运行（真实调用 LLM + 联网搜索，需 .env 的 GEMINI_API_KEY 和代理）。
"""

import sys

# Windows 下控制台/重定向输出统一 UTF-8，防止 emoji/中文打印报 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()

from langchain.agents import create_agent
from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    ToolMessage,
)
from langchain_core.runnables import RunnableConfig
from langchain_google_genai import ChatGoogleGenerativeAI

from day22_ddg_search import duckduckgo_search

# ═══════════════════════════════════════════════════════
# 模块级：LLM（Agent 的大脑）
# ═══════════════════════════════════════════════════════

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.2,
)

# ═══════════════════════════════════════════════════════
# 辅助：安全提取消息文本（content 联合类型收窄，Day 21 同款）
# ═══════════════════════════════════════════════════════

def message_text(msg: BaseMessage) -> str:
    """把任意消息的 content 收窄为 str（content 是 str | list[...] 联合类型）。"""
    content: object = msg.content
    if isinstance(content, str):
        return content
    return str(content)



# ═══════════════════════════════════════════════════════
# 辅助：打印 Agent 消息轨迹（读懂 ReAct 循环的现代形态）
# ═══════════════════════════════════════════════════════

def print_trace(messages: list[BaseMessage]) -> None:
    """按消息类型打印 Agent 决策轨迹（Thought→Action→Observation→Final）。"""
    for msg in messages:
        if isinstance(msg, HumanMessage):
            print(f"  🧑 [Human] {message_text(msg)[:60]}")
        elif isinstance(msg, AIMessage):
            tool_calls: list[dict[str, object]] = [
                {"name": str(tc.get("name", "")), "args": tc.get("args", {})}
                for tc in msg.tool_calls
            ]
            if tool_calls:
                for tc in tool_calls:
                    print(f"  🤔 [AI 决策] 调用工具: {tc['name']} 参数: {tc['args']}")
            else:
                print(f"  🤖 [AI 最终回答] {message_text(msg)[:80]}...")
        elif isinstance(msg, ToolMessage):
            print(f"  👀 [Observation] {message_text(msg)[:80]}...")

# ═══════════════════════════════════════════════════════
# 构建：第一个有工具的 Agent
# ═══════════════════════════════════════════════════════

def build_search_agent():
    """构建带搜索工具的测试助手 Agent。

    对比旧 API：create_react_agent(llm, tools, prompt) + AgentExecutor(...)
    现在一步到位，且无需手动 llm.bind_tools()（create_agent 自动绑定）。
    """
    return create_agent(
        model=llm,
        tools=[duckduckgo_search],
        system_prompt=(
            "你是一名资深测试工程师的 AI 助手。\n"
            "规则：\n"
            "1. 涉及最新信息（新版本、新闻、近期数据）时，必须先用搜索工具核实\n"
            "2. 回答要基于搜索结果，注明信息来源，不要编造\n"
            "3. 用中文回答，简洁分点"
        ),
    )

# ═══════════════════════════════════════════════════════
# 实验 1：会搜索的 Agent（学习计划的原始目标：查 pytest 新特性）
# ═══════════════════════════════════════════════════════

def exp1_search_agent() -> None:
    """实验 1：Agent 自主决定搜索 → 拿到结果 → 生成回答（完整 ReAct 循环）"""
    print("=" * 60)
    print("实验 1：第一个有工具的 Agent（联网查 pytest 新特性）")
    print("=" * 60)

    agent = build_search_agent()
    question: str = "最新版本的 pytest 有什么新特性？请搜索后回答。"

    # config 显式标注 RunnableConfig（口诀 5）；recursion_limit 替代旧 max_iterations
    config: RunnableConfig = {"recursion_limit": 25}
    result: dict[str, object] = agent.invoke(
        {"messages": [HumanMessage(content=question)]}, config=config
    )

    # 提取消息轨迹（isinstance 逐层校验，Pyright 安全）
    messages_obj: object = result.get("messages", [])
    messages: list[BaseMessage] = (
        [m for m in messages_obj if isinstance(m, BaseMessage)]
        if isinstance(messages_obj, list)
        else []
    )

    print(f"\n📜 消息轨迹（{len(messages)} 条）：")
    print_trace(messages)

    # 最终回答 = 最后一条 AIMessage（无 tool_calls 的那条）
    final_answer: str = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            final_answer = message_text(msg)
            break

    print("\n" + "-" * 60)
    print(f"🎯 最终回答：\n{final_answer}")


# ═══════════════════════════════════════════════════════
# 实验 2：不需要工具时，Agent 直接回答（模型自主决策的体现）
# ═══════════════════════════════════════════════════════

def exp2_no_tool_needed() -> None:
    """实验 2：常识性问题 → Agent 跳过搜索直接回答（轨迹里没有 ToolMessage）"""
    print("\n" + "=" * 60)
    print("实验 2：不需要工具的问题（Agent 自主跳过搜索）")
    print("=" * 60)

    agent = build_search_agent()
    config: RunnableConfig = {"recursion_limit": 25}
    result: dict[str, object] = agent.invoke(
        {"messages": [HumanMessage(content="什么是黑盒测试和白盒测试的区别？")]},
        config=config,
    )

    messages_obj: object = result.get("messages", [])
    messages: list[BaseMessage] = (
        [m for m in messages_obj if isinstance(m, BaseMessage)]
        if isinstance(messages_obj, list)
        else []
    )

    tool_used: bool = any(isinstance(m, ToolMessage) for m in messages)
    print(f"消息数: {len(messages)} | 是否用了搜索工具: {tool_used}（预期 False）")
    print(f"回答预览: {message_text(messages[-1])[:100]}...")


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    # exp1_search_agent()
    exp2_no_tool_needed()

    print("\n✅ 第一个 Agent 完成！")
    print("   模型自主决定：要不要搜索、搜什么、何时给出最终回答")
    print("   下一步：多工具 + 流式观察（练习 4）")
