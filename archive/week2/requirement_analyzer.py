"""需求文档分析模块：读取文本需求并提取关键规则行。"""

import json
from pathlib import Path
from typing import Any

KEYWORDS: list[str] = ["必须", "不允许", "超过", "支持", "不得", "至少"]


def analyze_requirement(filepath: str, output_path: str) -> dict[str, Any]:
    """
    分析需求文档文本文件，统计基本信息并提取含关键词的规则行。

    读取指定 txt 文件，统计字数与行数，使用列表推导式筛选包含
    预定义关键词的行，将分析结果写入 JSON 文件并返回结果字典。

    Args:
        filepath: 需求文档 txt 文件路径。
        output_path: 分析结果 JSON 文件的输出路径。

    Returns:
        dict[str, Any]: 分析结果，包含以下字段：
            - filepath: 输入文件路径
            - char_count: 字数（不含换行符，不含空行）
            - line_count: 非空行数
            - keywords: 使用的关键词列表
            - keyword_lines: 包含关键词的行列表

    Raises:
        FileNotFoundError: 输入文件不存在。
        OSError: 读取输入文件或写入输出文件失败。
        ValueError: 输入路径不是 txt 文件。
    """
    input_path = Path(filepath)
    result_path = Path(output_path)

    if input_path.suffix.lower() != ".txt":
        raise ValueError(f"仅支持 txt 文件，当前文件: {filepath}")

    try:
        content = input_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"需求文件不存在: {filepath}") from exc
    except OSError as exc:
        raise OSError(f"读取需求文件失败: {filepath}") from exc

    lines = content.splitlines()
    non_empty_lines = [line for line in lines if line.strip()]
    # 只统计非空行字符数（不含换行符）
    char_count = sum(len(line) for line in non_empty_lines)
    line_count = len(non_empty_lines)

    keyword_lines = [
        line.strip()
        for line in non_empty_lines
        if any(keyword in line for keyword in KEYWORDS)
    ]

    result: dict[str, Any] = {
        "filepath": str(input_path),
        "char_count": char_count,
        "line_count": line_count,
        "keywords": KEYWORDS,
        "keyword_lines": keyword_lines,
    }

    try:
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError as exc:
        raise OSError(f"写入分析结果失败: {output_path}") from exc

    return result
