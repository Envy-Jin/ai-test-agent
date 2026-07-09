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
        help="需求文档路径（.txt 格式）"
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

    args = parser.parse_args()

    # 1. 读取文件
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
    save_parsed_result(result, args.output)
    print(f"\n✅ 结果已保存到：{args.output}")


if __name__ == "__main__":
    main()