"""
Day 31 练习 1/2/3：Bug 报告智能分析 —— Bug 报告 → 结构化 BugAnalysis（单条 + 批量 + 质检 + 渲染 + 归档入库）

设计（步骤 1 的 4 个决策落地）：
  A. 主线形态 = Chain（固定单任务）：prompt | llm.with_fallbacks([backup]).with_structured_output(BugAnalysis)
     —— "固定任务 Chain，检索决策 Agent"第三次落地（Day 29 需求 / Day 30 接口 / 今天 Bug）
  B. Schema = 学习计划模板 8 字段 + bug_id/status 增强（Literal 枚举：bug_type 5 类 / severity 4 级 / status 3 态）
  C. 批量 = 确定性分割（split_bug_reports 正则）+ 单条 Chain 复用；聚合统计 sum() 推导
  D. 归档 = 每 Bug 一条文档幂等入库（doc_type="bug" 踩 kb_search 白名单）+ 已修复 Bug 走淘汰通道（day31_bug_archive）

实验：
  exp1_schema_smoke()    零 API：手工构造 BugAnalysis → 质检 → 渲染 → 断言（纯逻辑）
  exp2_split_demo()      零 API：split_bug_reports 分割验证（login_bugs.md / sample.md）
  exp3_analyze_file()    端到端：加载 → 分析 → 质检 → 渲染 → 落盘（真实 API）
  exp4_batch_pipeline()  端到端：分割 → 逐条分析 → 聚合 → 报表 → 落盘 → 入库（真实 API）

用法：
  python -c "from day31_bug_analyzer import exp2_split_demo; exp2_split_demo()"  # 零 API
  python day31_bug_analyzer.py   # 默认跑纯逻辑实验（真实 API 取消注释）
"""

import os
import re
from re import Match
import sys
from dataclasses import dataclass, field
# Day 40 新增：并发批量（asyncio.gather + Semaphore 限流）
import asyncio

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
# Bug 分析 Schema（设计决策 B：学习计划模板 8 字段 + bug_id/status 增强 + Literal 枚举）
# ═══════════════════════════════════════════════════════

BugType = Literal["功能缺陷", "性能问题", "UI问题", "安全漏洞", "兼容性问题"]
Severity = Literal["致命", "严重", "一般", "轻微"]
BugStatus = Literal["待修复", "已修复", "已关闭"]

DOCS_DIR: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs")
BUGS_DIR: str = os.path.join(DOCS_DIR, "bugs")


class BugTestCase(BaseModel):
    """建议补充的测试用例（学习计划模板：title + focus）。"""

    title: str = Field(description="用例标题，如 '验证码过期提示文案校验'")
    focus: str = Field(description="覆盖的测试点，如 '错误码 40101 的提示文案'")


class BugAnalysis(BaseModel):
    """Bug 分析结果：学习计划模板 8 字段 + bug_id/title/status 增强。"""

    bug_id: str = Field(description="Bug 编号，如 BUG-L01（从报告提取；没有则自动编号）")
    title: str = Field(description="Bug 标题，一句话")
    bug_summary: str = Field(description="一句话总结该 Bug 的本质")
    bug_type: BugType = Field(description="缺陷类型：功能缺陷/性能问题/UI问题/安全漏洞/兼容性问题")
    severity: Severity = Field(description="严重度：致命/严重/一般/轻微")
    root_cause_analysis: str = Field(description="根因分析：从现象反推最可能的原因，不臆测修复细节")
    reproduce_steps: list[str] = Field(description="精简可执行的复现步骤（从报告提取，缺步骤按合理推断补齐）")
    test_cases_to_add: list[BugTestCase] = Field(description="需要补充的测试用例（针对该 Bug 的回归加固）")
    regression_scope: list[str] = Field(description="回归测试建议范围（受影响的功能模块/关联接口）")
    prevention: str = Field(description="预防此类 Bug 的建议（工程/流程层面）")
    status: BugStatus = Field(default="待修复", description="Bug 状态：待修复/已修复/已关闭（归档的依据）")


# ═══════════════════════════════════════════════════════
# 批量分割（设计决策 C：确定性代码，零 API 可冒烟）
# ═══════════════════════════════════════════════════════

_BUG_HEADING = re.compile(r"^#{1,3}\s*BUG-\S+", re.MULTILINE)

def split_bug_reports(text: str) -> list[str]:
    """把一份含多个 Bug 的报告按标题拆成多段（确定性逻辑，不靠模型）。

    ⚠️ 教学点：批量处理的分割是【代码】职责——正则按 "## BUG-xxx" 标题行切段，
       模型只负责"每一段的分析"。分割可零 API 冒烟（exp2），不烧 token。
    """
    matches: list[re.Match[str]] = list[Match[str]](_BUG_HEADING.finditer(text))
    if not matches:
        return [text.strip()] if text.strip() else []
    sections: list[str] = []
    for i, m in enumerate[Match[str]](matches):
        start: int = m.start()
        end: int = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        section: str = text[start:end].strip()
        if section:
            sections.append(section)
    return sections


# ═══════════════════════════════════════════════════════
# 分析 Chain（设计决策 A：固定单任务；容错 = with_fallbacks，Day 29 坑 5 顺序）
# ═══════════════════════════════════════════════════════

BUG_ANALYSIS_PROMPT = """你是一名资深软件测试专家，擅长分析 Bug 报告并给出复现建议和测试加固方案。

请按以下要求分析（输出符合给定 Schema）：

【分析要求】
1. bug_id：优先从报告提取（如 BUG-L01）；报告没有编号则用功能简称+序号（如 LOGIN-01）
2. bug_type：从 5 类中选最贴切的（功能缺陷/性能问题/UI问题/安全漏洞/兼容性问题），不确定时选功能缺陷
3. severity：按影响范围分级——致命=数据丢失/资金损失/服务不可用；严重=核心功能不可用；
   一般=部分功能异常有绕行方案；轻微=体验/文案/样式问题
4. root_cause_analysis：从现象反推最可能的根因（如"错误码未区分导致文案透传错误"），
   只写分析与推断，不要臆测具体修复方案
5. reproduce_steps：精简到 3-6 步，每步可执行；报告缺步骤时按合理推断补齐并保持忠实
6. test_cases_to_add：针对该 Bug 的回归加固用例（title + focus），2-4 条，focus 必须写清覆盖哪个测试点
7. regression_scope：受影响的功能模块/关联接口（如"登录接口、会话管理"），1-4 项
8. prevention：工程/流程层面的预防建议（如"补充错误码映射表测试"）
9. status：从报告提取（待修复/已修复/已关闭）；报告未说明则默认待修复

【规范】
- 中文输出；字段值简洁明确，不要写"正常""待优化"这类空话"""


def build_bug_chain():
    """Bug 分析 Chain：prompt | llm（主+备 with_fallbacks）| 结构化输出。

    ⚠️ 返回注解【留空】（Day 26 口诀 25）；顺序【先 with_structured_output 再 with_fallbacks】
       （Day 29 坑 5：反了走 RunnableWithFallbacks.__getattr__ → pyright 推断 Any）。
    """
    llm_primary = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", thinking_level="medium")  # 主
    llm_backup = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0.2)  # 备（确定性优先）
    main = llm_primary.with_structured_output(BugAnalysis)
    backup = llm_backup.with_structured_output(BugAnalysis)
    llm = main.with_fallbacks([backup])
    prompt = ChatPromptTemplate.from_messages([
        ("system", BUG_ANALYSIS_PROMPT),
        ("human", "请分析以下 Bug 报告：\n\n{bug_report}"),
    ])
    return prompt | llm


def analyze_bug_report(text: str) -> BugAnalysis:
    """一行函数入口：Bug 报告文本 → BugAnalysis（Pydantic 实例）。

    ⚠️ 返回注解【明确写 BugAnalysis】：链 invoke 静态推断是 dict|BaseModel 联合 →
       isinstance 收窄 + dict 兜底 model_validate（Day 29 实操验证的写法）。
    """
    chain = build_bug_chain()
    result = chain.invoke({"bug_report": text})
    if isinstance(result, BugAnalysis):
        return result
    if not isinstance(result, dict):
        raise ValueError(f"分析失败：链返回 {type(result).__name__}，期望 dict 或 BugAnalysis")
    return BugAnalysis.model_validate(result)


def analyze_bug_file(path: str) -> BugAnalysis | None:
    """加载 Bug 报告（.md/.txt，复用 Day 29 加载器）→ 分析；加载失败返回 None（fail fast）。"""
    doc = load_document(path)
    if doc is None:
        return None
    print(f"  📄 已加载: {doc.source}（{len(doc.text)} 字符）")
    return analyze_bug_report(doc.text)

# ═══════════════════════════════════════════════════════
# 质检（设计决策 C：纯函数，零 API 可冒烟）
# ═══════════════════════════════════════════════════════

@dataclass
class BugValidationIssue:
    """一条质检问题。level: ERROR(硬伤) / WARNING(建议)。"""

    level: str
    message: str


@dataclass
class BugValidationReport:
    """Bug 分析质检报告。"""

    issues: list[BugValidationIssue] = field(default_factory=list)

    @property
    def has_error(self) -> bool:
        return any(issue.level == "ERROR" for issue in self.issues)


def validate_bug_analysis(analysis: BugAnalysis) -> BugValidationReport:
    """Bug 分析质检（纯函数，零 API）：复现/根因是硬检查，加固/回归/预防是软检查。"""
    report = BugValidationReport()
    if not analysis.reproduce_steps:
        report.issues.append(BugValidationIssue("ERROR", f"{analysis.bug_id} 缺少复现步骤"))
    if not analysis.root_cause_analysis.strip():
        report.issues.append(BugValidationIssue("ERROR", f"{analysis.bug_id} 缺少根因分析"))
    if not analysis.test_cases_to_add:
        report.issues.append(BugValidationIssue("WARNING", f"{analysis.bug_id} 未补充回归用例（建议 2-4 条）"))
    if not analysis.regression_scope:
        report.issues.append(BugValidationIssue("WARNING", f"{analysis.bug_id} 未给出回归范围"))
    if not analysis.prevention.strip():
        report.issues.append(BugValidationIssue("WARNING", f"{analysis.bug_id} 未给出预防建议"))
    return report


# ═══════════════════════════════════════════════════════
# 批量分析 + 聚合统计（设计决策 C：sum() 推导，模型不参与算术）
# ═══════════════════════════════════════════════════════

@dataclass
class BugBatchStats:
    """批量聚合统计（由代码 sum() 推导）。"""

    total: int
    by_severity: dict[str, int] = field(default_factory=dict)
    by_type: dict[str, int] = field(default_factory=dict)
    by_status: dict[str, int] = field(default_factory=dict)

    @property
    def open_count(self) -> int:
        return self.by_status.get("待修复", 0)

    @property
    def open_ratio(self) -> float:
        """待修复占比（0-1，保留 2 位）。"""
        return round(self.open_count / self.total, 2) if self.total else 0.0


def analyze_bug_batch(text: str) -> list[BugAnalysis]:
    """批量：一份报告 → 分割 → 逐段分析（单条 Chain 复用 N 次，互不污染）。

    ⚠️ 教学点：批量 ≠ 一次塞进 prompt；批量 = 代码分割 + 模型逐段分析。
    ⚠️ Day 40：本函数是**串行**版本，保留不动（向后兼容，且同步调用方零改动）。
    要快用并发版 `analyze_bug_batch_async`（见下方，N 倍网络等待 → ≈1 倍）。
    """
    sections: list[str] = split_bug_reports(text)
    return [analyze_bug_report(section) for section in sections]

async def analyze_bug_report_async(text: str) -> BugAnalysis:
    """异步版单条分析（Day 40 新增）：链路走 `ainvoke`。

    为什么单独写一个而不改 `analyze_bug_report`：
      · 同步版是**另一条代码路径**，不是"同一个函数的另一种调法"
        （实测：`RunnableLambda(协程函数)` 只能 ainvoke，反过来抛 TypeError）；
      · 保留同步版 = 现有调用方（day34 编排器的 S9 段、day31 的 exp3/exp4）零改动。
    """
    chain = build_bug_chain()
    result = await chain.ainvoke({"bug_report": text})
    if isinstance(result, BugAnalysis):
        return result
    if not isinstance(result, dict):
        raise ValueError(f"分析失败：链返回 {type(result).__name__}，期望 dict 或 BugAnalysis")
    return BugAnalysis.model_validate(result)


async def analyze_bug_batch_async(
    text: str,
    *,
    max_concurrency: int = 5,
) -> list[BugAnalysis]:
    """Day 40 新增：**并发**批量分析（分割 → asyncio.gather → 保序装配）。

    为什么能快：模型调用是 IO 密集（等网络），N 条串行 = N 次等待；并发 = ≈1 次等待。
    实测（day40_concurrency_lab）：4 段串行 0.69s → 并发 0.16s（4.3x）。

    为什么加 `max_concurrency`（默认 5，不是无限）：
      Gemini 免费额度约 15 RPM（母计划附录）。一次把 N 条全放飞会**撞限流**，
      拿到一堆 429 → 重试 → 反而更慢。用 `Semaphore` 把"同时在飞"关进配额内，
      是"快"与"稳"的折中。这也是 `batch(max_concurrency=...)` 参数存在的理由。

    ⚠️ `asyncio.gather` 保序：返回结果与 `sections` 一一对应（不是"谁先回来谁在前"）。
    ⚠️ 失败隔离：`return_exceptions=True` → 单条失败不炸整批，由调用方决定丢弃/重试。
    """
    sections: list[str] = split_bug_reports(text)
    if not sections:
        return []
    sem = asyncio.Semaphore(max_concurrency)

    async def _guarded(section: str) -> BugAnalysis:
        async with sem:  # 拿到许可才进入（限流点）
            return await analyze_bug_report_async(section)

    results: list[BugAnalysis | BaseException] = await asyncio.gather(
        *(_guarded(s) for s in sections), return_exceptions=True
    )
    ok: list[BugAnalysis] = []
    for idx, item in enumerate(results):
        if isinstance(item, BaseException):
            print(f"  ⚠️ 第 {idx + 1} 段分析失败（已隔离）：{type(item).__name__}: {item}")
            continue
        ok.append(item)
    return ok


def aggregate_stats(analyses: list[BugAnalysis]) -> BugBatchStats:
    """聚合：severity/bug_type/status 分布 + 待修复占比（纯函数，.get 兜底）。"""
    stats = BugBatchStats(total=len(analyses))
    for a in analyses:
        stats.by_severity[a.severity] = stats.by_severity.get(a.severity, 0) + 1
        stats.by_type[a.bug_type] = stats.by_type.get(a.bug_type, 0) + 1
        stats.by_status[a.status] = stats.by_status.get(a.status, 0) + 1
    return stats

# ═══════════════════════════════════════════════════════
# 渲染 + 落盘 + 入库（设计决策 D：确定性代码）
# ═══════════════════════════════════════════════════════

def render_bug_markdown(analysis: BugAnalysis, report: BugValidationReport) -> str:
    """渲染可评审 Markdown：Bug 摘要 + 根因 + 复现 + 加固用例 + 回归范围 + 预防 + 质检（确定性代码）。"""
    lines: list[str] = [
        f"# Bug 分析：{analysis.bug_id} {analysis.title}",
        "",
        f"- **一句话总结**：{analysis.bug_summary}",
        f"- **缺陷类型**：{analysis.bug_type}",
        f"- **严重度**：{analysis.severity}",
        f"- **状态**：{analysis.status}",
        "",
        "## 根因分析",
        analysis.root_cause_analysis,
        "",
        "## 复现步骤",
        "",
    ]
    for i, step in enumerate(analysis.reproduce_steps, start=1):
        lines.append(f"{i}. {step}")
    lines.append("")
    lines.append("## 建议补充的测试用例")
    lines.append("")
    lines.append("| 用例标题 | 覆盖的测试点 |")
    lines.append("|----------|--------------|")
    for case in analysis.test_cases_to_add:
        lines.append(f"| {case.title} | {case.focus} |")
    lines.append("")
    lines.append("## 回归测试建议范围")
    lines.append("")
    for scope in analysis.regression_scope:
        lines.append(f"- {scope}")
    lines.append("")
    lines.append("## 预防建议")
    lines.append(analysis.prevention)
    lines.append("")
    lines.append("## 质检报告")
    if report.issues:
        for issue in report.issues:
            lines.append(f"- **[{issue.level}]** {issue.message}")
    else:
        lines.append("- ✅ 无问题")
    return "\n".join(lines)


def render_batch_report(analyses: list[BugAnalysis], stats: BugBatchStats) -> str:
    """批量聚合报表：总数 + 分布 + 待修复占比 + 每 Bug 一行摘要（确定性代码）。"""
    lines: list[str] = [
        "# Bug 批量分析报告",
        "",
        f"- **Bug 总数**：{stats.total}",
        f"- **待修复**：{stats.open_count}（占比 {stats.open_ratio:.0%}）",
        f"- **按严重度**：{' / '.join(f'{k}={v}' for k, v in sorted(stats.by_severity.items()))}",
        f"- **按类型**：{' / '.join(f'{k}={v}' for k, v in sorted(stats.by_type.items()))}",
        f"- **按状态**：{' / '.join(f'{k}={v}' for k, v in sorted(stats.by_status.items()))}",
        "",
        "## 明细",
        "",
        "| Bug ID | 标题 | 类型 | 严重度 | 状态 | 加固用例数 |",
        "|--------|------|------|--------|------|------------|",
    ]
    for a in analyses:
        lines.append(
            f"| {a.bug_id} | {a.title} | {a.bug_type} | {a.severity} "
            f"| {a.status} | {len(a.test_cases_to_add)} |"
        )
    return "\n".join(lines)


def save_bug_analysis(analysis: BugAnalysis, report: BugValidationReport, name: str) -> tuple[str, str]:
    """落盘：JSON + Markdown 两份产物，返回 (json_path, md_path)。"""
    import json  # noqa: PLC0415

    out_dir: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "outputs")
    os.makedirs(out_dir, exist_ok=True)
    json_path: str = os.path.join(out_dir, f"bug_{name}_analysis.json")
    md_path: str = os.path.join(out_dir, f"bug_{name}_analysis.md")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(analysis.model_dump(), ensure_ascii=False, indent=2))
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_bug_markdown(analysis, report))
    return json_path, md_path


def build_bug_document(analysis: BugAnalysis, source: str) -> Document:
    """把一条 Bug 分析转成知识库文档（每 Bug 一条，metadata 带状态/类型/严重度）。

    ⚠️ chroma metadata 值只收 str/int/float/bool → Literal 值显式 str() 转换（练习 5 坑 2）。
    """
    return Document(
        page_content=render_bug_markdown(analysis, validate_bug_analysis(analysis)),
        metadata={
            "source": source,                    # 幂等 id 的依据（Day 24）
            "bug_id": analysis.bug_id,           # 练习 4 按 Bug 粒度定位
            "doc_type": "bug",                   # 踩 kb_search 白名单（Day 28 教训）
            "status": str(analysis.status),      # 淘汰通道的依据
            "severity": str(analysis.severity),
            "bug_type": str(analysis.bug_type),
            "generated_by": "day31",             # 追溯：哪来的知识
        },
    )


def upsert_bug_analyses(analyses: list[BugAnalysis], source: str, reviewed: bool = False) -> int:
    """Bug 分析产物幂等入库（doc_type="bug"）。

    ⚠️ 数据质量控制（Day 29 延续）：reviewed=False 时提示先人工评审。
    粒度说明：每 Bug 一条 Document；source 仍是报告文件名 → 同源整体替换（Day 24 幂等语义）。
    """
    if not reviewed:
        print("  ⚠️ 数据质量控制：入库前请先人工评审 Bug 分析（reviewed=True 表示已评审）")
    docs: list[Document] = [build_bug_document(a, source) for a in analyses]
    upserter = _get_kb_upserter()
    return upserter.upsert_documents(docs)


def _read_text(path: str) -> str:
    """读文件（utf-8，errors=replace）。"""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


# ═══════════════════════════════════════════════════════
# 实验
# ═══════════════════════════════════════════════════════
def exp1_schema_smoke() -> None:
    """实验：Schema 构造 + 质检 + 聚合（零 API）——断言枚举合法、ERROR 触发、统计推导。"""
    print("=" * 60)
    print("实验：exp1_schema_smoke —— Schema + 质检 + 聚合（零 API）")
    ok = BugAnalysis(
        bug_id="BUG-L01",
        title="错误密码提示文案错误",
        bug_summary="错误密码时提示'系统繁忙'而非'手机号或密码错误'，误导用户",
        bug_type="功能缺陷",
        severity="一般",
        root_cause_analysis="错误码未区分导致文案透传错误：40101 直接走了兜底文案",
        reproduce_steps=["打开登录页", "输入手机号 13800138000", "输入错误密码", "点击登录"],
        test_cases_to_add=[
            BugTestCase(title="错误码 40101 文案校验", focus="断言 40101 返回'手机号或密码错误'"),
            BugTestCase(title="兜底文案仅限 5xx", focus="5xx 才允许展示'系统繁忙'"),
        ],
        regression_scope=["登录接口", "文案配置"],
        prevention="补充错误码→文案映射表测试，覆盖全部已定义错误码",
        status="待修复",
    )
    report = validate_bug_analysis(ok)
    # print(f"report: {report}, has_error: {report.has_error}")
    assert not report.has_error, f"完整样例不应有 ERROR: {report.issues}"
    assert len(ok.test_cases_to_add) == 2
    print(f"  ✅ 完整样例质检通过（{len(report.issues)} 条建议）：{ok.bug_id} [{ok.bug_type}/{ok.severity}/{ok.status}]")

    # 反例：缺复现步骤 → ERROR（硬检查）
    bad = BugAnalysis(
        bug_id="BUG-X01", title="缺复现", bug_summary="s", bug_type="功能缺陷", severity="一般",
        root_cause_analysis="r", reproduce_steps=[], test_cases_to_add=[], regression_scope=[], prevention="",
    )
    bad_report = validate_bug_analysis(bad)
    # print(f"bad_report: {bad_report}, has_error: {bad_report.has_error}")
    assert bad_report.has_error, "缺复现步骤必须 ERROR"
    assert any("复现" in i.message for i in bad_report.issues)
    print(f"  ✅ 反例断言通过：缺复现步骤 → ERROR（{bad_report.issues[0].message}）")

    # 聚合统计：sum() 推导 + .get 兜底
    stats = aggregate_stats([ok, bad])
    print(f"stats: {stats}")
    assert stats.total == 2
    assert stats.by_status.get("待修复", 0) == 2
    assert stats.open_ratio == 1.0
    print(f"  ✅ 聚合统计推导: total={stats.total} 待修复占比={stats.open_ratio} by_type={stats.by_type}")
    print("✅ Schema 冒烟全部通过")

def exp2_split_demo() -> None:
    """实验：批量分割冒烟（零 API）——login_bugs.md 应切出 4 段，sample.md 应切出 3 段。"""
    print("=" * 60)
    print("实验：exp2_split_demo —— 批量分割（零 API）")
    here: str = os.path.dirname(os.path.abspath(__file__))
    # 今日新样本：4 个 Bug
    login_path: str = os.path.join(here, "..", "..", "docs", "bugs", "login_bugs.md")
    with open(login_path, "r", encoding="utf-8", errors="replace") as f:
        login_text: str = f.read()
    login_sections: list[str] = split_bug_reports(login_text)
    assert len(login_sections) == 4, f"login_bugs.md 应切 4 段，实际 {len(login_sections)}"
    print(f"  ✅ login_bugs.md 切出 {len(login_sections)} 段")
    for s in login_sections:
        first: str = s.splitlines()[0]
        print(f"     - {first[:50]}")
    # 知识库种子：3 个 Bug（顺带验证通用性）
    sample_path: str = os.path.join(here, "..", "..", "docs", "knowledge", "bugs", "sample.md")
    with open(sample_path, "r", encoding="utf-8", errors="replace") as f:
        sample_text: str = f.read()
    sample_sections: list[str] = split_bug_reports(sample_text)
    assert len(sample_sections) == 3, f"sample.md 应切 3 段，实际 {len(sample_sections)}"
    print(f"  ✅ sample.md 切出 {len(sample_sections)} 段（知识库种子通用）")
    print("✅ 分割冒烟全部通过")


def exp3_analyze_file(path: str, name: str) -> str | None:
    """端到端：加载 → 分析 → 质检 → 渲染 → 落盘（真实 API，返回 md 路径）。"""
    print("=" * 60)
    print(f"实验：exp3_analyze_file —— Bug 报告分析（{path}）")
    if path is None:
        path = os.path.join(BUGS_DIR, "login_bugs.md")   # 默认值在函数内部解析
    # 单份输入：只切第一段（批量演示走 exp4）
    sections: list[str] = split_bug_reports(_read_text(path))
    if not sections:
        print("❌ 报告为空")
        return None
    analysis = analyze_bug_report(sections[0])
    print(f"  ✅ 分析完成: {analysis.bug_id} [{analysis.bug_type}/{analysis.severity}] {analysis.title}")
    report = validate_bug_analysis(analysis)
    md = render_bug_markdown(analysis, report)  # 渲染函数在练习 3 定义，先跑 exp1/exp2 或按顺序追加
    json_path, md_path = save_bug_analysis(analysis, report, name)
    print(f"  ✅ 已落盘: {md_path}")
    print(md[:900])
    return md_path


def exp4_batch_pipeline(path: str, name: str, reviewed: bool = False) -> str | None:
    """批量完整闭环：分割 → 逐条分析 → 聚合 → 报表 → 落盘 → 评审预览 → 入库（真实 API）。

    返回批量报表 md 路径。reviewed=True 时入库（模拟"评审通过"）。
    """
    print("=" * 60)
    print(f"实验：exp4_batch_pipeline —— Bug 批量分析闭环（{path}）")
    text: str = _read_text(path)
    analyses: list[BugAnalysis] = analyze_bug_batch(text)
    if not analyses:
        print("❌ 分割后无有效段落")
        return None
    stats: BugBatchStats = aggregate_stats(analyses)
    print(f"  ✅ 批量分析完成: {len(analyses)} 个 Bug（待修复 {stats.open_count} 个）")
    # 逐条质检 + 单份落盘（评审对象：每份分析独立可 diff）
    reports: dict[str, BugValidationReport] = {}
    for a in analyses:
        r = validate_bug_analysis(a)
        reports[a.bug_id] = r
        print(f"     {a.bug_id} [{a.severity}/{a.status}] {a.title}"
              f"{'  ⚠️ERROR' if r.has_error else ''}")
    # 报表落盘
    out_dir: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "outputs")
    os.makedirs(out_dir, exist_ok=True)
    md_path: str = os.path.join(out_dir, f"bug_{name}_batch_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_batch_report(analyses, stats))
    print(f"  ✅ 报表落盘: {md_path}")
    # 评审预览（数据质量控制第一步：先看再入库）
    print("  ── 评审预览（前 2 个 Bug 的加固用例）──")
    for a in analyses[:2]:
        for case in a.test_cases_to_add[:2]:
            print(f"     {a.bug_id} 加固用例: {case.title}（{case.focus}）")
    # 入库（有 ERROR 的阻断，评审门硬性要求）
    if any(r.has_error for r in reports.values()):
        print(f"  ⚠️ 质检存在 ERROR，入库已阻断（先修正重跑）")
    else:
        written: int = upsert_bug_analyses(analyses, source=os.path.basename(path), reviewed=reviewed)
        print(f"  ✅ 入库完成（幂等写入 {written} 条片段，doc_type=bug）")
    return md_path


if __name__ == "__main__":
    # exp1_schema_smoke()
    # exp2_split_demo()
    # exp3_analyze_file(os.path.join(BUGS_DIR, "login_bugs.md"), name='login')  # 真实 API，取消注释
    exp4_batch_pipeline(os.path.join(BUGS_DIR, "login_bugs.md"), name='login', reviewed=True)
    print("\n💡 要点回顾：")
    print("   批量 = 分割归代码（正则零 API），分析归模型（单条 Chain 复用）")
    print("   Schema 八段式 = 学习计划模板原样 + bug_id/status 增强（归档的依据）")
    print("   枚举用 Literal 锁死：分类/严重度是语义（模型选），分布是算术（代码算）")
