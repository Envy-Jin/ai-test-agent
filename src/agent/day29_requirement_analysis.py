"""
Day 29 练习 2/3：需求文档解析 → 分级测试用例生成（第 5 周第一个测试专项模块）

设计（步骤 1 的 4 个决策落地）：
  A. 主线形态 = Chain（固定单任务不循环）：prompt | llm | with_structured_output
     —— 昨日答疑"固定任务 Chain，检索决策 Agent"的落地
  B. Schema = 学习计划模板 + summary：feature_name + test_suites[]（suite_type 枚举）
  C. 质检归代码：validate_analysis() 纯函数（id 唯一 / 分级覆盖度 / 统计 sum() 推导）
  D. 入库幂等：upsert_analysis() 复用 Day 24 的 KnowledgeUpserter（doc_type=requirement）

实验：
  exp1_chain_smoke()      零 API 冒烟：with_structured_output 构建不炸（FakeChatModel 不可用，
                          with_structured_output 需要真模型 → 用结构化输出降级写法演示构建）
  exp2_analyze_file()     端到端：加载 .md → 分析 → 质检 → 渲染 → 落盘（真实 API）
  exp3_validate_demo()    纯逻辑：手工构造 RequirementAnalysis → validate → 断言覆盖度（零 API）
  exp4_seed_kb()          入库：分析产物幂等写进知识库（真实 embedding API，步骤 4 跑）

用法：
  python -c "from day29_requirement_analysis import exp3_validate_demo; exp3_validate_demo()"  # 零 API
  python day29_requirement_analysis.py   # 默认跑纯逻辑实验（真实 API 取消注释）
"""

import os
import sys
from dataclasses import dataclass, field

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()  # ⚠️ 必须在 langchain import 之前（Day 25 口诀）

from typing import Literal

from langchain_core.documents import Document
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from day24_case_agent import _get_kb_upserter
from day29_doc_loader import load_document

# ═══════════════════════════════════════════════════════
# 分级 Schema（设计决策 B：学习计划模板 + summary + Literal 枚举）
# ═══════════════════════════════════════════════════════

Priority = Literal["P0", "P1", "P2"]
CaseType = Literal["功能", "边界", "异常", "安全", "兼容"]
SuiteType = Literal["功能测试", "边界测试", "异常测试", "安全测试", "兼容性测试"]

class RequirementTestCase(BaseModel):
    """分级测试用例（学习计划模板字段 + Literal 枚举锁死 priority/type）。"""

    id: str = Field(description="用例编号，如 TC001")
    title: str = Field(description="用例标题，一句话说清测什么")
    priority: Priority = Field(description="优先级：P0=正向功能，P1=边界/异常/安全，P2=兼容")
    type: CaseType = Field(description="用例类型：功能/边界/异常/安全/兼容")
    preconditions: list[str] = Field(default_factory=list, description="前置条件列表")
    steps: list[str] = Field(description="操作步骤列表（至少 1 步）")
    expected_result: str = Field(description="预期结果")
    test_data: dict[str, str] = Field(default_factory=dict, description="测试数据，如 {'phone': '13800138000'}")


class TestSuite(BaseModel):
    """测试套件：一类测试的集合（suite_type 区分五类）。"""

    suite_name: str = Field(description="套件名，如 '正向功能测试'")
    suite_type: SuiteType = Field(description="套件类型：功能/边界/异常/安全/兼容")
    test_cases: list[RequirementTestCase] = Field(description="该套件下的用例列表")


class RequirementAnalysis(BaseModel):
    """需求分析结果：feature_name + summary + test_suites[]（分级）。"""

    feature_name: str = Field(description="被测功能名称，如 '用户登录'")
    summary: str = Field(description="需求摘要：用 1-2 句话概括核心功能与关键约束")
    test_suites: list[TestSuite] = Field(description="测试套件列表（按类型分组）")

# ═══════════════════════════════════════════════════════
# 分析 Chain（设计决策 A：固定单任务不循环；容错 = with_fallbacks）
# ═══════════════════════════════════════════════════════

REQUIREMENT_ANALYSIS_PROMPT = """你是一名资深软件测试工程师，擅长从需求文档中提取测试点并生成分级测试用例。

需求文档：
{requirement}

请按以下要求生成测试用例（输出符合给定 Schema）：

【分级覆盖要求】
1. 正向功能测试（P0）：核心流程的完整正常路径，必选
2. 边界值测试（P1）：输入字段的边界值（如密码刚好 8 位 / 手机号 11 位极限），必选
3. 异常场景测试（P1）：非法输入、超时、重复提交等异常路径，必选
4. 安全性测试（P1）：鉴权、越权、注入、敏感信息等安全点（需求涉及登录/支付/数据时必须包含）
5. 兼容性测试（P2）：不同端/浏览器/分辨率等（需求未提多端可给出 1 条建议性用例或省略）

【用例编写规范】
- id 形如 TC001/TC002 全局递增，不要重复
- priority 严格按上述分级（P0 只给正向功能；边界/异常/安全给 P1；兼容给 P2）
- steps 至少 1 步且可执行；expected_result 写"可验证的预期"，不要写"正常"
- test_data 填关键输入（从需求字段提取，如 phone/password），没有则为空对象
- summary 用 1-2 句话概括需求核心功能与最关键约束"""

def build_analysis_chain():
    """需求分析 Chain：prompt | llm（主+备 with_fallbacks）| 结构化输出。
    ⚠️ 返回注解【留空】（Day 26 口诀 25 的 Chain 版）：让 pyright 推断真实链类型。
    ⚠️ 顺序有讲究（2026-08-26 源码级实测）：
       【先】with_structured_output →【再】with_fallbacks
       —— 反过来的话，with_fallbacks 返回的 RunnableWithFallbacks 走 __getattr__
       代理（langchain_core/runnables/fallbacks.py:592），pyright 推断为 Any，
       链上 invoke 丢类型检查；先结构化输出则类型链完整：
       RunnableWithFallbacks[Any, RequirementAnalysis] → invoke 返回 RequirementAnalysis
    ⚠️ with_fallbacks 是 Chain 的模型级容错（对比 Day 25 Agent 的 ModelFallbackMiddleware）：
       主模型抛错/超时自动切备用模型，一次调用内完成，无额外轮次。
    """
    llm_primary = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", thinking_level="medium")  # 主（Day 27 确认）
    llm_backup = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite")  # 备（不加 thinking_level，避免未知参数）
    # 先各自绑定结构化输出（类型完整），再组合 fallbacks（主失败切备，备也绑同 Schema）
    # ⚠️ 中间变量【不要】写 Runnable 等抽象注解（会窄化 invoke 返回 Any，口诀 25 精神）——
    #    留空让 pyright 推断具体类型：RunnableWithFallbacks[Any, RequirementAnalysis]
    main = llm_primary.with_structured_output(RequirementAnalysis)
    backup = llm_backup.with_structured_output(RequirementAnalysis)
    llm = main.with_fallbacks([backup])
    prompt = ChatPromptTemplate.from_messages([
        ("system", REQUIREMENT_ANALYSIS_PROMPT),
        ("human", "请分析以下需求文档并生成分级测试用例：\n\n{requirement}"),
    ])
    # invoke 返回校验过的 RequirementAnalysis 实例（pyright 从链推断，不用收窄）
    return prompt | llm


def analyze_requirement(text: str) -> RequirementAnalysis:
    """一行函数入口：需求文本 → RequirementAnalysis（Pydantic 实例）。

    ⚠️ 返回注解留空（同口诀 25）。Chain 的 invoke 返回类型由 pyright 从链推断。
    """
    chain = build_analysis_chain()
    result = chain.invoke({"requirement": text})
    if isinstance(result, RequirementAnalysis):
        return result
    if not isinstance(result, dict):
        raise ValueError(
            f"分析失败：链返回 {type(result).__name__}，期望 dict 或 RequirementAnalysis"
        )
    return RequirementAnalysis.model_validate(result)

def analyze_requirement_file(path: str) -> RequirementAnalysis | None:
    """加载文档 → 分析 → 返回 RequirementAnalysis；加载失败返回 None。"""
    doc = load_document(path)
    if doc is None:
        return None
    print(f"  📄 已加载: {doc.source}（{len(doc.text)} 字符）")
    return analyze_requirement(doc.text)


# ═══════════════════════════════════════════════════════
# 质检 + 统计（设计决策 C：确定性代码，零 API 可冒烟）
# ═══════════════════════════════════════════════════════

@dataclass
class ValidationIssue:
    """一条质检问题。level: ERROR(硬伤) / WARNING(建议) / INFO(提示)。"""

    level: str
    message: str


@dataclass
class ValidationReport:
    """质检报告：issues + 统计（统计永远 sum() 推导，不让模型算）。"""

    issues: list[ValidationIssue] = field(default_factory=list)
    total_cases: int = 0
    by_priority: dict[str, int] = field(default_factory=dict)
    by_type: dict[str, int] = field(default_factory=dict)

    @property
    def has_error(self) -> bool:
        return any(issue.level == "ERROR" for issue in self.issues)

def validate_analysis(analysis: RequirementAnalysis) -> ValidationReport:
    """分级用例质检：结构 + 覆盖度 + 统计（纯函数，零 API）。

    检查项：
      ① id 唯一性（跨 suite 全局唯一）→ 重复 = ERROR
      ② 每个用例至少 1 步 steps → 空 = ERROR
      ③ 分级覆盖度：P0 功能类（ERROR 缺）/ P1 边界+异常（WARNING 缺）/ P2 兼容（INFO 缺）
      ④ 统计：total / by_priority / by_type —— sum() 推导
    """
    report = ValidationReport()
    seen_ids: set[str] = set()
    case_types: set[str] = set()
    priorities: set[str] = set()
    total: int = 0
    by_priority: dict[str, int] = {"P0": 0, "P1": 0, "P2": 0}
    by_type: dict[str, int] = {}

    for suite in analysis.test_suites:
        for case in suite.test_cases:
            total += 1
            by_priority[case.priority] = by_priority.get(case.priority, 0) + 1
            by_type[case.type] = by_type.get(case.type, 0) + 1
            priorities.add(case.priority)
            case_types.add(case.type)
            if case.id in seen_ids:
                report.issues.append(ValidationIssue("ERROR", f"用例 id 重复: {case.id}"))
            seen_ids.add(case.id)
            if not case.steps:
                report.issues.append(ValidationIssue("ERROR", f"{case.id} 缺少操作步骤"))

    # 分级覆盖度（设计决策 C 的软检查）
    if not ({"P0"} & priorities and "功能" in case_types):
        report.issues.append(ValidationIssue("ERROR", "缺少 P0 正向功能用例（分级第一档必须有）"))
    if "边界" not in case_types:
        report.issues.append(ValidationIssue("WARNING", "缺少边界值用例（P1 建议）"))
    if "异常" not in case_types:
        report.issues.append(ValidationIssue("WARNING", "缺少异常场景用例（P1 建议）"))
    if "安全" not in case_types:
        report.issues.append(ValidationIssue("INFO", "缺少安全性用例（涉及登录/支付/数据时必须补 P1）"))

    report.total_cases = total
    report.by_priority = by_priority
    report.by_type = by_type
    return report


def render_analysis_markdown(analysis: RequirementAnalysis, report: ValidationReport) -> str:
    """渲染可评审 Markdown：摘要 + 分套件表格 + 质检报告 + 统计（确定性代码）。"""
    lines: list[str] = [
        f"# 需求分析：{analysis.feature_name}",
        "",
        "## 需求摘要",
        analysis.summary,
        "",
        f"## 测试套件（共 {len(analysis.test_suites)} 个，{report.total_cases} 条用例）",
        "",
    ]
    for suite in analysis.test_suites:
        lines.append(f"### {suite.suite_name}（{suite.suite_type}，{len(suite.test_cases)} 条）")
        lines.append("")
        lines.append("| ID | 标题 | 优先级 | 类型 | 前置条件 | 步骤 | 预期结果 | 测试数据 |")
        lines.append("|----|------|--------|------|----------|------|----------|----------|")
        for case in suite.test_cases:
            lines.append(
                f"| {case.id} | {case.title} | {case.priority} | {case.type} "
                f"| {'；'.join(case.preconditions) or '-'} | {'；'.join(case.steps)} "
                f"| {case.expected_result} | {_fmt_test_data(case.test_data)} |"
            )
        lines.append("")
    lines.append("## 质检报告")
    if report.issues:
        for issue in report.issues:
            lines.append(f"- **[{issue.level}]** {issue.message}")
    else:
        lines.append("- ✅ 无问题")
    lines.append("")
    lines.append("## 统计（由代码 sum() 推导）")
    lines.append(f"- 总用例数: {report.total_cases}")
    lines.append("- 按优先级: " + " / ".join(f"{k}={v}" for k, v in sorted(report.by_priority.items())))
    lines.append("- 按类型: " + " / ".join(f"{k}={v}" for k, v in sorted(report.by_type.items())))
    return "\n".join(lines)


def _fmt_test_data(data: dict[str, str]) -> str:
    """测试数据字典 → 紧凑字符串（空字典显示 '-'）。"""
    if not data:
        return "-"
    return ", ".join(f"{k}={v}" for k, v in data.items())


def save_analysis(analysis: RequirementAnalysis, report: ValidationReport, name: str) -> tuple[str, str]:
    """落盘：JSON + Markdown 两份产物，返回 (json_path, md_path)。"""
    import json  # noqa: PLC0415

    out_dir: str = os.path.join(os.path.dirname(__file__), "..", "..", "outputs")
    os.makedirs(out_dir, exist_ok=True)
    json_path: str = os.path.join(out_dir, f"requirement_{name}_analysis.json")
    md_path: str = os.path.join(out_dir, f"requirement_{name}_analysis.md")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(analysis.model_dump(), ensure_ascii=False, indent=2))
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_analysis_markdown(analysis, report))
    return json_path, md_path


def upsert_analysis(analysis: RequirementAnalysis, source: str, reviewed: bool = False) -> int:
    """分析产物幂等入库（设计决策 D：doc_type 踩 kb_search 白名单）。

    ⚠️ 教学点（数据质量控制）：知识库只放评审过的用例。reviewed=False 时
       文档会提示"入库前请人工评审"——真实工作流这里是 CI 门禁或人工确认。
    """
    if not reviewed:
        print("  ⚠️ 数据质量控制：入库前请先人工评审用例（reviewed=True 表示已评审）")
    upserter = _get_kb_upserter()
    docs: list[Document] = [
        Document(
            page_content=render_analysis_markdown(analysis, validate_analysis(analysis)),
            metadata={
                "source": source,                    # 幂等 id 的依据（Day 24）
                "doc_type": "requirement",           # 必须踩 kb_search 白名单（Day 28 教训）
                "feature": analysis.feature_name,    # feature 维度过滤
                "generated_by": "day29",             # 追溯：哪来的知识
            },
        )
    ]
    return upserter.upsert_documents(docs)

# ═══════════════════════════════════════════════════════
# 实验
# ═══════════════════════════════════════════════════════

def exp2_analyze_file(path: str, name: str) -> str | None:
    """端到端：加载 → 分析 → 质检 → 渲染 → 落盘（真实 API）。

    返回 Markdown 产物路径（加载失败返回 None）。
    """
    print("=" * 60)
    print(f"实验：exp2_analyze_file —— 需求文档解析（{path}）")
    analysis: RequirementAnalysis | None = analyze_requirement_file(path)
    if analysis is None:
        print("❌ 文档加载失败")
        return None
    print(f"  ✅ 分析完成: feature={analysis.feature_name!r} 摘要={analysis.summary[:40]}...")
    report: ValidationReport = validate_analysis(analysis)
    md: str = render_analysis_markdown(analysis, report)
    print(f"  ✅ 质检: {len(report.issues)} 条问题，总用例 {report.total_cases} 条")
    for issue in report.issues:
        print(f"     [{issue.level}] {issue.message}")
    json_path, md_path = save_analysis(analysis, report, name)
    print(f"  ✅ 已落盘: {md_path}")
    print(md[:1200])
    return md_path


def exp3_validate_demo() -> None:
    """实验：质检纯逻辑冒烟（零 API）——构造 5 类用例断言覆盖度 + 统计推导。"""
    print("=" * 60)
    print("实验：exp3_validate_demo —— 质检纯逻辑（零 API）")
    ok = RequirementAnalysis(
        feature_name="用户登录",
        summary="手机号/邮箱登录，密码不少于8位，错误超5次锁30分钟",
        test_suites=[
            TestSuite(suite_name="正向功能测试", suite_type="功能测试", test_cases=[
                RequirementTestCase(id="TC001", title="正确账号密码登录", priority="P0", type="功能",
                                    steps=["输入手机号", "输入密码", "点击登录"],
                                    expected_result="登录成功返回 token", test_data={"phone": "13800138000"}),
            ]),
            TestSuite(suite_name="边界值测试", suite_type="边界测试", test_cases=[
                RequirementTestCase(id="TC002", title="密码刚好8位", priority="P1", type="边界",
                                    steps=["输入8位密码", "登录"], expected_result="校验通过进入下一步",
                                    test_data={"password": "abc12345"}),
            ]),
            TestSuite(suite_name="异常场景测试", suite_type="异常测试", test_cases=[
                RequirementTestCase(id="TC003", title="密码错误5次锁定", priority="P1", type="异常",
                                    steps=["连续输错5次", "第6次输入正确密码"],
                                    expected_result="账号锁定30分钟，提示稍后再试"),
            ]),
            TestSuite(suite_name="安全测试", suite_type="安全测试", test_cases=[
                RequirementTestCase(id="TC004", title="SQL注入尝试", priority="P1", type="安全",
                                    steps=["用户名输入' or '1'='1", "登录"],
                                    expected_result="返回参数校验错误，不泄露数据"),
            ]),
            TestSuite(suite_name="兼容性测试", suite_type="兼容性测试", test_cases=[
                RequirementTestCase(id="TC005", title="移动端浏览器登录", priority="P2", type="兼容",
                                    steps=["用手机浏览器打开登录页", "正常登录"],
                                    expected_result="页面布局与功能正常"),
            ]),
        ],
    )
    report: ValidationReport = validate_analysis(ok)
    assert not report.has_error, f"完整样例不应有 ERROR: {report.issues}"
    assert report.total_cases == 5
    assert report.by_priority == {"P0": 1, "P1": 3, "P2": 1}, "统计必须由代码推导"
    print(render_analysis_markdown(ok, report)[:900])

    # 反例：缺 P0 功能 → 必须报 ERROR（分级第一档的硬检查）
    bad = RequirementAnalysis(
        feature_name="残缺需求", summary="只有边界用例",
        test_suites=[TestSuite(suite_name="边界值测试", suite_type="边界测试", test_cases=[
            RequirementTestCase(id="TC001", title="边界用例", priority="P1", type="边界",
                                steps=["输入"], expected_result="通过"),
        ])],
    )
    bad_report: ValidationReport = validate_analysis(bad)
    assert bad_report.has_error, "缺 P0 必须 ERROR"
    assert any("P0" in issue.message for issue in bad_report.issues)
    print(f"  ✅ 反例断言通过：缺 P0 功能类 → ERROR（{bad_report.issues[0].message}）")
    print("✅ 质检冒烟全部通过")

def exp_full_pipeline(path: str, name: str, reviewed: bool = False) -> str | None:
    """完整闭环：加载 → 分析 → 质检 → 落盘 → 评审预览 → 入库（真实 API）。

    返回 Markdown 产物路径。reviewed=True 时产物入库（模拟"评审通过"）。
    """
    print("=" * 60)
    print(f"实验：exp_full_pipeline —— 需求解析完整闭环（{path}）")
    analysis: RequirementAnalysis | None = analyze_requirement_file(path)
    if analysis is None:
        return None
    report: ValidationReport = validate_analysis(analysis)
    json_path, md_path = save_analysis(analysis, report, name)
    print(f"  ✅ 产物落盘: {json_path}")
    print(f"               {md_path}")
    # 评审预览（数据质量控制的第一步：先看再入库）
    print("  ── 评审预览（前 3 条用例）──")
    for suite in analysis.test_suites[:3]:
        for case in suite.test_cases[:3]:
            print(f"     {case.id} [{case.priority}/{case.type}] {case.title}")
    if report.has_error:
        print(f"  ⚠️ 质检存在 ERROR，建议修正后重跑（issues={len(report.issues)}）")
    else:
        written: int = upsert_analysis(analysis, source=os.path.basename(path), reviewed=reviewed)
        print(f"  ✅ 入库完成（幂等写入 {written} 条片段，doc_type=requirement）")
    return md_path
