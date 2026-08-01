"""
Day 16 练习 5：RunnableParallel + 多模板进阶

并行生成不同类型的测试用例，合并输出。

⚠️ Pyright 注意事项：
  - RunnableParallel 的 invoke 返回 dict[str, Any]，每个 key 对应一个子管道的结果
  - 用 TypedDict 可以给返回的 dict 提供类型提示
  - 但是 TypedDict 在运行时不做验证，需要自己控制

用法：直接运行跑全部实验，或在 main() 中注释掉不想跑的实验函数。
"""

import os
import json
from typing import TypedDict, Any
from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser, PydanticOutputParser
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_core.exceptions import OutputParserException
from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════
# 模块级：Pydantic 模型 + LLM + 辅助函数（所有实验共用）
# ═══════════════════════════════════════════════════════

class SimpleCase(BaseModel):
    """简化版测试用例"""
    id: str = Field(description="用例编号")
    title: str = Field(description="用例标题")
    steps: list[str] = Field(description="测试步骤")
    expected: str = Field(description="预期结果")


class TypedSuite(BaseModel):
    """按类型的测试套件"""
    test_type: str = Field(description="测试类型")
    cases: list[SimpleCase] = Field(description="用例列表")


class ParallelResult(TypedDict, total=False):
    """RunnableParallel 返回的结构"""
    positive: TypedSuite
    boundary: TypedSuite
    negative: TypedSuite


llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.1,
    google_api_key=os.getenv("GEMINI_API_KEY"),
)


def make_typed_chain(test_type_cn: str, instructions: str):
    """构建一个按类型生成的子管道"""
    parser = PydanticOutputParser(pydantic_object=TypedSuite)
    prompt = ChatPromptTemplate.from_messages([
        ("system", f"""你是软件测试工程师。{instructions}
{{format_instructions}}
⚠️ 你的 test_type 字段必须设为 "{test_type_cn}"。"""),
        ("human", "需求：{requirement}"),
    ])
    prompt = prompt.partial(format_instructions=parser.get_format_instructions())
    return prompt | llm | parser


# ═══════════════════════════════════════════════════════
# 实验 1：RunnableParallel 并行三管齐下
# ═══════════════════════════════════════════════════════

def exp1_runnable_parallel(requirement: str) -> dict[str, TypedSuite]:
    """实验 1：RunnableParallel 并行生成正向/边界/异常三类用例"""
    print("=" * 60)
    print("实验 1：RunnableParallel —— 并行生成三类用例")
    print("=" * 60)

    positive_chain = make_typed_chain("正向测试", "请生成正常功能流程的测试用例，3个。")
    boundary_chain = make_typed_chain("边界测试", "请生成边界条件测试用例（空值、超长、特殊字符等），3个。")
    negative_chain = make_typed_chain("异常测试", "请生成异常场景测试用例（非法输入、并发冲突等），3个。")

    parallel_chain = RunnableParallel(
        positive=positive_chain,
        boundary=boundary_chain,
        negative=negative_chain,
    )

    try:
        result: dict[str, TypedSuite] = parallel_chain.invoke({"requirement": requirement})
        print(f"返回类型: {type(result).__name__}")
        print(f"包含 key: {list(result.keys())}")
        total_cases = sum(len(suite.cases) for suite in result.values())
        print(f"总用例数: {total_cases}")
        for suite in result.values():
            print(f"  {suite.test_type}: {len(suite.cases)} 个用例")
        return result
    except OutputParserException as e:
        print(f"解析失败: {e}")
        return {}


# ═══════════════════════════════════════════════════════
# 实验 2：RunnablePassthrough —— 合并输入到输出
# ═══════════════════════════════════════════════════════

def exp2_passthrough(parallel_result: dict[str, TypedSuite], requirement: str) -> None:
    """实验 2：RunnablePassthrough 透传数据，把并行结果综述为一句话"""
    print("\n" + "=" * 60)
    print("实验 2：RunnablePassthrough + 总结 Chain")
    print("=" * 60)

    summary_prompt = ChatPromptTemplate.from_template(
        "根据以下测试用例覆盖情况，用一句话总结测试策略建议：\n"
        "{cases_summary}\n\n需求：{requirement}"
    )
    summary_chain = summary_prompt | llm | StrOutputParser()

    # ⚠️ 关键：RunnableParallel 拼数据 + pipe 给 summary_chain 生成总结
    #    full_chain 分两步：
    #    ① RunnableParallel 把 parallel_result 和 requirement 拼成一个 dict
    #       → {"cases_summary": "...", "requirement": "..."}
    #    ② | summary_chain 把这个 dict 填进 Prompt 模板，LLM 生成一句话总结
    full_chain = (
        RunnableParallel(
            cases_summary=lambda x: json.dumps(
                {k: f"{len(v.cases)}个{v.test_type}用例"
                 for k, v in x["parallel"].items()},
                ensure_ascii=False,
            ),
            requirement=RunnablePassthrough(),
        )
        | summary_chain
    )

    try:
        summary = full_chain.invoke({
            "parallel": parallel_result,
            "requirement": requirement,
        })
        print(f"总结: {summary}")
    except Exception as e:
        print(f"失败: {e}")


# ═══════════════════════════════════════════════════════
# 实验 3：理解链的类型
# ═══════════════════════════════════════════════════════

def exp3_chain_types() -> None:
    """实验 3：观察不同 LCEL 组合的返回类型"""
    print("\n" + "=" * 60)
    print("实验 3：理解 LCEL 链的类型层级")
    print("=" * 60)

    prompt_only = ChatPromptTemplate.from_template("Hello {name}")
    str_chain = prompt_only | llm | StrOutputParser()

    print(f"prompt:                        {type(prompt_only).__name__}")
    print(f"prompt | llm:                  {type(prompt_only | llm).__name__}")
    print(f"prompt | llm | StrOutputParser: {type(str_chain).__name__}")

    r1 = prompt_only.invoke({"name": "World"})
    r2 = (prompt_only | llm).invoke({"name": "World"})
    r3 = str_chain.invoke({"name": "World"})

    print(f"\nprompt.invoke()            → {type(r1).__name__}")
    print(f"(prompt|llm).invoke()      → {type(r2).__name__}")
    print(f"(prompt|llm|parser).invoke() → {type(r3).__name__}")
    print(f"  结果: {r3}")

    print("\n💡 每加一个 | 组件，返回类型就变成那个组件的输出类型")
    print("   这就是 LCEL '类型安全的组合' 的含义")


if __name__ == "__main__":
    requirement = "用户登录功能：手机号+密码，连续错5次锁定30分钟"
    parallel_result = exp1_runnable_parallel(requirement)
    exp2_passthrough(parallel_result, requirement)
    exp3_chain_types()