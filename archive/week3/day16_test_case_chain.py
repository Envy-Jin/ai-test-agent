"""
Day 16 练习 4：构建「需求→测试用例」完整 Chain

这是今日的核心产出 —— 一个可复用的测试用例生成管道。

特性：
  - 基于 PydanticOutputParser（类型安全，Pyright 友好）
  - 支持多种测试类型（正向/边界/异常/安全）
  - 输入验证（需求不能为空）
  - 输出可直接序列化为 JSON
"""

import os
import json
from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.exceptions import OutputParserException
from langchain_core.runnables import RunnableSerializable
from pydantic import BaseModel, Field

# ═══════════════════════════════════════════════════════
# Pydantic 数据模型
# ═══════════════════════════════════════════════════════

class TestCase(BaseModel):
    """单个测试用例"""
    id: str = Field(description="用例编号，如 TC-001")
    title: str = Field(description="用例标题")
    priority: str = Field(description="优先级：P0/P1/P2")
    test_type: str = Field(description="测试类型：正向/边界/异常/安全/性能")
    preconditions: list[str] = Field(description="前置条件")
    steps: list[str] = Field(description="测试步骤")
    expected: str = Field(description="预期结果")


class TestSuite(BaseModel):
    """测试套件"""
    feature: str = Field(description="被测功能名称")
    requirement_summary: str = Field(description="需求摘要")
    test_cases: list[TestCase] = Field(description="测试用例列表")
    coverage_notes: str = Field(default="", description="覆盖度说明")

# ═══════════════════════════════════════════════════════
# Chain 构建
# ═══════════════════════════════════════════════════════

class TestCaseGenerator:
    """测试用例生成器 —— 封装 Chain 的构建和调用"""

    def __init__(self, model: str = "gemini-3.1-flash-lite", temperature: float = 0.1):
        # LLM
        self.llm = ChatGoogleGenerativeAI(
            model=model,
            temperature=temperature,
            google_api_key=os.getenv("GEMINI_API_KEY"),
        )

        # Parser
        self.parser = PydanticOutputParser(pydantic_object=TestSuite)

        # Prompt
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """你是一名资深软件测试工程师，有10年以上测试经验。
请根据需求描述，生成完整的测试用例套件。

{format_instructions}

⚠️ 重要规则：
- 每个功能至少生成 3 个用例（正向、边界、异常各至少 1 个）
- P0 级别的用例标注为最高优先级
- 测试步骤要具体、可执行，不能太笼统
- 不要输出任何 Markdown 标记或代码块符号"""),
            ("human", """功能需求：{requirement}
测试类型侧重：{test_type}

请生成覆盖以下场景的测试用例：
1. 正常功能流程（正向测试）
2. 边界条件（输入范围边界值、空值、特殊字符）
3. 异常场景（非法输入、超时、并发冲突）
4. 如果涉及用户输入，补充安全测试（SQL注入、XSS）"""),
        ])

        # 注入格式指令
        self.prompt = self.prompt.partial(
            format_instructions=self.parser.get_format_instructions()
        )

        # 构建 Chain
        self.chain: RunnableSerializable = self.prompt | self.llm | self.parser

    def generate(
        self,
        requirement: str,
        test_type: str = "综合测试",
    ) -> TestSuite | None:
        """
        生成测试用例套件。

        Args:
            requirement: 功能需求描述（不能为空）
            test_type: 测试类型侧重

        Returns:
            TestSuite 实例，如果解析失败返回 None

        ⚠️ Pyright 注意事项：
           - 返回 Optional[TestSuite]，调用方必须检查 None
           - 这是"要么返回有意义的值，要么返回 None"的风格
        """
        if not requirement.strip():
            print("错误：需求描述不能为空")
            return None

        try:
            suite: TestSuite = self.chain.invoke({
                "requirement": requirement.strip(),
                "test_type": test_type,
            })
            return suite
        except OutputParserException as e:
            print(f"解析失败（LLM 输出不是合法 JSON/Pydantic）: {e}")
            return None
        except Exception as e:
            print(f"调用失败: {e}")
            return None

    def generate_to_json(
        self,
        requirement: str,
        test_type: str = "综合测试",
        indent: int = 2,
    ) -> str | None:
        """生成测试用例并输出为 JSON 字符串"""
        suite = self.generate(requirement, test_type)
        if suite is None:
            return None
        return json.dumps(
            suite.model_dump(),  # model_dump() 是 Pydantic 的序列化方法
            ensure_ascii=False,
            indent=indent,
        )

# ═══════════════════════════════════════════════════════
# 测试场景（按需注释单个场景）
# ═══════════════════════════════════════════════════════

def scenario1_basic() -> None:
    """场景 1：基本调用 —— 登录功能测试用例"""
    generator = TestCaseGenerator()
    print("=" * 60)
    print("场景 1：登录功能测试用例")
    print("=" * 60)

    suite = generator.generate(
        requirement="用户登录功能：支持手机号（1开头的11位数字）+ 密码（不少于8位，含大小写字母和数字）登录。"
                    "连续输错5次锁定账号30分钟。",
        test_type="综合测试",
    )

    if suite:
        print(f"功能: {suite.feature}")
        print(f"摘要: {suite.requirement_summary}")
        print(f"用例数: {len(suite.test_cases)}")
        print(f"覆盖说明: {suite.coverage_notes}")

        priority_count: dict[str, int] = {}
        for tc in suite.test_cases:
            priority_count[tc.priority] = priority_count.get(tc.priority, 0) + 1
        print(f"优先级分布: {priority_count}")

        if suite.test_cases:
            first_tc = suite.test_cases[0]
            print(f"\n示例用例 [{first_tc.id}] {first_tc.title}:")
            print(f"  优先级: {first_tc.priority}")
            print(f"  类型: {first_tc.test_type}")
            print(f"  前置条件: {first_tc.preconditions}")
            print(f"  步骤: {first_tc.steps}")
            print(f"  预期: {first_tc.expected}")
    else:
        print("生成失败")


def scenario2_json_output() -> None:
    """场景 2：生成 JSON 字符串"""
    generator = TestCaseGenerator()
    print("\n" + "=" * 60)
    print("场景 2：输出为 JSON 字符串")
    print("=" * 60)

    json_output = generator.generate_to_json(
        requirement="用户注册功能：输入用户名（字母+数字，4-20位）、邮箱、密码（8位以上）",
        test_type="边界测试",
    )

    if json_output:
        print(f"JSON 长度: {len(json_output)} 字符")
        print(f"前 300 字符:\n{json_output[:300]}...")
    else:
        print("生成失败")


def scenario3_empty_requirement() -> None:
    """场景 3：空需求 —— 预期返回 None"""
    generator = TestCaseGenerator()
    print("\n" + "=" * 60)
    print("场景 3：空需求（预期返回 None）")
    print("=" * 60)

    result = generator.generate(requirement="   ")
    print(f"结果: {result}")  # 应该是 None


if __name__ == "__main__":
    scenario1_basic()
    scenario2_json_output()
    scenario3_empty_requirement()

    print("\n✅ Day 16 核心产出完成！")
    print("   TestCaseGenerator 类 = Prompt Template + LLM + Pydantic Parser 的封装")
    print("   后续可以作为 Tool 注册到 Agent 中（Day 23）")