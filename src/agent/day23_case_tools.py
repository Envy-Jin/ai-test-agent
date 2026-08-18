"""
Day 23 练习 4：把既有模块包装成工具链 —— 测试用例生成工具箱

学习计划 Day 23 今日产出：完成 3 个测试专用工具的定义
  （generate_test_cases / run_api_test / analyze_bug_report）+ 组装成 Agent

今天的组合拳（复用 Day 12 的模块 + Day 22 的工具机制）：
  1. generate_test_cases：LLM 生成测试用例 + json_extractor 清洗（Day 12）
     → 内部用"小模型 JSON 三件套"（完整示例 + 只输出一个对象 + 提取清洗）
  2. analyze_bug_report：LLM 结构化分析 Bug（JSON 提取 + 校验）
  3. run_api_test：从练习 2 导入（接口调用工具）
  4. kb_search：从 Day 22 导入（内部知识库工具）
  → create_agent 组装成"测试用例生成 Agent 雏形"（Day 24 会基于它做完整版）

⚠️ Pyright 注意事项：
  - extract_json 返回 dict | list | None → isinstance(dict) 收窄后再取字段
  - llm.invoke 返回 AIMessage → content 是 str | list[...] → isinstance 收窄
  - 工具统一返回 str（Observation 全是文本，类型最稳）
  - 复用既有工具：直接 import 工具对象（无需重新装饰）
  - 提示词里 JSON 示例的花括号必须双写 {{ }} 转义（Day 16/19 口诀）

用法：直接运行（实验 1 零 API；实验 2/3 真实调用 LLM，需 .env 的 GEMINI_API_KEY）。
"""

import json
import sys

# Windows 下控制台/重定向输出统一 UTF-8，防止 emoji/中文打印报 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI

from json_extractor import extract_json

from day22_agent_multi import kb_search
from day23_annotated_args import run_api_test

# ═══════════════════════════════════════════════════════
# 模块级：LLM（Agent 的大脑 + 工具的生成引擎）
# ═══════════════════════════════════════════════════════

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.2,
)


# ═══════════════════════════════════════════════════════
# 工具 1：generate_test_cases —— LLM 生成 + json_extractor 清洗
# ═══════════════════════════════════════════════════════

GENERATE_CASES_PROMPT = """你是一名资深测试工程师。请为以下需求生成测试用例，覆盖正向、边界、异常场景。

需求：{requirement}

只输出一个 JSON 对象，不要输出数组，不要输出其他文字，格式如下：
{{
  "feature_name": "功能名称",
  "test_cases": [
    {{
      "id": "TC001",
      "title": "用例标题",
      "type": "正向/边界/异常",
      "priority": "P0/P1/P2",
      "steps": ["步骤1", "步骤2"],
      "expected": "预期结果"
    }}
  ]
}}"""


@tool
def generate_test_cases(requirement: str) -> str:
    """根据需求描述生成结构化测试用例（JSON 格式）。
    输入需求文本，返回包含 feature_name 和 test_cases 数组的 JSON 字符串。
    当用户要求"生成测试用例 / 编写用例"时使用。"""
    try:
        response = llm.invoke(
            [HumanMessage(content=GENERATE_CASES_PROMPT.format(requirement=requirement))]
        )
        raw_text: str = content_to_text(response.content)
    except Exception as exc:
        return f"❌ 生成失败（{type(exc).__name__}）: {exc}"

    parsed: dict | list | None = extract_json(raw_text)

    if not isinstance(parsed, dict):
        return "❌ 模型输出无法解析为 JSON 对象，请重试"

    # 容错清洗（Day 12 口诀：setdefault 补缺省 + 类型兜底）
    cases: list = parsed.get("test_cases", [])
    if not isinstance(cases, list):
        cases = []
    parsed["test_cases"] = cases
    if "feature_name" not in parsed:
        parsed["feature_name"] = requirement[:20]
    return json.dumps(parsed, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════
# 工具 2：analyze_bug_report —— LLM 结构化分析 Bug
# ═══════════════════════════════════════════════════════

ANALYZE_BUG_PROMPT = """你是一名资深测试工程师。请分析以下 Bug 报告，输出结构化结论。

Bug 报告：
{bug_text}

只输出一个 JSON 对象，不要输出数组，不要输出其他文字，格式如下：
{{
  "bug_summary": "一句话总结",
  "bug_type": "功能缺陷/性能问题/UI问题/安全漏洞/兼容性问题",
  "severity": "致命/严重/一般/轻微",
  "reproduce_steps": ["复现步骤1", "复现步骤2"],
  "suggestion": "修复/测试建议"
}}"""


@tool
def analyze_bug_report(bug_text: str) -> str:
    """分析 Bug 报告，提取关键信息（类型/严重度/复现步骤）并给出建议。
    输入 Bug 描述的原始文本，返回 JSON 字符串。
    当用户要求"分析 Bug / 分析缺陷"时使用。"""
    try:
        response = llm.invoke(
            [HumanMessage(content=ANALYZE_BUG_PROMPT.format(bug_text=bug_text))]
        )
        raw_text: str = content_to_text(response.content)
    except Exception as exc:
        return f"❌ 分析失败（{type(exc).__name__}）: {exc}"

    parsed: dict | list | None = extract_json(raw_text)
    if not isinstance(parsed, dict):
        return "❌ 模型输出无法解析为 JSON 对象，请重试"
    return json.dumps(parsed, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════
# 组装：测试用例生成 Agent 雏形（4 工具）
# ═══════════════════════════════════════════════════════
CASE_TOOLS = [generate_test_cases, analyze_bug_report, run_api_test, kb_search]


def build_case_agent():
    """组装 4 工具 Agent：生成用例 / 分析 Bug / 调接口 / 查知识库。"""
    return create_agent(
        model=llm,
        tools=CASE_TOOLS,
        system_prompt=(
            "你是一名资深测试工程师的 AI 助手，可以使用多个工具完成任务。\n"
            "工具选择规则：\n"
            "1. 用户要求生成测试用例 → generate_test_cases\n"
            "2. 用户要求分析 Bug 报告 → analyze_bug_report\n"
            "3. 用户要求实际调用接口验证 → run_api_test\n"
            "4. 问题涉及项目内部知识（历史 Bug/需求/已有用例）→ kb_search\n"
            "5. 用中文回答，基于工具返回的真实结果，不要编造"
        ),
    )


# ═══════════════════════════════════════════════════════
# 辅助：AIMessage.content 收窄为纯文本（Day 23 关键修复）
# ═══════════════════════════════════════════════════════

def content_to_text(content: object) -> str:
    """把 AIMessage.content 收窄为纯文本。

    content 可能是：
      - str：直接返回
      - list[dict]：Gemini 3.1 等新模型的 content blocks，
        形如 [{"type": "text", "text": "..."}] → 提取所有 text 块拼接。
    ⚠️ 不能 str(content)：list 会变成 Python repr（[{'type': ...}]），
       不是合法 JSON，extract_json 会解析失败返回 None。
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(str(block.get("text", "")))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return str(content)


def message_text(msg: BaseMessage) -> str:
    """把任意消息的 content 收窄为 str（内部复用 content_to_text）。"""
    return content_to_text(msg.content)


# ═══════════════════════════════════════════════════════
# 实验 1：组装 Agent（零 API）
# ═══════════════════════════════════════════════════════

def exp1_build_agent() -> None:
    """实验 1：组装 4 工具 Agent（只构建，不调用 LLM）"""
    print("=" * 60)
    print("实验 1：组装测试用例生成 Agent（4 工具）")
    print("=" * 60)

    # tools = [generate_test_cases, analyze_bug_report, run_api_test, kb_search]
    agent = build_case_agent()
    print(f"✅ Agent 构建成功: {type(agent).__name__}")
    print(f"   工具箱: {[t.name for t in CASE_TOOLS]}")
    print("   （实验 2/3 用真实 LLM 调用）")


# ═══════════════════════════════════════════════════════
# 实验 2：generate_test_cases 工具直调（真实 LLM）
# ═══════════════════════════════════════════════════════

def exp2_generate_cases_direct() -> None:
    """实验 2：直接调用 generate_test_cases（不经过 Agent）"""
    print("\n" + "=" * 60)
    print("实验 2：generate_test_cases 工具直调（真实 LLM）")
    print("=" * 60)

    raw: object = generate_test_cases.invoke(
        {"requirement": "用户登录，支持手机号和密码，密码不少于 8 位"}
    )
    text: str = raw if isinstance(raw, str) else str(raw)
    print(text[:600])
    print("\n💡 输出是干净的 JSON 字符串（json_extractor 清洗过）—— 这就是 Observation")

# ═══════════════════════════════════════════════════════
# 实验 3：Agent 自主选工具（真实 LLM）
# ═══════════════════════════════════════════════════════

def exp3_agent_loop() -> None:
    """实验 3：Agent 自主选择工具（真实 LLM，看消息轨迹）"""
    print("\n" + "=" * 60)
    print("实验 3：Agent 自主选择工具（真实 LLM）")
    print("=" * 60)

    agent = build_case_agent()
    config: RunnableConfig = {"recursion_limit": 25}
    question: str = "帮我为「购物车结算功能」生成测试用例，覆盖异常场景"
    result: dict[str, object] = agent.invoke(
        {"messages": [HumanMessage(content=question)]}, config=config
    )

    msgs_obj: object = result.get("messages", [])
    messages: list[BaseMessage] = (
        [m for m in msgs_obj if isinstance(m, BaseMessage)]
        if isinstance(msgs_obj, list)
        else []
    )
    print(f"\n📜 消息轨迹（{len(messages)} 条）：")
    for msg in messages:
        if isinstance(msg, HumanMessage):
            print(f"  🧑 [Human] {message_text(msg)[:50]}")
        elif isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                print(f"  🤔 [决策] 调用 {str(tc.get('name', ''))} 参数: {tc.get('args', {})}")
        elif isinstance(msg, ToolMessage):
            print(f"  👀 [Observation] {message_text(msg)[:60]}...")
        elif isinstance(msg, AIMessage):
            print(f"  🤖 [最终回答] {message_text(msg)[:80]}...")

    final_answer: str = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not msg.tool_calls:
            final_answer = message_text(msg)
            break
    print("\n" + "-" * 60)
    print(f"🎯 最终回答：\n{final_answer[:500]}")
    print("💡 预期：模型选 generate_test_cases（可能先 kb_search 查项目背景）")

# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    # exp1_build_agent()
    # exp2_generate_cases_direct()
    exp3_agent_loop()

    print("\n✅ 测试用例生成工具箱完成！")
    print("   既有模块（Day 12 json_extractor）+ 新工具（用例生成/Bug 分析）+ 复用（kb_search）")
    print("   4 个工具组装成 Agent 雏形 —— Day 24 在此基础上做完整测试用例生成 Agent")