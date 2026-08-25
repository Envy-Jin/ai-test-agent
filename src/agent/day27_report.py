"""
Day 27 练习 1：测试报告生成模块 —— TestReport Schema + Markdown 渲染

目标：
  1. 用 Pydantic 定义报告结构（TestReport / ReportItem）——报告被 Schema 约束
  2. render_test_report 纯逻辑渲染 Markdown（Day 33 报告模板的预告版）
  3. 分工铁律：统计数字（total/passed/failed/blocked）由代码推导，不让模型算
  4. 零 API 冒烟：构造示例数据渲染，断言数字可推演

用法：
  python day27_report.py                          # 运行示例渲染（零 API）
  python -c "from day27_report import render_test_report, TestReport, ReportItem; print('✅ 导入 ok')"
"""
import sys
from typing import Annotated

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from pydantic import BaseModel, Field


class ReportItem(BaseModel):
    """单条用例执行结果。"""

    id: str = Field(description="用例编号，如 TC001")
    title: str = Field(description="用例标题")
    priority: str = Field(description="优先级：P0/P1/P2")
    case_type: str = Field(description="用例类型：功能/边界/异常/安全")
    steps: list[str] = Field(description="操作步骤")
    expected: str = Field(description="预期结果")
    actual: str = Field(description="实际结果（接口返回摘要，如实填写）")
    status: str = Field(description="执行状态：PASS/FAIL/BLOCKED")


class TestReport(BaseModel):
    """最终测试报告（Agent v4 的 response_format 输出 Schema）。"""

    feature: str = Field(description="被测功能模块名")
    base_url: str | None = Field(default=None, description="被测接口地址（无接口可留空）")
    items: list[ReportItem] = Field(description="全部用例及其执行结果")
    conclusion: str = Field(description="测试结论（如：建议通过 / 需修复后回归）")


# ═══════════════════════════════════════════════════════
# 2. 渲染函数：纯逻辑，统计数字由代码推导
# ═══════════════════════════════════════════════════════

def render_test_report(report: TestReport) -> str:
    """把结构化测试报告渲染成 Markdown 字符串。

    设计要点：
      - total/passed/failed/blocked 用 sum 从 items 推导——算术交给确定性代码
      - 缺陷列表 = status == "FAIL" 的用例（渲染层过滤，模型不用特意整理）
      - 输出可直接落盘为 .md 文件
    """
    items: list[ReportItem] = report.items
    total: int = len(items)
    passed: int = sum(1 for it in items if it.status == "PASS")
    failed: int = sum(1 for it in items if it.status == "FAIL")
    blocked: int = sum(1 for it in items if it.status == "BLOCKED")
    base_url: str = report.base_url or "(无接口)"

    lines: list[str] = [
        "# 测试报告",
        "",
        f"**功能模块**: {report.feature}",
        f"**接口地址**: {base_url}",
        "**测试执行人**: AI Agent",
        "",
        "## 执行摘要",
        "",
        f"- 总用例数: {total}",
        f"- 通过: {passed}",
        f"- 失败: {failed}",
        f"- 阻塞: {blocked}",
        "",
        "## 详细结果",
        "",
        "| ID | 标题 | 优先级 | 类型 | 状态 |",
        "|----|------|--------|------|------|",
    ]
    for it in items:
        lines.append(f"| {it.id} | {it.title} | {it.priority} | {it.case_type} | {it.status} |")

    failed_items: list[ReportItem] = [it for it in items if it.status == "FAIL"]
    lines.append("")
    lines.append("## 缺陷列表")
    lines.append("")
    if failed_items:
        for it in failed_items:
            lines.append(f"- **{it.id}** {it.title}：预期 `{it.expected}`，实际 `{it.actual}`")
    else:
        lines.append("- 无")

    lines.append("")
    lines.append("## 测试结论")
    lines.append("")
    lines.append(report.conclusion)
    return "\n".join(lines) + "\n"


# ═══════════════════════════════════════════════════════
# 实验
# ═══════════════════════════════════════════════════════

def exp1_render_sample() -> None:
    """实验 1：构造示例报告渲染（零 API）——观察 Markdown 结构与统计推导。"""
    print("=" * 60)
    print("实验 1：示例报告渲染（纯逻辑，零 API）")
    report = TestReport(
        feature="用户登录",
        base_url="http://127.0.0.1:8765/api/login",
        items=[
            ReportItem(
                id="TC001",
                title="正确账号密码登录",
                priority="P0",
                case_type="功能",
                steps=["POST /api/login", 'body={"phone":"13800138000","password":"Test123456"}'],
                expected="返回 code=0 与 token",
                actual="code=0，data 含 token=demo-token-123",
                status="PASS",
            ),
            ReportItem(
                id="TC002",
                title="密码少于 8 位",
                priority="P1",
                case_type="边界",
                steps=["POST /api/login", 'body={"phone":"13800138000","password":"123"}'],
                expected="返回 400 与错误码 40002",
                actual="400，code=40002，提示密码长度不能少于8位",
                status="PASS",
            ),
            ReportItem(
                id="TC003",
                title="错误密码登录",
                priority="P0",
                case_type="异常",
                steps=["POST /api/login", 'body={"phone":"13800138000","password":"WrongPass1"}'],
                expected="返回 401 与错误码 40101",
                actual="500，服务端异常（真实环境应为 401）",
                status="FAIL",
            ),
            ReportItem(
                id="TC004",
                title="内网接口可达性",
                priority="P2",
                case_type="异常",
                steps=["POST /api/login", 'body={"phone":"13800138000","password":"Test123456"}'],
                expected="返回 200",
                actual="请求超时（网络不可达）",
                status="BLOCKED",
            ),
        ],
        conclusion="核心流程通过，但 TC003 暴露服务端异常，建议修复后回归测试。",
    )
    md: str = render_test_report(report)
    print(md)
    # 断言推演：4 条用例 = 2 PASS + 1 FAIL + 1 BLOCKED
    assert "总用例数: 4" in md and "通过: 2" in md and "失败: 1" in md and "阻塞: 1" in md
    assert "| TC003 |" in md and "**TC003**" in md          # FAIL 用例进详细结果 + 缺陷列表
    assert "**TC001**" not in md and "**TC002**" not in md  # PASS 用例不进缺陷列表
    assert "| TC004 |" in md and "阻塞: 1" in md             # BLOCKED 只进详细结果
    print("✅ 断言通过：统计推导 + 缺陷过滤逻辑正确")





if __name__ == "__main__":
    exp1_render_sample()
    print("\n💡 要点回顾：")
    print("   报告 = Schema（TestReport 约束结构）+ 渲染（确定性代码算统计）")
    print("   模型只填 items[].status / actual / conclusion，算术永远交给 sum()")
    print("   缺陷列表 = 渲染层过滤 FAIL（模型不用特意整理）")