"""
Day 24 练习 1+2：Agent 结构化输出 —— ToolStrategy vs ProviderStrategy

目标：
  1. 理解 response_format 两种策略的机制差异（ToolStrategy = 人工 tool calling；
     ProviderStrategy = 模型原生 json_schema 模式）
  2. result["structured_response"] 直接拿到 Pydantic 实例 / dict，不再需要 json_extractor
  3. 对比 Day 23 的"小模型 JSON 三件套"：结构化输出把"事后清洗"变成"生成时约束"

⚠️ Pyright 注意事项：
  - result["structured_response"] 取值是 object → 必须 isinstance 收窄后才能用
  - 构建函数与实验函数分离：构建可被无 API 冒烟测试（FakeChatModel）验证

用法：
  python day24_structured_output.py        # 全部实验（需要真实 API）
  python -c "from day24_structured_output import build_tool_strategy_agent; build_tool_strategy_agent()"  # 只构建（零 API）
"""

import os
import sys
from typing import Literal

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()

from langchain.agents import create_agent
from langchain.agents.structured_output import ProviderStrategy, ToolStrategy
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

# ═══════════════════════════════════════════════════════
# 输出 Schema（Pydantic 模型 = 结构化输出的"模具"）
# ═══════════════════════════════════════════════════════

class ContactInfo(BaseModel):
    """联系人信息（练习 1 的 Schema）。"""
    name: str = Field(description="联系人姓名")
    email: str = Field(description="联系邮箱")
    phone: str = Field(description="手机号")


class BugReport(BaseModel):
    """Bug 报告（练习 2 的 Schema，贴近测试场景）。"""
    bug_summary: str = Field(description="一句话总结 Bug")
    severity: Literal["P0", "P1", "P2", "P3"] = Field(description="严重级别")
    reproduce_steps: list[str] = Field(description="复现步骤，按顺序列出")

class BugReportList(BaseModel):
    bugs: list[BugReport] = Field(description="Bug 报告列表")

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.2,
)

# ═══════════════════════════════════════════════════════
# 构建函数（可无 API 冒烟验证：create_agent 构建期不调 API）
# ═══════════════════════════════════════════════════════

def build_tool_strategy_agent():
    """练习 1：ToolStrategy —— 人工 tool calling，任何支持工具调用的模型都行。"""
    return create_agent(
        model=llm,
        system_prompt="你是一个信息提取助手，从用户的文本中提取联系人信息。",
        response_format=ToolStrategy(ContactInfo),
    )


def build_provider_strategy_agent():
    """练习 2：ProviderStrategy —— Gemini 原生 json_schema 模式，更可靠。"""
    return create_agent(
        model=llm,
        system_prompt="你是一个 Bug 分析助手，把用户的 Bug 描述逐一整理成结构化字段，并返回一个 Bug 报告列表。",
        response_format=ProviderStrategy(BugReportList),
    )


def build_auto_agent():
    """进阶：直接传 Schema 类型，langchain>=1.1 自动选择策略。"""
    return create_agent(
        model=llm,
        system_prompt="你是一个信息提取助手。",
        response_format=ContactInfo,
    )

# ═══════════════════════════════════════════════════════
# 辅助：从 invoke 结果提取结构化响应（Pyright 收窄教学点）
# ═══════════════════════════════════════════════════════

def extract_contact(result: dict[str, object]) -> ContactInfo | None:
    """从 agent.invoke 结果提取 ContactInfo（dict 取值是 object，必须 isinstance 收窄）。"""
    raw: object = result.get("structured_response")
    if isinstance(raw, ContactInfo):
        return raw
    return None


def extract_bug(result: dict[str, object]) -> BugReport | None:
    """从 agent.invoke 结果提取 BugReport。"""
    raw: object = result.get("structured_response")
    if isinstance(raw, BugReport):
        return raw
    return None

def extract_bug_list(result: dict[str, object]) -> BugReportList | None:
    """从 agent.invoke 结果提取 BugReport。"""
    raw: object = result.get("structured_response")
    if isinstance(raw, BugReportList):
        return raw
    return None

# ═══════════════════════════════════════════════════════
# 实验（真实 API）
# ═══════════════════════════════════════════════════════

def exp1_tool_strategy() -> None:
    """实验 1：ToolStrategy 提取联系人信息。"""
    print("=" * 60)
    print("实验 1：ToolStrategy（人工 tool calling）")
    agent = build_tool_strategy_agent()
    result: dict[str, object] = agent.invoke(
        {"messages": [{"role": "user", "content": "张三的联系方式：zhangsan@example.com，电话 13800138000"}]}
    )
    contact: ContactInfo | None = extract_contact(result)
    if contact is None:
        print("❌ 未拿到结构化响应，打印原始消息兜底查看：")
        print(result.get("messages"))
        return
    print(f"✅ 结构化响应（Pydantic 实例）: {contact}")
    # print(f"   name={contact.name}, email={contact.email}, phone={contact.phone}")
    print(f"   {contact.model_dump_json(indent=2)}")
    # 对比：直接可用的数据 vs 之前要 json.loads 的字符串
    print(f"   type={type(contact).__name__} —— 无需 json.loads，直接用属性")


def exp2_provider_strategy() -> None:
    """实验 2：ProviderStrategy（Gemini 原生 json_schema 模式）。"""
    print("=" * 60)
    print("实验 2：ProviderStrategy（模型原生结构化输出）")
    agent = build_provider_strategy_agent()
    result: dict[str, object] = agent.invoke(
        {"messages": [{"role": "user", "content": "订单完成之后，购物车中商品未被清空"}, {"role": "user", "content": "登录完成之后，在首页没有登出选项"}, {"role": "user", "content": "登录页面点击登录按钮后白屏，刷新后恢复，概率约 30%，影响所有用户"},{"role": "user", "content": "填写收件人信息时，联系人写成了练习人"}]}
    )

    # bug: BugReport | None = extract_bug(result)
    bug_list: BugReportList | None = extract_bug_list(result)
    if bug_list is None:
        print("❌ 未拿到结构化响应，打印原始消息兜底查看：")
        print(result.get("messages"))
        return
    print(f"✅ 结构化响应: {bug_list}")
    # for bug in bug_list.bugs:
    #     print(f"   bug_summary={bug.bug_summary}")
    #     print(f"   severity={bug.severity}")
    #     print(f"   reproduce_steps={bug.reproduce_steps}")
    for i, bug in enumerate(bug_list.bugs, 1):
        print(f"[{i}] {bug.model_dump_json(indent=2)}")

def exp3_auto_strategy() -> None:
    """实验 3：直接传 Schema 类型（自动选择策略）。"""
    print("=" * 60)
    print("实验 3：直接传 Schema（自动选择）")
    agent = build_auto_agent()
    result: dict[str, object] = agent.invoke(
        {"messages": [{"role": "user", "content": "李四：lisi@example.com，13900139000"}]}
    )
    contact: ContactInfo | None = extract_contact(result)
    if contact is None:
        print("❌ 未拿到结构化响应")
        return
    print(f"✅ 自动策略也返回了 ContactInfo: {contact}")



if __name__ == "__main__":
    exp1_tool_strategy()
    # exp2_provider_strategy()
    # exp3_auto_strategy()
    print("\n💡 要点回顾：")
    print("   structured_response = Pydantic 实例，直接用属性，不再 json.loads")
    print("   ToolStrategy = 人工 tool calling（任何模型）；ProviderStrategy = 原生（更稳）")
    print("   直接传 Schema 类 → 自动选择；flash-lite 建议显式 ToolStrategy 求稳")