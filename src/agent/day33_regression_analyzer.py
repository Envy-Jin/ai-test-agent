"""Day 33 练习 2/3：回归分析 —— 变更 + 用例注册表 → RegressionPlan。

设计决策：变更解析（ChangeInfo）与用例注册表归代码（练习 1），
"这些改动影响哪些模块、哪些用例该回归"归模型（语义判断）。
本脚本：
  练习 2（第一部分）：RegressionPlan Schema + 回归 Chain（结构化输出 + 容错）
    + 输出收窄 parse_regression_plan —— exp3 零 API 冒烟；
  练习 3（第二部分，追加在文件末尾）：真实 API 回归分析（exp4）+ 与
    "模块关键词规则基线"对照（exp5，分界线实证）+ main 完成态。

实验（cd src/agent）：
  练习 2：
    python -c "from day33_regression_analyzer import exp3_build_chain_smoke; exp3_build_chain_smoke()"
  练习 3（见练习 3 步骤）：
    python -c "from day33_regression_analyzer import exp4_analyze_real; exp4_analyze_real()"
    python -c "from day33_regression_analyzer import exp5_rules_baseline; exp5_rules_baseline()"
    python day33_regression_analyzer.py     # main 完成态
"""
from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()  # ⚠️ 必须在 import langchain 之前（项目规范）

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402
from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: E402
from pydantic import BaseModel, Field, ValidationError  # noqa: E402

# import 提前放：练习 3 才用到的也在这里（2026-09-02 规范，禁止"补 import"提示）
from day33_change_schema import (  # noqa: E402
    CASE_REGISTRY_PATH,
    CHANGE_DIFF_PATH,
    CaseEntry,
    ChangeInfo,
    load_case_registry,
    parse_git_diff,
    read_change_diff,
)

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

# ── 路径（钉 __file__）──
_AGENT_DIR: str = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT: str = os.path.dirname(os.path.dirname(_AGENT_DIR))
OUT_REGRESSION: str = os.path.join(_PROJECT_ROOT, "outputs", "regression")


# ═══════════════════════════════════════════════════════
# Schema：回归计划（练习 2 —— 学习计划 Day 33 模板的四档分级）
# ═══════════════════════════════════════════════════════
class RegressionCase(BaseModel):
    """回归档位中的一条用例。case_id 必须逐字来自注册表，reason 必填（计划可审计）。"""

    case_id: str
    module: str
    reason: str


class NewCaseSuggestion(BaseModel):
    """变更引入新行为但注册表未覆盖 → 建议新增的用例。"""

    title: str
    module: str
    focus: str


class RegressionPlan(BaseModel):
    """回归测试计划：变更摘要 + 影响模块 + 四档用例。

    档位语义（与"用例自身优先级 P0/P1"是两回事，用语义化字段名避免混淆）：
      must_regression   必回归：直接改动模块、覆盖被删/被改逻辑
      should_regression 建议回归：相邻/依赖模块，中等风险
      can_skip          可跳过：本次影响不到（reason 说明为什么）
      need_add          需新增：新行为无用例覆盖
    """

    change_summary: str
    impacted_modules: list[str]
    must_regression: list[RegressionCase]
    should_regression: list[RegressionCase]
    can_skip: list[RegressionCase]
    need_add: list[NewCaseSuggestion]

    def case_ids(self, level: str) -> list[str]:
        """取某一档全部 case_id（保持计划内顺序、去重）。level ∈ {must, should, skip}。"""
        mapping: dict[str, list[RegressionCase]] = {
            "must": self.must_regression,
            "should": self.should_regression,
            "skip": self.can_skip,
        }
        picked: list[str] = []
        for case in mapping.get(level, []):
            if case.case_id not in picked:
                picked.append(case.case_id)
        return picked


# ═══════════════════════════════════════════════════════
# 模型（用户指定延续）：主 gemini-3.5-flash-lite / 备 gemini-3.1-flash-lite
# ═══════════════════════════════════════════════════════
_primary_llm: ChatGoogleGenerativeAI = ChatGoogleGenerativeAI(
    model="gemini-3.5-flash-lite",
    thinking_level="medium",
)
_backup_llm: ChatGoogleGenerativeAI = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.2,
)

# Day 29 坑 5：先 with_structured_output 再 with_fallbacks（顺序反了丢类型）
_regression_chain = _primary_llm.with_structured_output(RegressionPlan).with_fallbacks(
    [_backup_llm.with_structured_output(RegressionPlan)]
)


# ═══════════════════════════════════════════════════════
# Prompt（练习 2 —— reason 必填写在 prompt 里，硬约束）
# ═══════════════════════════════════════════════════════
REGRESSION_PROMPT: str = """你是资深测试工程师。下面是本次代码变更（git diff 原文 + 解析摘要）与现有测试用例注册表，请输出回归测试计划。

## 变更解析摘要
{change_summary}

## 代码变更（git diff 原文）
{diff_text}

## 现有测试用例注册表（JSON）
{registry_json}

## 输出要求（严格遵守）
1. change_summary：一句话概括本次变更做了什么。
2. impacted_modules：从注册表的 module 取值集合中挑出受影响的模块。
3. must_regression：必回归。直接改动模块里、覆盖被删/被改逻辑的用例。
4. should_regression：建议回归。相邻/依赖模块、或与变更弱相关的用例（中等风险）。
5. can_skip：可跳过。本次变更明确影响不到的用例——reason 必须写"为什么影响不到"。
6. need_add：需新增。变更引入了注册表未覆盖的新行为（如 token 派生规则变化）。

注意：
- case_id 必须逐字来自注册表；reason 必须具体引用变更点，禁止"建议回归"这类空话。
- 注册表 5 条用例要么进 must/should，要么进 can_skip，不许遗漏、不许编造。
- 鉴权/越权相关变更要特别警惕：删除内联校验、token 签发规则变化通常影响越权用例。"""


def _registry_to_text(registry: list[CaseEntry]) -> str:
    return json.dumps([c.model_dump() for c in registry], ensure_ascii=False, indent=2)


def _change_to_summary(change: ChangeInfo) -> str:
    lines: list[str] = []
    for f in change.changed_files:
        lines.append(f"- {f.path}: +{f.add_lines}/-{f.del_lines} lines, hunks={f.hunk_count}, symbols={f.symbols}")
    return f"变更文件 {len(change.changed_files)} 个，总增 {change.total_add} / 总删 {change.total_del} 行：\n" + "\n".join(lines)


def _render_regression_input(diff_text: str, change: ChangeInfo, registry: list[CaseEntry]) -> str:
    """用 str.replace 拼 prompt 输入——注册表 JSON 内含大量花括号，
    用 .format/f-string 会被当成占位符炸掉（Day 32 模板坑的运行时变体）。"""
    return (
        REGRESSION_PROMPT.replace("{change_summary}", _change_to_summary(change))
        .replace("{diff_text}", diff_text[:6000])
        .replace("{registry_json}", _registry_to_text(registry))
    )


# ═══════════════════════════════════════════════════════
# 输出收窄（练习 2 —— Day 29 坑 1 模式：object → isinstance 链）
# ═══════════════════════════════════════════════════════
def parse_regression_plan(raw: object) -> RegressionPlan | None:
    """模型输出收窄：dict | BaseModel → RegressionPlan；不合法返回 None（错误风格二选一）。"""
    if isinstance(raw, RegressionPlan):
        return raw
    if isinstance(raw, BaseModel):
        raw = raw.model_dump()
    if isinstance(raw, dict):
        try:
            return RegressionPlan.model_validate(raw)
        except ValidationError as exc:
            print(f"[parse_regression_plan] 结构校验失败: {exc}")
            return None
    return None


def analyze_regression(
    diff_text: str,
    change: ChangeInfo,
    registry: list[CaseEntry],
) -> RegressionPlan | None:
    """回归分析 Chain（模型语义）：变更 + 注册表 → RegressionPlan。

    invoke 返回 dict | RegressionPlan 联合 → parse_regression_plan 收窄；
    调用失败/结构不合法 → 返回 None（由调用方决定重试或降级到规则基线）。
    """
    messages = [
        SystemMessage(content="你是测试团队的回归分析助手。"),
        HumanMessage(content=_render_regression_input(diff_text, change, registry)),
    ]
    try:
        raw = _regression_chain.invoke(messages)
        return parse_regression_plan(raw)
    except Exception as exc:
        print(f"[analyze_regression] 调用失败: {exc}")
        return None


# ═══════════════════════════════════════════════════════
# 第二部分（练习 3）：规则基线 + 计划渲染 + 真实 API 实验 + main
# ═══════════════════════════════════════════════════════
def baseline_rules(diff_text: str, registry: list[CaseEntry]) -> RegressionPlan:
    """规则基线（确定性，零 API）：扫 diff 行内容里的模块关键词 → 受影响模块。

    规则只会"关键词命中"：受影响模块里 P0 全 must、P1 全 should，其余模块全 skip。
    局限（对照实验的意义）：看不到"删了校验 → 越权风险"这类语义，只能按模块粗圈；
    且 diff 行里若没出现模块名（如只改公共模块）就会漏判。快、可解释，但粗。
    """
    affected: set[str] = set()
    for line in diff_text.splitlines():
        if not (line.startswith("+") or line.startswith("-")):
            continue
        low = line.lower()
        for module in ("login", "orders"):
            if f"/api/{module}" in low or module in low:
                affected.add(module)
    must: list[RegressionCase] = []
    should: list[RegressionCase] = []
    skip: list[RegressionCase] = []
    for case in registry:
        if case.module in affected:
            if case.priority == "P0":
                must.append(RegressionCase(case_id=case.case_id, module=case.module, reason="规则基线：模块命中变更关键词"))
            else:
                should.append(RegressionCase(case_id=case.case_id, module=case.module, reason="规则基线：模块命中变更关键词（P1）"))
        else:
            skip.append(RegressionCase(case_id=case.case_id, module=case.module, reason=f"规则基线：变更未命中 {case.module} 模块"))
    return RegressionPlan(
        change_summary="规则基线：diff 行关键词命中模块",
        impacted_modules=sorted(affected),
        must_regression=must,
        should_regression=should,
        can_skip=skip,
        need_add=[],
    )


def render_plan_markdown(plan: RegressionPlan) -> str:
    """回归计划 → Markdown（给人看 + 落盘）。列表拼接，不碰 f-string 花括号。"""
    lines: list[str] = [
        "# 回归测试计划",
        "",
        f"**变更摘要**: {plan.change_summary}",
        f"**影响模块**: {', '.join(plan.impacted_modules)}",
        "",
        "## 必回归（must_regression）",
    ]
    for case in plan.must_regression:
        lines.append(f"- {case.case_id} [{case.module}] {case.reason}")
    lines.append("")
    lines.append("## 建议回归（should_regression）")
    for case in plan.should_regression:
        lines.append(f"- {case.case_id} [{case.module}] {case.reason}")
    lines.append("")
    lines.append("## 可跳过（can_skip）")
    for case in plan.can_skip:
        lines.append(f"- {case.case_id} [{case.module}] {case.reason}")
    lines.append("")
    lines.append("## 需新增（need_add）")
    for s in plan.need_add:
        lines.append(f"- [{s.module}] {s.title} —— 覆盖点: {s.focus}")
    return "\n".join(lines)

# ═══════════════════════════════════════════════════════
# 实验（练习 2：exp3 零 API 冒烟；练习 3 的 exp4/exp5/main 见第二部分）
# ═══════════════════════════════════════════════════════
def exp3_build_chain_smoke() -> None:
    """零 API 冒烟：Chain 构建可用（模块级）+ 收窄函数喂样例 dict 验证（练习 2）。"""
    print(f"回归 Chain 类型: {type(_regression_chain).__name__}（构建成功，未调用 API）")
    sample_raw: dict[str, object] = {
        "change_summary": "冒烟样例：未调用真实模型",
        "impacted_modules": ["login"],
        "must_regression": [{"case_id": "TC001", "module": "login", "reason": "样例"}],
        "should_regression": [],
        "can_skip": [],
        "need_add": [],
    }
    plan = parse_regression_plan(sample_raw)
    if plan is None:
        print("❌ parse_regression_plan 冒烟失败")
        return
    print(f"✅ 收窄 OK: {type(plan).__name__} | must={plan.case_ids('must')} | 摘要={plan.change_summary}")


def exp4_analyze_real() -> None:
    """真实 API：变更 diff + 注册表 → 模型回归计划 → 落盘 json + md（练习 3）。"""
    diff_text = read_change_diff(CHANGE_DIFF_PATH)
    change = parse_git_diff(diff_text)
    registry = load_case_registry(CASE_REGISTRY_PATH)
    plan = analyze_regression(diff_text, change, registry)
    if plan is None:
        print("❌ 回归分析失败（返回 None），检查网络/模型后重试，或先跑 exp3 确认链可用")
        return
    os.makedirs(OUT_REGRESSION, exist_ok=True)
    plan_json = os.path.join(OUT_REGRESSION, "regression_plan.json")
    plan_md = os.path.join(OUT_REGRESSION, "regression_plan.md")
    with open(plan_json, "w", encoding="utf-8") as f:
        json.dump(plan.model_dump(), f, ensure_ascii=False, indent=2)
    with open(plan_md, "w", encoding="utf-8") as f:
        f.write(render_plan_markdown(plan))
    print(f"✅ 回归计划已落盘: {plan_json}")
    print(f"   影响模块: {plan.impacted_modules}")
    print(f"   must={plan.case_ids('must')} should={plan.case_ids('should')} skip={plan.case_ids('skip')}")
    print(f"   need_add={len(plan.need_add)} 条")


def exp5_rules_baseline() -> None:
    """模型 vs 规则基线对照：读 exp4 落盘的模型计划，与规则基线比档位（零 API）。"""
    plan_json = os.path.join(OUT_REGRESSION, "regression_plan.json")
    if not os.path.exists(plan_json):
        print("⚠️ 未找到 regression_plan.json，请先运行 exp4_analyze_real()")
        return
    with open(plan_json, "r", encoding="utf-8") as f:
        model_plan = RegressionPlan.model_validate(json.load(f))
    diff_text = read_change_diff(CHANGE_DIFF_PATH)
    registry = load_case_registry(CASE_REGISTRY_PATH)
    rule_plan = baseline_rules(diff_text, registry)
    print("─" * 64)
    print("模型计划  must:", model_plan.case_ids("must"), "| should:", model_plan.case_ids("should"), "| skip:", model_plan.case_ids("skip"))
    print("规则基线  must:", rule_plan.case_ids("must"), "| should:", rule_plan.case_ids("should"), "| skip:", rule_plan.case_ids("skip"))
    print("─" * 64)
    print("观察：规则基线只会按模块粗筛（且依赖 diff 行出现模块关键词）；")
    print("模型能指出\"删内联校验→越权风险\"这类因果。规则是零成本基线，模型是语义精修。")



if __name__ == "__main__":
    """完成态（练习 3 末尾才出现）：exp4（真实 API 一次）→ exp5（读落盘对照，零 API）。"""
    # exp3_build_chain_smoke()
    exp4_analyze_real()
    exp5_rules_baseline()
