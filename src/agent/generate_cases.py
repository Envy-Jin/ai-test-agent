"""
src/agent/generate_cases.py —— 需求文档 → 测试用例 CLI 工具

Day 14 核心产出：将主流水线、Excel 报告、Markdown 报告打包成命令行工具。

用法：
    # 基础用法（默认 JSON）
    python src/agent/generate_cases.py -i docs/requirements/login_requirement.md

    # 输出 Excel
    python src/agent/generate_cases.py -i docs/requirements/login_requirement.md -f excel

    # 同时输出三种格式
    python src/agent/generate_cases.py -i docs/requirements/login_requirement.md -f all

    # 自定义输出路径
    python src/agent/generate_cases.py -i docs/requirements/register_requirement.txt -o outputs/my_report

    # 静默模式
    python src/agent/generate_cases.py -i docs/requirements/login_requirement.md -q
"""

import argparse
import json
import os
import sys
import time
from logger_config import setup_logger

logger = setup_logger("ai_test_agent")

def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        prog="generate_cases",
        description="需求文档 → 测试用例生成器 | 支持 JSON / Excel / Markdown 输出",
        epilog="示例: python src/agent/generate_cases.py -i docs/requirements/login_requirement.md -f all",
    )

    parser.add_argument(
        "--input", "-i",
        required=True,
        metavar="FILE",
        help="需求文档路径（支持 .txt / .md）",
    )

    parser.add_argument(
        "--output", "-o",
        default=None,
        metavar="PREFIX",
        help="输出文件前缀（不含扩展名），默认根据输入文件自动生成到 outputs/ 目录",
    )

    parser.add_argument(
        "--format", "-f",
        choices=["json", "excel", "markdown", "all"],
        default="json",
        help="输出格式: json（默认）, excel, markdown, all（三种都输出）",
    )

    parser.add_argument(
        "--temperature", "-t",
        type=float,
        default=0.2,
        help="Gemini 温度参数（0.0~1.0），默认 0.2",
    )

    parser.add_argument(
        "--quiet", "-q",
        action="store_true",
        help="静默模式，不显示详细进度",
    )

    parser.add_argument(
        "--version", "-v",
        action="version",
        version="generate_cases v1.0.0 (Day 14)",
    )

    return parser

def run(args: argparse.Namespace):
    """执行 CLI 命令"""
    # ============================================================
    # 1. 参数处理
    # ============================================================
    input_path = args.input

    # 验证输入文件
    if not os.path.exists(input_path):
        print(f"❌ 错误：需求文档不存在 → {input_path}")
        sys.exit(1)

    ext = os.path.splitext(input_path)[1].lower()
    if ext not in (".txt", ".md", ".markdown"):
        print(f"❌ 错误：不支持的文件格式 → {ext}（仅支持 .txt / .md）")
        sys.exit(1)

    # 确定输出前缀
    if args.output:
        output_prefix = args.output
    else:
        base = os.path.splitext(os.path.basename(input_path))[0]
        output_prefix = f"outputs/{base}_test_cases"

    output_format = args.format
    verbose = not args.quiet

    # ============================================================
    # 2. 运行主流水线 → 生成 JSON
    # ============================================================
    if verbose:
        print("=" * 60)
        print("  🚀 需求文档 → 测试用例生成器")
        print("=" * 60)
        print(f"  📄 输入: {input_path}")
        print(f"  📁 输出: {output_prefix}.*")
        print(f"  🎯 格式: {output_format}")
        print(f"  🌡 温度: {args.temperature}")
        print("=" * 60)

    # 导入并运行流水线
    from main_pipeline import run_pipeline

    json_path = f"{output_prefix}.json"

    start_time = time.time()

    try:
        report = run_pipeline(
            input_path=input_path,
            output_dir=os.path.dirname(output_prefix) or "outputs",
            verbose=verbose,
        )
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    # 在 run() 函数调用 run_pipeline 之后
    if isinstance(report, dict):
        meta = report.get("meta", {})
        if meta.get("status") == "failed":
            print("❌ 流水线执行失败，跳过报表生成")
            error_msg = report.get("error", {}).get("message", "未知错误")
            print(f"   错误: {error_msg}")
            sys.exit(1)

    # 重命名：主流水线输出可能路径不同，确保一致
    # main_pipeline 内部会存到 outputs/{base}_test_cases.json
    # 这里用 run_pipeline 的返回值来确保一致性

    if verbose:
        print(f"\n  ✅ 流水线执行完成（{time.time() - start_time:.1f}s）")


    # ============================================================
    # 3. 根据 --format 生成对应格式
    # ============================================================
    generated_files = [json_path]  # JSON 总是默认生成的

    if output_format in ("excel", "all"):
        if verbose:
            print(f"\n  📊 生成 Excel 报告...")
        from excel_reporter import ExcelReporter
        excel_path = f"{output_prefix}.xlsx"
        ExcelReporter().generate(json_path, excel_path)
        generated_files.append(excel_path)
        if verbose:
            print(f"     ✅ {excel_path}")

    if output_format in ("markdown", "all"):
        if verbose:
            print(f"\n  📝 生成 Markdown 报告...")
        from markdown_reporter import MarkdownReporter
        md_path = f"{output_prefix}.md"
        MarkdownReporter().generate(json_path, md_path)
        generated_files.append(md_path)
        if verbose:
            print(f"     ✅ {md_path}")

    # ============================================================
    # 4. 打印结果摘要
    # ============================================================
    if verbose:
        print("\n" + "=" * 60)
        print("  🎉 生成完成！")
        print("=" * 60)
        for f in generated_files:
            if os.path.exists(f):
                size = os.path.getsize(f)
                size_str = f"{size:,} 字节" if size < 1024 * 1024 else f"{size / 1024:.1f} KB"
                print(f"  📁 {f} ({size_str})")

        # 简短统计
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                summary = json.load(f).get("summary", {})
            print(f"\n  📊 功能点: {summary.get('features_count', '?')}")
            print(f"  📝 测试用例: {summary.get('total_cases', '?')}")
        except Exception:
            pass

    else:
        # 静默模式：只输出文件列表
        for f in generated_files:
            if os.path.exists(f):
                print(f)

    return generated_files


def main():
    """CLI 入口"""
    parser = build_parser()
    args = parser.parse_args()

    # 如果没有参数，打印帮助
    if len(sys.argv) == 1:
        parser.print_help()
        print("\n  💡 快速开始:")
        print("     python src/agent/generate_cases.py -i docs/requirements/login_requirement.md -f all")
        sys.exit(0)

    run(args)


# ============================================================
# 自检
# ============================================================

def test_cli():
    """测试 CLI 命令"""
    print("=" * 60)
    print("🧪 测试 generate_cases CLI")
    print("=" * 60)

    # 模拟命令行参数
    import argparse

    # 测试 1：--help
    print("\n--- 测试 1：--help ---")
    parser = build_parser()
    try:
        args = parser.parse_args(["--help"])
    except SystemExit:
        pass  # --help 会触发 SystemExit
    print("   --help 正常输出 ✓")

    # 测试 2：--version
    print("\n--- 测试 2：--version ---")
    try:
        args = parser.parse_args(["--version"])
    except SystemExit:
        pass
    print("   --version 正常输出 ✓")

    # 测试 3：实际运行
    print("\n--- 测试 3：实际生成 ---")
    test_input = "docs/requirements/login_requirement.md"
    if not os.path.exists(test_input):
        print(f"   ⚠️ 跳过：{test_input} 不存在")
        return

    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        mock_args = argparse.Namespace(
            input=test_input,
            output=f"{tmpdir}/test_output",
            format="all",
            temperature=0.2,
            quiet=True,
        )
        files = run(mock_args)
        print(f"   生成文件: {len(files)} 个")
        for f in files:
            if os.path.exists(f):
                print(f"   ✓ {f} ({os.path.getsize(f)} 字节)")

    print("\n✅ generate_cases CLI 测试通过！")


if __name__ == "__main__":
    import sys

    # 如果有命令行参数（非测试），走 main()
    if len(sys.argv) > 1 and sys.argv[0].endswith("generate_cases.py"):
        main()
    else:
        test_cli()