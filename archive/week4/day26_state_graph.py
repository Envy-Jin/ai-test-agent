"""
Day 26 练习 1：LangGraph 状态机 —— 显式流程的测试工作流

目标：
  1. 理解五件套：State 模式 / 节点 / 边 / 条件边 / 编译执行
  2. 用 StateGraph 把"提取功能点 → 生成用例 → 审查"变成显式流程图
  3. 条件边 + 循环：审查不通过 → 自动回 generate 补用例（LCEL 链做不到）
  4. START/END 常量写法（set_entry_point 已成 legacy，别再用）

用法：
  python day26_state_graph.py                  # 全部实验（纯逻辑零 API + LLM 增强）
  python -c "from day26_state_graph import build_workflow; build_workflow()"  # 零 API 冒烟
"""

import operator
import re
import sys
from typing import Annotated, TypedDict

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()

from langgraph.graph import END, START, StateGraph

# ═══════════════════════════════════════════════════════
# 1. State 模式：共享状态字典（字段 + reducer 定义更新方式）
# ═══════════════════════════════════════════════════════

class TestWorkflowState(TypedDict):
    """测试工作流的共享状态。

    - requirement: 无 reducer → 覆盖式（最后写入者胜）
    - feature:     覆盖式（可空 → 用 xxx | None）
    - test_cases:  Annotated + operator.add → 累积拼接（回炉再生成不丢已生成的）
    - review_notes: 覆盖式（每轮审查覆盖上一轮意见）
    - rounds:      Annotated + operator.add → 数值累积（记录回炉了几轮）
    """
    requirement: str
    feature: str | None
    test_cases: Annotated[list[dict[str, str]], operator.add]
    review_notes: list[str]
    rounds: Annotated[int, operator.add]


# ═══════════════════════════════════════════════════════
# 2. 节点：普通函数，接收完整 state，返回部分更新
# ═══════════════════════════════════════════════════════

def extract_feature(state: TestWorkflowState) -> dict[str, object]:
    """提取功能点：匹配「XX功能」字样（纯逻辑，零 API；LLM 版见实验 2）。"""
    req: str = state["requirement"]
    match = re.search(r"([\u4e00-\u9fa5A-Za-z0-9]{2,8}?)功能", req)
    feature: str = match.group(1) if match else "未知功能"
    print(f"  [extract] 功能点 = {feature}")
    return {"feature": feature}


def generate_cases(state: TestWorkflowState) -> dict[str, object]:
    """生成用例：正常/边界/异常三件套（纯逻辑模板；LLM 版见实验 2）。"""
    feature: str = state.get("feature") or "未知功能"
    cases: list[dict[str, str]] = [
        {"id": "TC001", "title": f"{feature}正常流程", "type": "正向"},
        {"id": "TC002", "title": f"{feature}边界值", "type": "边界"},
        {"id": "TC003", "title": f"{feature}异常输入", "type": "异常"},
    ]
    print(f"  [generate] 生成 {len(cases)} 条用例")
    return {"test_cases": cases, "rounds": 1}


def review_cases(state: TestWorkflowState) -> dict[str, object]:
    """审查用例：质检员只打分、不产用例——数量不足判不合格（演示条件边 + 回炉循环）。

    设计意图：review 只记录审查意见（review_notes），不合格时由路由函数
    把流程送回 generate 重新生产。职责单一，不会出现"审查时偷偷改了数据"的副作用。
    """
    cases: list[dict[str, str]] = state.get("test_cases", [])
    if len(cases) < 5:
        notes: list[str] = [f"不通过：用例数 {len(cases)} < 5，需要补充"]
        print(f"  [review] 不通过（{len(cases)} 条 < 5），回炉！")
        return {"review_notes": notes}
    print(f"  [review] 通过（{len(cases)} 条 >= 5）")
    return {"review_notes": ["通过"]}


# ═══════════════════════════════════════════════════════
# 3. 条件边路由函数：根据当前状态决定下一步去哪
# ═══════════════════════════════════════════════════════

def route_review(state: TestWorkflowState) -> str:
    """审查路由：有不通过意见 → 回 generate 补用例；否则 → END。"""
    notes: list[str] = state.get("review_notes", [])
    if any("不通过" in n for n in notes):
        return "regenerate"
    return "pass"


# ═══════════════════════════════════════════════════════
# 4. 构建图 + 编译
# ═══════════════════════════════════════════════════════

def build_workflow():
    """搭建 StateGraph：extract → generate ⇄ review（条件边回炉）。"""
    builder = StateGraph(TestWorkflowState)
    builder.add_node("extract", extract_feature)
    builder.add_node("generate", generate_cases)
    builder.add_node("review", review_cases)
    builder.add_edge(START, "extract")
    builder.add_edge("extract", "generate")
    builder.add_edge("generate", "review")
    # 条件边：review 之后按路由函数决定去向
    builder.add_conditional_edges(
        "review",
        route_review,
        {"regenerate": "generate", "pass": END},  # 返回值 → 节点名 / END
    )
    return builder.compile()


# ═══════════════════════════════════════════════════════
# 实验
# ═══════════════════════════════════════════════════════

def exp1_pure_logic() -> None:
    """实验 1：纯逻辑节点完整跑通（零 API 冒烟）——观察回炉循环。"""
    print("=" * 60)
    print("实验 1：纯逻辑工作流（零 API，验证图结构 + 条件边回炉）")
    app = build_workflow()
    result: dict[str, object] = app.invoke(
        {"requirement": "用户登录功能，支持手机号和密码登录", "feature": None, "test_cases": [], "review_notes": [], "rounds": 0}
    )
    rounds_obj: object = result.get("rounds", 0)
    rounds: int = rounds_obj if isinstance(rounds_obj, int) else 0
    cases_obj: object = result.get("test_cases", [])
    cases: list[dict[str, str]] = cases_obj if isinstance(cases_obj, list) else []
    print(f"✅ 流程结束：generate 执行 {rounds} 轮，最终 {len(cases)} 条用例")
    for c in cases:
        print(f"   {c['id']} [{c['type']}] {c['title']}")
    # 流程复盘：第一轮 3 条（不通过）→ 回炉 → 第二轮再生成 3 条 → operator.add 累积共 6 条（通过）
    assert rounds == 2 and len(cases) == 6, "预期：第一轮 3 条不通过 → 回炉 → 第二轮再生成 3 条（累积 6 条）→ 通过"
    print("✅ 断言通过：条件边回炉循环工作正常")


def exp2_llm_enhanced() -> None:
    """实验 2：LLM 增强版——用真实模型提取功能点 + 生成用例（真实 API）。

    替换两个节点：extract 用模型结构化输出，generate 用模型生成 JSON 用例。
    """
    print("=" * 60)
    print("实验 2：LLM 增强版（真实 API：gemini-3.1-flash-lite）")

    from langchain.agents.structured_output import ToolStrategy  # noqa: PLC0415
    from langchain_core.messages import HumanMessage  # noqa: PLC0415
    from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: PLC0415
    from pydantic import BaseModel, Field  # noqa: PLC0415

    class FeatureOut(BaseModel):
        """结构化：功能点提取结果。"""
        feature: str = Field(description="被测功能模块名")

    class CaseItem(BaseModel):
        """结构化：单条用例。"""
        id: str = Field(description="用例编号，如 TC001")
        title: str = Field(description="用例标题")
        case_type: str = Field(description="用例类型：正向/边界/异常")

    class CaseList(BaseModel):
        """结构化：一次生成 3 条用例（与纯逻辑版每次 3 条对齐，2 轮完成）。"""
        cases: list[CaseItem]

    llm = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0.2)

    # 节点替换：extract → LLM 结构化输出；generate → LLM 一次生成 3 条
    def extract_feature_llm(state: TestWorkflowState) -> dict[str, object]:
        out = llm.with_structured_output(FeatureOut).invoke(
            f"从以下需求中提取被测功能模块名（2-8 个字）：\n{state['requirement']}"
        )
        if isinstance(out, FeatureOut):
            return {"feature": out.feature}
        return {"feature": "未知功能"}

    def generate_cases_llm(state: TestWorkflowState) -> dict[str, object]:
        feature: str = state.get("feature") or "未知功能"
        out = llm.with_structured_output(CaseList).invoke(
            [HumanMessage(content=f"为「{feature}」生成 3 条测试用例（正向/边界/异常各一条），字段 id/title/case_type")]
        )
        if isinstance(out, CaseList):
            return {"test_cases": [c.model_dump() for c in out.cases], "rounds": 1}
        return {"test_cases": [], "rounds": 1}

    builder = StateGraph(TestWorkflowState)
    builder.add_node("extract", extract_feature_llm)
    builder.add_node("generate", generate_cases_llm)
    builder.add_node("review", review_cases)  # 审查节点复用纯逻辑版
    builder.add_edge(START, "extract")
    builder.add_edge("extract", "generate")
    builder.add_edge("generate", "review")
    builder.add_conditional_edges("review", route_review, {"regenerate": "generate", "pass": END})
    app = builder.compile()

    result: dict[str, object] = app.invoke(
        {"requirement": "支付功能，支持微信和支付宝", "feature": None, "test_cases": [], "review_notes": [], "rounds": 0}
    )
    rounds_obj: object = result.get("rounds", 0)
    rounds: int = rounds_obj if isinstance(rounds_obj, int) else 0
    cases_obj: object = result.get("test_cases", [])
    cases: list[dict[str, str]] = cases_obj if isinstance(cases_obj, list) else []
    print(f"✅ LLM 版流程结束：generate 执行 {rounds} 轮，最终 {len(cases)} 条用例")


if __name__ == "__main__":
    exp1_pure_logic()
    # exp2_llm_enhanced()  # 真实 API，默认注释；想跑就取消注释
    print("\n💡 要点回顾：")
    print("   五件套 = State(TypedDict+reducer) + 节点(函数) + 边 + 条件边 + 编译")
    print("   条件边 + 循环 = LCEL 做不了的回炉重试（审查不过就回去改）")
    print("   reducer：operator.add 拼接累积；覆盖式字段最后写入者胜")
    print("   START/END 常量是标准写法，set_entry_point 已成 legacy")
