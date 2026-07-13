"""
需求文档解析命令行工具

用法：
    python src/agent/requirement_parser.py docs/requirement.txt
    python src/agent/requirement_parser.py docs/requirement.txt -o result.json -v
"""

import argparse
import json
import re
import sys
import glob
import os
from dataclasses import dataclass, field, asdict

# ====== 数据结构 ======

@dataclass
class Feature:
    """单个功能模块的解析结果"""
    feature: str
    sub_features: list[str] = field(default_factory=list)
    constraints: list[str] = field(default_factory=list)
    raw_text: str = ""

@dataclass
class ParsedRequirement:
    """完整需求文档的解析结果"""
    features: list[Feature] = field(default_factory=list)
    source_file: str = ""
    total_features: int = 0
    total_constraints: int = 0

    def summarize(self) -> str:
        return (
            f"共解析出 {self.total_features} 个功能模块，"
            f"提取 {self.total_constraints} 条约束条件"
        )

# ====== 解析函数 ======

def split_by_features(text: str) -> list[tuple[str, str]]:
    """将需求文本按功能分段"""
    pattern = r'([\u4e00-\u9fa5]+)功能[：:]'
    matches = list(re.finditer(pattern, text))

    segments = []
    for i, match in enumerate(matches):
        feature_name = match.group(1)
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        description = text[start:end].strip()
        segments.append((feature_name, description))
    return segments

def extract_sub_features(description: str) -> list[str]:
    """从功能描述中提取子功能"""
    pattern = r'(支持|需要)([\u4e00-\u9fa5\w]+?)(?=[，,。.；;（(])'
    matches = re.findall(pattern, description)
    return [f"{prefix}{content}" for prefix, content in matches]

def extract_constraints(description: str) -> list[str]:
    """从功能描述中提取约束条件"""
    constraint_keywords = [
        '不少于', '不超过', '必须', '唯一', '至少',
        '最多', '不可', '不能', '禁止'
    ]
    constraints = []
    sentences = re.split(r'[，,。.；;]', description)
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        for keyword in constraint_keywords:
            if keyword in sentence:
                constraints.append(sentence)
                break
    return constraints

def parse_requirement(text: str) -> ParsedRequirement:
    """解析完整的需求文档文本"""
    segments = split_by_features(text)
    features = []
    total_constraints = 0

    for feature_name, description in segments:
        sub_features = extract_sub_features(description)
        constraints = extract_constraints(description)
        features.append(Feature(
            feature=feature_name,
            sub_features=sub_features,
            constraints=constraints,
            raw_text=description
        ))
        total_constraints += len(constraints)

    return ParsedRequirement(
        features=features,
        total_features=len(features),
        total_constraints=total_constraints
    )

# ====== 文件操作 ======

def read_requirement_file(filepath: str) -> str:
    """读取需求文件"""
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def save_parsed_result(result: ParsedRequirement, output_path: str) -> None:
    """保存解析结果为 JSON"""
    result_dict = {
        "features": [asdict(f) for f in result.features],
        "source_file": result.source_file,
        "total_features": result.total_features,
        "total_constraints": result.total_constraints,
        "summary": result.summarize()
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, ensure_ascii=False, indent=2)


def save_parsed_result_markdown(result: ParsedRequirement, output_path: str) -> None:
    """
    将解析结果保存为 Markdown 格式

    Args:
        result: ParsedRequirement 对象
        output_path: 输出文件路径
    """
    lines = []
    lines.append(f"# 需求文档解析结果")
    lines.append(f"\n> 来源：{result.source_file}")
    lines.append(f"\n{result.summarize()}\n")

    for f in result.features:
        lines.append(f"\n## {f.feature}\n")

        if f.sub_features:
            lines.append("### 子功能\n")
            for sf in f.sub_features:
                lines.append(f"- {sf}")
            lines.append("")

        if f.constraints:
            lines.append("### 约束条件\n")
            lines.append("| # | 约束描述 |")
            lines.append("|---|----------|")
            for i, c in enumerate(f.constraints, 1):
                lines.append(f"| {i} | {c} |")
            lines.append("")

    markdown_text = "\n".join(lines)
    with open(output_path, "w", encoding="utf-8") as f_out:
        f_out.write(markdown_text)
    print(f"✅ Markdown 结果已保存到 {output_path}")


def save_parsed_result_csv(result: ParsedRequirement, output_path: str) -> None:
    """
    将解析结果保存为 CSV 格式（每个功能一行）

    Args:
        result: ParsedRequirement 对象
        output_path: 输出文件路径
    """
    import csv

    with open(output_path, "w", encoding="utf-8", newline="") as f_out:
        writer = csv.writer(f_out)
        # 表头
        writer.writerow(["功能名称", "子功能", "约束条件", "子功能数量", "约束数量"])
        # 数据行
        for f in result.features:
            writer.writerow([
                f.feature,
                "; ".join(f.sub_features),
                "; ".join(f.constraints),
                len(f.sub_features),
                len(f.constraints)
            ])
    print(f"✅ CSV 结果已保存到 {output_path}")

def batch_parse(directory: str, output_dir: str = "docs", verbose: bool = False) -> list[str]:
    """
    批量解析目录下所有 .txt 需求文件

    Args:
        directory: 需求文件目录路径
        output_dir: 输出文件目录
        verbose: 是否显示详细输出
    Returns:
        成功解析的文件路径列表
    """
    txt_files = glob.glob(os.path.join(directory, "*.txt"))
    if not txt_files:
        print(f"⚠️  目录 {directory} 中没有 .txt 文件")
        return []

    print(f"找到 {len(txt_files)} 个需求文件")
    success_files = []

    for filepath in txt_files:
        try:
            text = read_requirement_file(filepath)
            result = parse_requirement(text)
            result.source_file = filepath

            # 输出文件名 = 原文件名 + _parsed.json
            basename = os.path.splitext(os.path.basename(filepath))[0]
            output_path = os.path.join(output_dir, f"{basename}_parsed.json")

            save_parsed_result(result, output_path)
            success_files.append(filepath)

            if verbose:
                print(f"\n📄 {filepath}")
                print(f"   {result.summarize()}")
        except Exception as e:
            print(f"❌ 解析失败：{filepath} — {type(e).__name__}: {e}")

    print(f"\n✅ 成功解析 {len(success_files)}/{len(txt_files)} 个文件")
    return success_files

    
# ====== 命令行入口 ======

def main():
    parser = argparse.ArgumentParser(
        description="需求文档解析工具：从 .txt 需求文件中提取功能点，输出结构化 JSON",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python src/agent/requirement_parser.py docs/requirement.txt
  python src/agent/requirement_parser.py docs/requirement.txt -o result.json -v
        """
    )
    parser.add_argument(
        "input_file",
        nargs="?",         # 0 或 1 个参数
        default=None,
        help="输入需求文件路径（批量模式 -b 下不需要）"
    )
    parser.add_argument(
        "-o", "--output",
        default="docs/parsed_requirement.json",
        help="输出 JSON 文件路径（默认: docs/parsed_requirement.json）"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="显示详细解析结果"
    )

    parser.add_argument(
    "-f", "--format",
    choices=["json", "markdown", "csv"],
    default="json",
    help="输出格式：json / markdown / csv（默认: json）"
    )

    parser.add_argument(
    "-t", "--test-cases",
    action="store_true",
    help="根据约束条件预生成边界值测试用例框架"
    )

    parser.add_argument(
    "-b", "--batch",
    help="批量解析目录下所有 .txt 文件（传入目录路径）"
    )

    args = parser.parse_args()

    if args.batch:
        batch_parse(args.batch, output_dir="docs", verbose=args.verbose)
    return

    # 1. 读取文件
    # 单文件模式下，如果没有 input_file，报错更友好
    if not args.input_file:
        parser.error("单文件模式需要提供 input_file")
        
    try:
        text = read_requirement_file(args.input_file)
        print(f"📄 读取文件：{args.input_file}（{len(text)} 字符）")
    except FileNotFoundError:
        print(f"❌ 文件不存在：{args.input_file}")
        sys.exit(1)

    # 2. 解析
    result = parse_requirement(text)
    result.source_file = args.input_file
    print(f"\n📊 {result.summarize()}")

    # 3. 详细输出
    if args.verbose:
        print("\n" + "=" * 50)
        for f in result.features:
            print(f"\n【{f.feature}】")
            if f.sub_features:
                print(f"  子功能 ({len(f.sub_features)} 个):")
                for sf in f.sub_features:
                    print(f"    - {sf}")
            if f.constraints:
                print(f"  约束条件 ({len(f.constraints)} 个):")
                for c in f.constraints:
                    print(f"    - {c}")
        print("\n" + "=" * 50)

    # 4. 保存结果
    # save_parsed_result(result, args.output)
    # print(f"\n✅ 结果已保存到：{args.output}")

    # 替换原来的 save_parsed_result(result, args.output) 调用：

    # 根据格式自动调整输出文件后缀

    output_path = args.output
    if args.format == "markdown" and not output_path.endswith(".md"):
        output_path = output_path.replace(".json", ".md")
    elif args.format == "csv" and not output_path.endswith(".csv"):
        output_path = output_path.replace(".json", ".csv")

    # 按格式保存
    if args.format == "json":
        save_parsed_result(result, output_path)
    elif args.format == "markdown":
        save_parsed_result_markdown(result, output_path)
    elif args.format == "csv":
        save_parsed_result_csv(result, output_path)

    print(f"\n✅ 结果已保存到：{output_path}（格式：{args.format}）")

    # 测试用例预生成
    if args.test_cases:
        from test_case_pregenerator import generate_from_parsed_requirement
        test_cases_dict = generate_from_parsed_requirement(result)
        test_cases_output = args.output.replace(".json", "_test_cases.json")
        import json
        from dataclasses import asdict
        with open(test_cases_output, "w", encoding="utf-8") as f:
            # 将每个 TestCase 转为 dict
            serializable = {}
            for feature_name, cases in test_cases_dict.items():
                serializable[feature_name] = [asdict(c) for c in cases]
            json.dump(serializable, f, ensure_ascii=False, indent=2)
        print(f"\n✅ 测试用例已保存到：{test_cases_output}")


if __name__ == "__main__":
    main()