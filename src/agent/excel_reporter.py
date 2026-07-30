"""
src/agent/excel_reporter.py —— Excel 测试用例报告生成器

Day 14 核心模块之一：将 main_pipeline 输出的 JSON 转换为专业的 Excel 报告。

功能：
1. 每个功能点一个独立 Sheet（带格式化）
2. 「总览」Sheet（摘要 + 类型/优先级统计）
3. 优先级颜色标记（P0 红色、P1 橙色）
4. 用例类型行背景色（正向绿色、异常浅红）
5. 表头蓝色背景白色文字
6. 自适应列宽 + 边框

使用 openpyxl 实现，不依赖 Excel 软件。
"""

import json
import os
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import (
    Font, PatternFill, Alignment, Border, Side, numbers
)
from openpyxl.utils import get_column_letter
from logger_config import setup_logger

logger = setup_logger("ai_test_agent")


# ============================================================
# 样式常量
# ============================================================

# 表头样式
HEADER_FONT = Font(name="Calibri", bold=True, color="FFFFFF", size=11)
HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
HEADER_ALIGNMENT = Alignment(horizontal="center", vertical="center", wrap_text=True)

# 数据行样式
DATA_FONT = Font(name="Calibri", size=10)
DATA_ALIGNMENT = Alignment(vertical="top", wrap_text=True)
CENTER_ALIGNMENT = Alignment(horizontal="center", vertical="top", wrap_text=True)

# 优先级颜色
PRIORITY_FONTS = {
    "P0": Font(name="Calibri", size=10, color="FF0000", bold=True),  # 红色加粗
    "P1": Font(name="Calibri", size=10, color="ED7D31"),              # 橙色
    "P2": Font(name="Calibri", size=10, color="4472C4"),              # 蓝色
}

# 用例类型行背景色
TYPE_FILLS = {
    "正向": PatternFill(start_color="E2EFDA", end_color="E2EFDA", fill_type="solid"),   # 浅绿
    "边界": PatternFill(start_color="FFF2CC", end_color="FFF2CC", fill_type="solid"),    # 浅黄
    "异常": PatternFill(start_color="FCE4D6", end_color="FCE4D6", fill_type="solid"),    # 浅红
    "安全": PatternFill(start_color="D9E2F3", end_color="D9E2F3", fill_type="solid"),    # 浅蓝
    "性能": PatternFill(start_color="E4DFEC", end_color="E4DFEC", fill_type="solid"),    # 浅紫
}

# 边框（细线）
THIN_BORDER = Border(
    left=Side(style="thin", color="B4C6E7"),
    right=Side(style="thin", color="B4C6E7"),
    top=Side(style="thin", color="B4C6E7"),
    bottom=Side(style="thin", color="B4C6E7"),
)

# 总览 Sheet 的标题样式
TITLE_FONT = Font(name="Calibri", bold=True, size=14, color="1F4E79")
SUBTITLE_FONT = Font(name="Calibri", bold=True, size=12, color="2E75B6")

# 用例 Sheet 列定义
CASE_COLUMNS = [
    ("ID", 12),
    ("类型", 10),
    ("优先级", 10),
    ("标题", 35),
    ("前置条件", 25),
    ("测试步骤", 50),
    ("预期结果", 40),
]


# ============================================================
# ExcelReporter
# ============================================================

class ExcelReporter:
    """
    Excel 测试用例报告生成器

    职责：
    1. 读取 main_pipeline 输出的 JSON
    2. 每个功能点生成一个独立 Sheet（带格式）
    3. 生成「总览」Sheet（摘要 + 统计）
    4. 保存为 .xlsx 文件

    使用示例：
        reporter = ExcelReporter()
        reporter.generate("outputs/login_test_cases.json", "outputs/report.xlsx")
    """

    def generate(self, json_path: str, output_path: str) -> str:
        """
        从 JSON 生成 Excel 报告

        Args:
            json_path: main_pipeline 输出的 JSON 文件路径
            output_path: Excel 输出路径（.xlsx）

        Returns:
            生成的 Excel 文件路径
        """
        logger.info(f"ExcelReporter.generate(): {json_path} → {output_path}")

        # 1. 读取 JSON
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 2. 创建工作簿
        self.wb = Workbook()
        # 删除默认 Sheet（后面自己建）
        default = self.wb.active
        if default is not None:
            self.wb.remove(default)

        # 3. 生成「总览」Sheet
        self._create_overview_sheet(data)

        # 4. 为每个功能点生成独立 Sheet
        suites = data.get("suites", [])
        for suite in suites:
            self._create_feature_sheet(suite)

        # 5. 保存
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        self.wb.save(output_path)
        logger.info(f"Excel 报告已保存: {output_path}")

        return output_path

    # ============================================================
    # 总览 Sheet
    # ============================================================

    def _create_overview_sheet(self, data: dict):
        """创建「总览」Sheet"""
        ws = self.wb.create_sheet("总览", 0)  # 放在第一个

        meta = data.get("meta", {})
        summary = data.get("summary", {})
        suites = data.get("suites", [])

        # ---- 标题 ----
        ws.merge_cells("A1:F1")
        cell = ws["A1"]
        cell.value = "测试用例生成报告"
        cell.font = TITLE_FONT
        cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 35

        # ---- 基本信息 ----
        row = 3
        info_data = [
            ("需求文档", meta.get("source_file", "N/A")),
            ("生成时间", meta.get("generated_at", "N/A")),
            ("总耗时", f"{meta.get('elapsed_seconds', 0)}s"),
            ("功能点数", summary.get("features_count", 0)),
            ("测试用例总数", summary.get("total_cases", 0)),
        ]
        ws.merge_cells(f"A{row}:F{row}")
        ws[f"A{row}"].value = "📋 基本信息"
        ws[f"A{row}"].font = SUBTITLE_FONT
        row += 1

        for label, value in info_data:
            ws.cell(row=row, column=1, value=label).font = Font(name="Calibri", bold=True, size=10)
            ws.cell(row=row, column=2, value=value).font = DATA_FONT
            row += 1

        # ---- 用例类型分布 ----
        row += 1
        ws.merge_cells(f"A{row}:F{row}")
        ws[f"A{row}"].value = "📊 用例类型分布"
        ws[f"A{row}"].font = SUBTITLE_FONT
        row += 1

        type_dist = summary.get("case_type_distribution", {})
        ws.cell(row=row, column=1, value="类型").font = Font(name="Calibri", bold=True, size=10)
        ws.cell(row=row, column=2, value="数量").font = Font(name="Calibri", bold=True, size=10)
        row += 1

        for ct, count in type_dist.items():
            if count > 0:
                ws.cell(row=row, column=1, value=ct).font = DATA_FONT
                ws.cell(row=row, column=2, value=count).font = DATA_FONT
                row += 1

        # ---- 优先级分布 ----
        row += 1
        ws.merge_cells(f"A{row}:F{row}")
        ws[f"A{row}"].value = "📊 优先级分布"
        ws[f"A{row}"].font = SUBTITLE_FONT
        row += 1

        priority_dist = summary.get("priority_distribution", {})
        ws.cell(row=row, column=1, value="优先级").font = Font(name="Calibri", bold=True, size=10)
        ws.cell(row=row, column=2, value="数量").font = Font(name="Calibri", bold=True, size=10)
        row += 1

        for pri, count in priority_dist.items():
            if count > 0:
                cell_pri = ws.cell(row=row, column=1, value=pri)
                cell_pri.font = PRIORITY_FONTS.get(pri, DATA_FONT)
                ws.cell(row=row, column=2, value=count).font = DATA_FONT
                row += 1

        # ---- 各功能点概览 ----
        row += 1
        ws.merge_cells(f"A{row}:F{row}")
        ws[f"A{row}"].value = "📋 各功能点用例数"
        ws[f"A{row}"].font = SUBTITLE_FONT
        row += 1

        # 表头
        for col_idx, header in enumerate(["功能名称", "用例数", "生成模式"], 1):
            cell = ws.cell(row=row, column=col_idx, value=header)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = HEADER_ALIGNMENT
            cell.border = THIN_BORDER
        row += 1

        for suite in suites:
            feature = suite.get("feature", {})
            ws.cell(row=row, column=1, value=feature.get("name", "?"))
            ws.cell(row=row, column=2, value=suite.get("case_count", 0))
            ws.cell(row=row, column=3, value=suite.get("generation_mode", "?"))
            for col_idx in range(1, 4):
                ws.cell(row=row, column=col_idx).font = DATA_FONT
                ws.cell(row=row, column=col_idx).border = THIN_BORDER
            row += 1

        # 列宽
        ws.column_dimensions["A"].width = 18
        ws.column_dimensions["B"].width = 20
        ws.column_dimensions["C"].width = 40

    # ============================================================
    # 功能点独立 Sheet
    # ============================================================

    def _create_feature_sheet(self, suite: dict):
        """为一个功能点创建独立 Sheet"""
        feature = suite.get("feature", {})
        feature_name = feature.get("name", "未命名")
        test_cases = suite.get("test_cases", [])

        # Sheet 名限制 31 字符
        sheet_name = feature_name[:31]
        ws = self.wb.create_sheet(sheet_name)

        # ---- 标题行 ----
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(CASE_COLUMNS))
        title_cell = ws["A1"]
        title_cell.value = f"功能：{feature_name}"
        title_cell.font = TITLE_FONT
        title_cell.alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[1].height = 30

        # ---- 功能信息 ----
        row = 3
        info_items = [
            ("描述", feature.get("description", "")),
            ("子功能", "、".join(feature.get("sub_features", []))),
            ("约束条件", "；".join(feature.get("constraints", []))),
            ("用例数", len(test_cases)),
            ("生成模式", suite.get("generation_mode", "?")),
        ]
        for label, value in info_items:
            if value:  # 空值不显示
                ws.cell(row=row, column=1, value=label).font = Font(name="Calibri", bold=True, size=10)
                ws.cell(row=row, column=2, value=str(value) if not isinstance(value, int) else value).font = DATA_FONT
                # 合并后面的列
                ws.merge_cells(start_row=row, start_column=2, end_row=row, end_column=len(CASE_COLUMNS))
                row += 1

        # ---- 用例表头 ----
        row += 1
        for col_idx, (col_name, col_width) in enumerate(CASE_COLUMNS, 1):
            cell = ws.cell(row=row, column=col_idx, value=col_name)
            cell.font = HEADER_FONT
            cell.fill = HEADER_FILL
            cell.alignment = HEADER_ALIGNMENT
            cell.border = THIN_BORDER
            ws.column_dimensions[get_column_letter(col_idx)].width = col_width
        ws.row_dimensions[row].height = 25

        # ---- 用例数据行 ----
        header_row = row
        for case in test_cases:
            row += 1
            case_type = case.get("type", "")
            priority = case.get("priority", "")

            # 获取行背景色
            row_fill = TYPE_FILLS.get(case_type)
            row_font = PRIORITY_FONTS.get(priority, DATA_FONT)

            values = [
                case.get("id", ""),
                case_type,
                priority,
                case.get("title", ""),
                "\n".join(case.get("preconditions", [])),
                "\n".join(f"{i+1}. {s}" for i, s in enumerate(case.get("steps", []))),
                case.get("expected", ""),
            ]

            for col_idx, value in enumerate(values, 1):
                cell = ws.cell(row=row, column=col_idx, value=value)
                cell.font = row_font if col_idx in (1, 2, 3) else DATA_FONT
                cell.border = THIN_BORDER

                # 居中列
                if col_idx in (1, 2, 3):
                    cell.alignment = CENTER_ALIGNMENT
                else:
                    cell.alignment = DATA_ALIGNMENT

                # 行背景色（非居中列也应用）
                if row_fill:
                    cell.fill = row_fill

            # 设置行高（根据步骤数动态调整）
            steps_count = len(case.get("steps", []))
            ws.row_dimensions[row].height = max(20, steps_count * 18 + 10)

        # 冻结表头
        ws.freeze_panes = f"A{header_row + 1}"    

# ============================================================
# 自检
# ============================================================

def test_excel_reporter():
    """用 Day 13 的输出测试 Excel 报告生成"""
    import tempfile

    print("=" * 60)
    print("🧪 测试 ExcelReporter")
    print("=" * 60)

    reporter = ExcelReporter()

    # 使用已有的 login 测试用例 JSON
    json_path = "outputs/login_requirement_test_cases.json"
    if not os.path.exists(json_path):
        print(f"⚠️ 测试文件不存在，跳过: {json_path}")
        print("   请先运行: python src/agent/main_pipeline.py docs/requirements/login_requirement.md")
        return

    output_path = "outputs/login_requirement_test_cases.xlsx"
    result = reporter.generate(json_path, output_path)

    print(f"生成文件: {result}")
    print(f"文件大小: {os.path.getsize(result)} 字节")

    # 验证：用 openpyxl 读回来检查
    from openpyxl import load_workbook
    wb = load_workbook(result)
    print(f"Sheet 数量: {len(wb.sheetnames)}")
    print(f"Sheet 列表: {wb.sheetnames}")

    # 检查总览 Sheet
    ws_overview = wb["总览"]
    print(f"总览 Sheet 行数: {ws_overview.max_row}")

    # 检查功能 Sheet
    for sheet_name in wb.sheetnames[1:]:
        ws = wb[sheet_name]
        print(f"Sheet「{sheet_name}」: {ws.max_row} 行 x {ws.max_column} 列")

    wb.close()
    print("\n✅ ExcelReporter 测试通过！")


if __name__ == "__main__":
    test_excel_reporter()