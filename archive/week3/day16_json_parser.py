"""
Day 16 练习 3：JsonOutputParser + PydanticOutputParser

两种结构化输出解析方式：
  1. JsonOutputParser      → 返回 dict（简单直接）
  2. PydanticOutputParser   → 返回 Pydantic 模型实例（类型安全，Pyright 友好）

⚠️ Pyright 关键注意事项：
  - JsonOutputParser 在管道中返回类型为 Any，没有类型提示
  - PydanticOutputParser 利用 Pydantic 模型，返回具体类型 TestSuite
  - 推荐使用 PydanticOutputParser（Day 16+ 的默认选择）
"""

import os
from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, PydanticOutputParser
from langchain_core.exceptions import OutputParserException
from pydantic import BaseModel, Field

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.1,   # 结构化输出用低温度
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

# ═══════════════════════════════════════════════════════
# 定义 Pydantic 输出模型（类型安全，Pyright 友好）
# ═══════════════════════════════════════════════════════

class TestCase(BaseModel):
    """单个测试用例"""
    id: str = Field(description="测试用例编号，格式 TC-编号")
    title: str = Field(description="测试用例标题")
    priority: str = Field(description="优先级：P0/P1/P2")
    test_type: str = Field(description="测试类型：正向/边界/异常")
    preconditions: list[str] = Field(description="前置条件列表")
    steps: list[str] = Field(description="测试步骤列表")
    expected: str = Field(description="预期结果")


class TestSuite(BaseModel):
    """测试套件（包含多个用例）"""
    feature: str = Field(description="被测功能名称")
    test_cases: list[TestCase] = Field(description="测试用例列表")

# ═══════════════════════════════════════════════════════
# 实验 1：JsonOutputParser —— 直接返回 dict
# ═══════════════════════════════════════════════════════

def exp1_json_output_parser() -> None:
    """实验 1：JsonOutputParser 基础用法"""
    print("=" * 60)
    print("实验 1：JsonOutputParser —— 返回 dict（简单直接）")
    print("=" * 60)

    json_parser = JsonOutputParser()    
    json_prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一名资深软件测试工程师。
请严格按照以下 JSON 格式输出测试用例，不要添加任何额外文字。
{format_instructions}"""),
        ("human", "功能需求：{requirement}\n测试类型：{test_type}"),
    ])
    json_prompt = json_prompt.partial(
        format_instructions=json_parser.get_format_instructions()
    )
    json_chain = json_prompt | llm | json_parser

    try:
        result_dict = json_chain.invoke({
            "requirement": "用户登录功能：手机号+密码",
            "test_type": "正向功能测试",
        })
        print(f"返回类型: {type(result_dict).__name__}")
        keys = list(result_dict.keys()) if isinstance(result_dict, dict) else "N/A"
        print(f"顶层键: {keys}")
        print(f"内容:\n{result_dict}")
    except OutputParserException as e:
        print(f"解析失败: {e}")

# ═══════════════════════════════════════════════════════
# 实验 2：PydanticOutputParser —— 返回 Pydantic 模型实例
# ═══════════════════════════════════════════════════════

def exp2_pydantic_output_parser() -> None:
    """实验 2：PydanticOutputParser 类型安全用法"""
    print("\n" + "=" * 60)
    print("实验 2：PydanticOutputParser —— 返回 TestSuite 实例（类型安全）")
    print("=" * 60)

    pydantic_parser = PydanticOutputParser(pydantic_object=TestSuite)
    pydantic_prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一名资深软件测试工程师。
请根据需求生成完整的测试用例。{format_instructions}"""),
        ("human", "功能需求：{requirement}\n测试类型：{test_type}"),
    ])
    pydantic_prompt = pydantic_prompt.partial(
        format_instructions=pydantic_parser.get_format_instructions()
    )
    pydantic_chain = pydantic_prompt | llm | pydantic_parser

    try:
        suite: TestSuite = pydantic_chain.invoke({
            "requirement": "用户登录功能：手机号+密码",
            "test_type": "正向功能测试",
        })
        print(f"返回类型: {type(suite).__name__}")
        print(f"功能: {suite.feature}")
        print(f"用例数量: {len(suite.test_cases)}")
        for tc in suite.test_cases:
            print(f"  - [{tc.priority}] {tc.id}: {tc.title}")
            print(f"    类型: {tc.test_type}")
            print(f"    步骤: {len(tc.steps)} 步")
            print()
    except OutputParserException as e:
        print(f"Pydantic 解析失败: {e}")


# ═══════════════════════════════════════════════════════
# 实验 3：对比 —— Pydantic 模型的优势
# ═══════════════════════════════════════════════════════

def exp3_compare() -> None:
    """实验 3：纯展示对比表，无 API 调用"""
    print("=" * 60)
    print("实验 3：Pydantic vs 纯 dict 的对比")
    print("=" * 60)
    print("""
┌──────────────────────┬──────────────────────────┬────────────────────────────┐
│ 维度                 │ JsonOutputParser (dict)  │ PydanticOutputParser (Model)│
├──────────────────────┼──────────────────────────┼────────────────────────────┤
│ 返回类型             │ dict (Pyright 推断 Any)  │ TestSuite（明确类型）       │
│ 字段访问             │ result["test_cases"]     │ suite.test_cases（IDE 补全）│
│ 字段验证             │ 无（运行时才发现缺失）     │ 自动验证（解析时就检查）    │
│ IDE 智能提示          │ ❌ 无                    │ ✅ 完整补全                 │
│ 重构支持             │ ❌ 手动全改               │ ✅ 改 Pydantic 模型即可     │
│ 默认值/可选字段       │ 手动处理                  │ Field(default=...) 声明式   │
└──────────────────────┴──────────────────────────┴────────────────────────────┘

💡 推荐：Day 16 起，结构化输出优先使用 PydanticOutputParser！
""")


# ═══════════════════════════════════════════════════════
# 实验 4：解析失败的处理
# ═══════════════════════════════════════════════════════

def exp4_parse_failure() -> None:
    """实验 4：演示 try/except 捕获解析失败"""
    print("=" * 60)
    print("实验 4：解析失败时怎么办？")
    print("=" * 60)

    pydantic_parser = PydanticOutputParser(pydantic_object=TestSuite)
    pydantic_prompt = ChatPromptTemplate.from_messages([
        ("system", """你是一名资深软件测试工程师。
请根据需求生成完整的测试用例。{format_instructions}"""),
        ("human", "功能需求：{requirement}\n测试类型：{test_type}"),
    ])
    pydantic_prompt = pydantic_prompt.partial(
        format_instructions=pydantic_parser.get_format_instructions()
    )
    pydantic_chain = pydantic_prompt | llm | pydantic_parser

    try:
        result = pydantic_chain.invoke({
            "requirement": "一个非常模糊的描述",
            "test_type": "未知类型",
        })
        print(f"成功: {type(result).__name__}")
    except OutputParserException as e:
        print(f"解析失败（预期内）: {str(e)[:100]}...")

    print("\n💡 解析失败的常见原因：")
    print("  1. LLM 输出的 JSON 格式不合法（少了逗号/引号）")
    print("  2. 输出包含了代码块标记 ```json...```（JsonOutputParser 能处理）")
    print("  3. 输出字段和 Pydantic 模型不匹配")
    print("  → 解法：降低 temperature、优化 Prompt 中的格式指令")



if __name__ == "__main__":
    # exp1_json_output_parser()
    exp2_pydantic_output_parser()
    # exp3_compare()
    # exp4_parse_failure()