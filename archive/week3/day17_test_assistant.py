"""
Day 17 练习 4：测试助手对话系统（⭐ 今日核心产出）

一个记住上下文的测试需求分析助手：
  - 支持多轮对话（分析 → 追问 → 补充 → 导出）
  - 基于 PydanticOutputParser 的结构化输出（兼容纯文本回退）
  - session_id 隔离不同用户
  - 自动管理对话历史

⚠️ Pyright 注意事项：
  - PydanticOutputParser 在管道中返回具体 Pydantic 类型，Pyright 友好
  - 但 Memory 模式下 LLM 的输出可能包含多轮回答，解析可能失败
  - 因此提供了 fallback：解析失败时回退到 StrOutputParser
  - assistant.chain 类型注解为 RunnableSerializable
  - 所有 invoke 返回值都显式注解类型

用法：直接运行演示场景，或在 main() 中注释掉不想跑的场景。
"""

import os
import json
from typing import Any
from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.output_parsers import StrOutputParser, PydanticOutputParser
from langchain_core.chat_history import BaseChatMessageHistory, InMemoryChatMessageHistory
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_core.runnables import RunnableConfig
from langchain_core.runnables import RunnableSerializable
from langchain_core.exceptions import OutputParserException
from pydantic import BaseModel, Field

# ═══════════════════════════════════════════════════════
# Pydantic 数据模型
# ═══════════════════════════════════════════════════════

class TestPoint(BaseModel):
    """单个测试关注点"""
    category: str = Field(description="测试分类：正向/边界/异常/安全/性能")
    description: str = Field(description="测试点描述")
    priority: str = Field(description="优先级：P0/P1/P2")


class AnalysisResult(BaseModel):
    """需求分析结果"""
    feature: str = Field(description="被分析的功能名称")
    summary: str = Field(description="需求摘要")
    test_points: list[TestPoint] = Field(description="测试关注点列表")
    recommendations: str = Field(description="测试建议")


# ═══════════════════════════════════════════════════════
# TestAssistant 类（核心产出）
# ═══════════════════════════════════════════════════════

class TestAssistant:
    """
    带记忆的测试助手。

    特性：
    - 多轮对话：记住之前分析的内容，支持追问和补充
    - 结构化输出：PydanticOutputParser 解析分析结果
    - Session 隔离：每个 conversation_id 独立的对话历史
    - 回退策略：解析失败时返回纯文本结果
    """

    SYSTEM_PROMPT = """你是一名资深软件测试工程师，有 10 年以上测试经验。

你的工作方式是：
1. 认真听取用户的需求描述
2. 记住对话历史中的上下文（之前分析过的功能、已经建议的测试点）
3. 根据上下文提供连贯、不重复的建议
4. 当用户说"补充"或"继续"时，基于之前的分析追加而非重来

当需要结构化分析时，输出 JSON 格式，包含以下字段：
{format_instructions}

当只是简单交流时（如问候、确认），直接文字回复即可。"""

    def __init__(self, model: str = "gemini-3.1-flash-lite", temperature: float = 0.2):
        # LLM
        self.llm = ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            google_api_key=os.getenv("GEMINI_API_KEY"),
        )

        # Parser
        self.pydantic_parser = PydanticOutputParser(pydantic_object=AnalysisResult)

        # Prompt
        prompt = ChatPromptTemplate.from_messages([
            ("system", self.SYSTEM_PROMPT),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
        ])
        self.prompt = prompt.partial(
            format_instructions=self.pydantic_parser.get_format_instructions()
        )

        # 主 Chain：用 StrOutputParser（更稳定，Memory 模式下 Pydantic 解析容易失败）
        # 原因：LLM 在有历史上下文时，可能输出非纯 JSON（如加上"根据之前的分析..."前缀）
        self.chain: RunnableSerializable = self.prompt | self.llm | StrOutputParser()

        # store
        self.store: dict[str, BaseChatMessageHistory] = {}

        # 带 Memory 的 Chain
        self.chain_with_memory = RunnableWithMessageHistory(
            self.chain,
            self._get_session_history,
            input_messages_key="input",
            history_messages_key="chat_history",
        )

    def _get_session_history(self, session_id: str) -> BaseChatMessageHistory:
        """内部方法：按 session_id 获取/创建历史"""
        if session_id not in self.store:
            self.store[session_id] = InMemoryChatMessageHistory()
        return self.store[session_id]

    def chat(self, message: str, session_id: str = "default") -> str:
        """
        发送消息并获取回复。

        Args:
            message: 用户输入
            session_id: 会话 ID，不同 ID 的对话互不干扰

        Returns:
            AI 的回复文本
        """
        config: RunnableConfig = {"configurable": {"session_id": session_id}}
        result: str = self.chain_with_memory.invoke(
            {"input": message},
            config=config,
        )
        return result

    def analyze_requirement(self, requirement: str, session_id: str = "default") -> AnalysisResult | None:
        """
        分析需求并尝试返回结构化结果。

        策略：先用纯文本 chain 生成，再尝试用 PydanticParser 解析。
        如果解析失败，打印原始文本，返回 None。
        """
        # 构建分析请求
        analyze_msg = f"""请分析以下需求，输出 JSON 格式的分析结果：

需求描述：
{requirement}

请严格按照以下 JSON 格式输出，不要添加额外说明：
{self.pydantic_parser.get_format_instructions()}"""

        response = self.chat(analyze_msg, session_id=session_id)

        # 尝试解析
        try:
            result: AnalysisResult = self.pydantic_parser.parse(response)
            return result
        except OutputParserException:
            print(f"结构化解析失败（LLM 输出非纯 JSON），原始回复的前 100 字符:")
            print(f"  {response[:100]}...")
            return None

    def get_history_summary(self, session_id: str = "default") -> str:
        """获取对话历史摘要"""
        if session_id not in self.store:
            return "（无历史记录）"
        hist = self.store[session_id]
        lines: list[str] = []
        for i, msg in enumerate(hist.messages):
            role = "👤 用户" if msg.__class__.__name__ == "HumanMessage" else "🤖 助手"
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            preview = content[:80].replace("\n", " ")
            lines.append(f"  [{i}] {role}: {preview}...")
        return "\n".join(lines) if lines else "（无历史记录）"

    def clear_session(self, session_id: str = "default") -> None:
        """清空指定会话"""
        if session_id in self.store:
            self.store[session_id].clear()

    def clear_all(self) -> None:
        """清空所有会话"""
        self.store.clear()


# ═══════════════════════════════════════════════════════
# 演示场景
# ═══════════════════════════════════════════════════════

def scenario1_multi_turn_analysis() -> None:
    """场景 1：多轮需求分析 — 分析 → 追问 → 补充"""
    print("=" * 60)
    print("场景 1：多轮需求分析（分析 → 追问 → 补充）")
    print("=" * 60)

    assistant = TestAssistant()
    session = "scenario1"

    # 第 1 轮：初步分析
    resp1 = assistant.chat(
        "我需要分析一个「用户登录」功能：支持手机号+密码登录，"
        "连续输错 5 次锁定 30 分钟。请帮我列出测试关注点。",
        session_id=session,
    )
    print(f"【第 1 轮】分析登录功能:\n{resp1[:200]}...\n")

    # 第 2 轮：追问（不需要重复需求描述）
    resp2 = assistant.chat(
        "你刚才提到的测试关注点中，安全测试部分能展开详细说说吗？",
        session_id=session,
    )
    print(f"【第 2 轮】追问安全测试:\n{resp2[:200]}...\n")

    # 第 3 轮：补充（基于上下文）
    resp3 = assistant.chat(
        "除了安全，还需要补充性能测试的关注点",
        session_id=session,
    )
    print(f"【第 3 轮】补充性能测试:\n{resp3[:200]}...\n")

    assistant.clear_session(session)


def scenario2_structured_analysis() -> None:
    """场景 2：结构化需求分析"""
    print("=" * 60)
    print("场景 2：结构化需求分析（尝试 Pydantic 解析）")
    print("=" * 60)

    assistant = TestAssistant(temperature=0.1)
    session = "scenario2"

    result = assistant.analyze_requirement(
        "用户注册功能：输入手机号、验证码、设置密码（8位以上，含大小写字母和数字）",
        session_id=session,
    )

    if result is not None:
        print(f"功能: {result.feature}")
        print(f"摘要: {result.summary}")
        print(f"测试点数量: {len(result.test_points)}")
        for tp in result.test_points:
            print(f"  [{tp.priority}] {tp.category}: {tp.description}")
        print(f"建议: {result.recommendations}")
    else:
        print("结构化解析失败，查看历史记录中的原始文本回复")

    assistant.clear_session(session)


def scenario3_interactive_demo() -> None:
    """场景 3：交互式演示 —— 模拟完整对话流程"""
    print("=" * 60)
    print("场景 3：完整对话流程演示")
    print("=" * 60)

    assistant = TestAssistant()
    session = "scenario3"

    conversation: list[tuple[str, str]] = [
        ("你好，我是测试工程师小张", "打招呼"),
        ("我需要测试一个电商购物车功能：支持添加商品、修改数量、删除商品、计算总价", "描述需求"),
        ("请重点分析并发场景下的测试点", "追问并发"),
        ("把以上分析整理成一个测试计划大纲", "导出"),
    ]

    for msg, label in conversation:
        resp = assistant.chat(msg, session_id=session)
        print(f"\n👤 [{label}]: {msg}")
        print(f"🤖 回复前 120 字符: {resp[:120]}...")

    print(f"\n📋 对话历史摘要:")
    print(assistant.get_history_summary(session))

    assistant.clear_session(session)


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的场景
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    scenario1_multi_turn_analysis()
    scenario2_structured_analysis()
    scenario3_interactive_demo()

    print("\n✅ Day 17 核心产出完成！")
    print("   TestAssistant 类 = Prompt + LLM + Memory 的封装")
    print("   特性：多轮对话记忆、Session 隔离、结构化分析")
    print("   后续可以扩展为：WebSocket 实时对话服务（Day 37 Streamlit 集成）")