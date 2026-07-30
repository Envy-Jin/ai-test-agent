"""
src/agent/markdown_reporter.py —— Markdown 测试报告生成器

Day 14 核心模块之二：将 main_pipeline 输出的 JSON 转换为规范的 Markdown 报告。

适合放入 Git 仓库、CI/CD 流程、或直接粘贴到 Wiki/文档系统。
"""

import json
import os
from datetime import datetime
from logger_config import setup_logger

logger = setup_logger("ai_test_agent")

class MarkdownReporter:
    """
    Markdown 测试报告生成器

    使用示例：
        reporter = MarkdownReporter()
        md = reporter.generate(
            "outputs/login_test_cases.json",
            "outputs/report.md"
        )
    """

    def generate(self, json_path: str, output_path: str | None = None) -> str:
        """
        从 JSON 生成 Markdown 报告

        Args:
            json_path: main_pipeline 输出的 JSON 文件路径
            output_path: Markdown 输出路径（None 则只返回文本不保存）

        Returns:
            Markdown 格式的报告文本
        """
        logger.info(f"MarkdownReporter.generate(): {json_path}")

        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        meta = data.get("meta", {})
        summary = data.get("summary", {})
        suites = data.get("suites", [])

        lines = []

        # ========== 标题 ==========
        lines.append("# 测试用例生成报告")
        lines.append("")
        lines.append(f"> 自动生成于 {meta.get('generated_at', 'N/A')}")
        lines.append(f"> 需求文档：`{meta.get('source_file', 'N/A')}`")
        lines.append(f"> 生成耗时：{meta.get('elapsed_seconds', 0)}s")
        lines.append("")

        # ========== 基本信息 ==========
        lines.append("## 基本信息")
        lines.append("")
        lines.append(f"| 项目 | 值 |")
        lines.append(f"|------|-----|")
        lines.append(f"| 需求文档 | {meta.get('source_file', 'N/A')} |")
        lines.append(f"| 生成时间 | {meta.get('generated_at', 'N/A')} |")
        lines.append(f"| 功能点数 | {summary.get('features_count', 0)} |")
        lines.append(f"| 测试用例总数 | {summary.get('total_cases', 0)} |")
        lines.append(f"| 成功生成 | {summary.get('success_count', 0)} |")
        lines.append(f"| 失败 | {summary.get('failed_count', 0)} |")
        lines.append("")

        # ========== 测试统计 ==========
        lines.append("## 测试统计")
        lines.append("")

        # 用例类型分布
        lines.append("### 用例类型分布")
        lines.append("")
        lines.append("| 类型 | 数量 | 占比 |")
        lines.append("|------|------|------|")
        total = summary.get("total_cases", 1)
        type_dist = summary.get("case_type_distribution", {})
        for ct, count in sorted(type_dist.items(), key=lambda x: -x[1]):
            if count > 0:
                pct = count / max(total, 1) * 100
                lines.append(f"| {ct} | {count} | {pct:.1f}% |")
        lines.append("")

        # 优先级分布
        lines.append("### 优先级分布")
        lines.append("")
        lines.append("| 优先级 | 数量 | 占比 |")
        lines.append("|--------|------|------|")
        priority_dist = summary.get("priority_distribution", {})
        for pri in ["P0", "P1", "P2"]:
            count = priority_dist.get(pri, 0)
            pct = count / max(total, 1) * 100
            lines.append(f"| {pri} | {count} | {pct:.1f}% |")
        lines.append("")

        # ========== 各功能点测试用例 ==========
        lines.append("## 各功能点测试用例")
        lines.append("")

        for suite in suites:
            feature = suite.get("feature", {})
            feature_name = feature.get("name", "未命名")
            mode = suite.get("generation_mode", "?")
            test_cases = suite.get("test_cases", [])

            lines.append(f"### {feature_name}")
            lines.append("")
            lines.append(f"- **描述**：{feature.get('description', '无')}")
            lines.append(f"- **子功能**：{'、'.join(feature.get('sub_features', [])) or '无'}")
            lines.append(f"- **约束条件**：{'；'.join(feature.get('constraints', [])) or '无'}")
            lines.append(f"- **用例数**：{len(test_cases)}（生成模式：{mode}）")
            lines.append("")

            # 按优先级排序：P0 → P1 → P2
            priority_order = {"P0": 0, "P1": 1, "P2": 2}
            sorted_cases = sorted(test_cases, key=lambda c: priority_order.get(c.get("priority", "P2"), 2))

            for case in sorted_cases:
                case_id = case.get("id", "?")
                title = case.get("title", "?")
                priority = case.get("priority", "?")
                case_type = case.get("type", "?")

                lines.append(f"#### {case_id} - {title} `[{priority}]` `[{case_type}]`")
                lines.append("")

                # 前置条件
                preconditions = case.get("preconditions", [])
                if preconditions:
                    lines.append("**前置条件**：")
                    for pc in preconditions:
                        lines.append(f"- {pc}")
                    lines.append("")

                # 测试步骤
                steps = case.get("steps", [])
                if steps:
                    lines.append("**测试步骤**：")
                    for i, step in enumerate(steps, 1):
                        lines.append(f"{i}. {step}")
                    lines.append("")

                # 预期结果
                expected = case.get("expected", "")
                if expected:
                    lines.append(f"**预期结果**：{expected}")
                    lines.append("")

                lines.append("---")
                lines.append("")

        report = "\n".join(lines)

        # 保存
        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report)
            logger.info(f"Markdown 报告已保存: {output_path}")

        return report

# ============================================================
# 自检
# ============================================================

def test_markdown_reporter():
    """用 Day 13 的输出测试 Markdown 报告生成"""
    print("=" * 60)
    print("🧪 测试 MarkdownReporter")
    print("=" * 60)

    reporter = MarkdownReporter()

    json_path = "outputs/login_requirement_test_cases.json"
    if not os.path.exists(json_path):
        print(f"⚠️ 测试文件不存在，跳过: {json_path}")
        print("   请先运行: python src/agent/main_pipeline.py docs/requirements/login_requirement.md")
        return

    output_path = "outputs/login_requirement_test_cases.md"
    report = reporter.generate(json_path, output_path)

    print(f"生成文件: {output_path}")
    print(f"文件大小: {os.path.getsize(output_path)} 字节")
    print(f"报告行数: {len(report.splitlines())}")

    # 检查关键内容
    assert "测试用例生成报告" in report, "❌ 缺少标题"
    assert "基本信息" in report, "❌ 缺少基本信息"
    assert "测试统计" in report, "❌ 缺少测试统计"
    assert "各功能点测试用例" in report, "❌ 缺少用例详情"

    print("\n✅ MarkdownReporter 测试通过！")


if __name__ == "__main__":
    test_markdown_reporter()