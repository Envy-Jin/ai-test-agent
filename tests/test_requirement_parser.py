# tests/test_requirement_parser.py —— 需求解析器单元测试
import pytest
import json
import os
import sys

# 将项目 src 目录加入 Python 路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from src.agent.requirement_parser import (
    split_by_features,
    extract_sub_features,
    extract_constraints,
    parse_requirement,
    read_requirement_file,
    save_parsed_result,
    save_parsed_result_csv,
    save_parsed_result_markdown,
    Feature,
    ParsedRequirement,
)


# === split_by_features 测试 ===
def test_split_single_feature():
    """测试单个功能分段"""
    text = "用户登录功能：支持手机号登录。"
    segments = split_by_features(text)
    assert len(segments) == 1
    assert segments[0][0] == "用户登录"

def test_split_multiple_features():
    """测试多个功能分段"""
    text = "用户注册功能：支持手机号注册。商品搜索功能：支持关键词搜索。订单管理功能：支持创建订单。"
    segments = split_by_features(text)
    assert len(segments) == 3
    names = [s[0] for s in segments]
    assert names == ["用户注册", "商品搜索", "订单管理"]

def test_split_no_feature():
    """测试没有功能关键词的文本"""
    text = "这是一段普通文本，没有功能描述。"
    segments = split_by_features(text)
    assert len(segments) == 0


# === extract_sub_features 测试 ===
def test_extract_sub_features_basic():
    """测试基础子功能提取"""
    desc = "支持手机号注册，需要短信验证码验证，支持按价格排序。"
    subs = extract_sub_features(desc)
    assert len(subs) >= 2
    # 验证包含关键子功能
    assert any("手机号" in s for s in subs)
    assert any("验证码" in s for s in subs)

def test_extract_sub_features_empty():
    """测试空描述"""
    subs = extract_sub_features("")
    assert subs == []

def test_extract_sub_features_no_keywords():
    """测试不含'支持'或'需要'的描述"""
    desc = "密码不少于8位，年龄必须在1-150之间。"
    subs = extract_sub_features(desc)
    # 不含"支持"或"需要"，应返回空列表或极少
    assert len(subs) == 0

# === extract_constraints 测试 ===
def test_extract_constraints_basic():
    """测试基础约束提取"""
    desc = "密码不少于8位且必须包含数字，年龄必须在1-150之间，同一手机号不可重复注册。"
    constraints = extract_constraints(desc)
    assert len(constraints) >= 2
    assert any("不少于" in c for c in constraints)
    assert any("不可" in c for c in constraints)

def test_extract_constraints_no_keywords():
    """测试不含约束关键词的描述"""
    desc = "支持手机号登录，支持邮箱登录。"
    constraints = extract_constraints(desc)
    assert len(constraints) == 0

def test_extract_constraints_dedup():
    """测试同一短句不重复添加"""
    desc = "密码必须不少于8位。"
    constraints = extract_constraints(desc)
    # 同一句即使包含多个关键词，也应只出现一次
    constraint_text_count = sum(1 for c in constraints if "密码必须不少于8位" in c)
    assert constraint_text_count <= 1

# === parse_requirement 完整流程测试 ===
def test_parse_complete_requirement():
    """测试完整需求文档解析"""
    text = (
        "用户注册功能：支持手机号注册，需要短信验证码验证，"
        "密码不少于8位且必须包含数字和字母，同一手机号不可重复注册。\n"
        "商品搜索功能：支持关键词搜索，搜索结果不超过1000条。"
    )
    result = parse_requirement(text)

    assert result.total_features == 2
    assert result.total_constraints >= 2
    assert result.features[0].feature == "用户注册"
    assert result.features[1].feature == "商品搜索"

def test_parse_empty_text():
    """测试空文本解析"""
    result = parse_requirement("")
    assert result.total_features == 0
    assert result.features == []

def test_parse_single_feature():
    """测试单功能解析"""
    text = "登录功能：支持手机号登录，密码不少于8位。"
    result = parse_requirement(text)
    assert result.total_features == 1
    assert result.features[0].feature == "登录"


# === 多格式输出和扩展功能测试 ===

def test_extract_numbers_from_constraint():
    """测试约束条件数字提取"""
    # 先尝试导入，如果还没创建模块就跳过
    try:
        from src.agent.test_case_pregenerator import _extract_numbers
    except ImportError:
        pytest.skip("test_case_pregenerator 模块尚未创建")

    assert _extract_numbers("密码不少于8位") == [8]
    assert _extract_numbers("年龄必须在1-150之间") == [1, 150]
    assert _extract_numbers("无数字约束") == []

def test_markdown_output():
    """测试 Markdown 输出"""

    result = ParsedRequirement(
        features=[Feature(
            feature="登录",
            sub_features=["手机号登录"],
            constraints=["密码不少于8位"]
        )],
        total_features=1,
        total_constraints=1,
        source_file="test.txt"
    )

    output_path = "docs/test_markdown_output.md"
    save_parsed_result_markdown(result, output_path)

    # 验证文件存在且内容包含关键信息
    with open(output_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "登录" in content
    assert "密码不少于8位" in content

    # 清理测试文件
    os.remove(output_path)

def test_csv_output():
    """测试 CSV 输出"""

    result = ParsedRequirement(
        features=[Feature(
            feature="注册",
            sub_features=["手机号注册"],
            constraints=["密码不少于8位"]
        )],
        total_features=1,
        total_constraints=1,
        source_file="test.txt"
    )

    output_path = "docs/test_csv_output.csv"
    save_parsed_result_csv(result, output_path)

    # 验证文件存在
    with open(output_path, "r", encoding="utf-8") as f:
        content = f.read()
    assert "注册" in content
    assert "密码不少于8位" in content

    # 清理测试文件
    os.remove(output_path)