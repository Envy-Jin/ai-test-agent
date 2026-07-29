"""
src/agent/main_pipeline.py —— 需求文档 → 测试用例 主流水线

Day 13 核心产出：串联 DocReader → FeatureExtractor → TestCaseGenerator

一个函数跑通全流程：
    doc_reader.py          →  读取需求文档
            ↓
    feature_extractor.py  →  提取功能点
            ↓
    test_case_generator.py →  为每个功能点生成测试用例
            ↓
    main_pipeline.py      →  汇总输出 JSON 报告
"""

import json
import os
import time
from dataclasses import dataclass, asdict

from doc_reader import DocReader
from feature_extractor import FeatureExtractor, FeatureExtractionResult, Feature
from test_case_generator import TestCaseGenerator, GenerationResult, FeatureTestSuite
from logger_config import setup_logger

logger = setup_logger("ai_test_agent")

# ============================================================
# 流水线入口
# ============================================================
def run_pipeline(
    input_path: str,
    output_dir: str = "outputs",
    verbose: bool = True,
) -> dict:
    """
    主流水线：需求文档 → 测试用例 JSON

    流程：
    1. 读取需求文档 (DocReader)
    2. 提取功能点 (FeatureExtractor)
    3. 为每个功能点生成测试用例 (TestCaseGenerator)
    4. 汇总输出 JSON 报告

    Args:
        input_path: 需求文档路径 (.txt / .md)
        output_dir: 输出目录
        verbose: 是否显示详细进度

    Returns:
        dict: 包含完整生成结果的 dict

    Raises:
        FileNotFoundError: 需求文档不存在
        ValueError: 文件格式不支持
    """
    pipeline_start = time.time()

    if verbose:
        print("=" * 60)
        print("🚀 需求文档 → 测试用例生成器")
        print("=" * 60)
        print(f"📄 输入: {input_path}")

    # ============================================================
    # 阶段 1：读取需求文档
    # ============================================================
    if verbose:
        print("\n📖 [阶段 1/3] 读取需求文档...")

    reader = DocReader()
    # parse_file 抛 FileNotFoundError / ValueError，
    # 让异常自然向上传播，由 main() / run_pipeline() 调用方决定如何处理
    requirement_text = reader.parse_file(input_path)

    if verbose:
        print(f"   ✅ 读取完成: {len(requirement_text)} 字符, "
              f"{len(requirement_text.splitlines())} 行")


    # ============================================================
    # 阶段 2：提取功能点
    # ============================================================
    if verbose:
        print("\n🔍 [阶段 2/3] 分析需求，提取功能点...")

    extractor = FeatureExtractor()
    extraction_result = extractor.extract(requirement_text)

    if not extraction_result.success:
        if verbose:
            print(f"   ❌ 功能提取失败: {extraction_result.error_message}")
        return _build_error_report(input_path, extraction_result)

    features = extraction_result.features
    if verbose:
        print(f"   ✅ 提取到 {len(features)} 个功能点:")
        for i, feat in enumerate(features):
            subs = f" ({len(feat.sub_features)} 个子功能)" if feat.sub_features else ""
            inputs = f" — {len(feat.inputs)} 个输入字段" if feat.inputs else ""
            print(f"      {i+1}. {feat.name}{subs}{inputs}")


    # ============================================================
    # 阶段 3：生成测试用例
    # ============================================================
    if verbose:
        print(f"\n🧪 [阶段 3/3] 为每个功能点生成测试用例...")

    generator = TestCaseGenerator()
    gen_result = generator.generate_all(features, verbose=verbose)

    # ============================================================
    # 汇总输出
    # ============================================================
    pipeline_elapsed = time.time() - pipeline_start

    if verbose:
        print(f"\n{'=' * 60}")
        print(f"✅ 流水线执行完成！")
        print(f"   功能点: {len(features)} 个")
        print(f"   测试用例: {gen_result.total_cases} 个")
        print(f"   成功: {gen_result.success_count} | 失败: {gen_result.failed_count}")
        print(f"   总耗时: {pipeline_elapsed:.1f}s")
        print(f"{'=' * 60}")

    # 构建输出 dict
    report = _build_report(
        input_path=input_path,
        features=features,
        gen_result=gen_result,
        elapsed=pipeline_elapsed,
    )

    # 保存 JSON
    os.makedirs(output_dir, exist_ok=True)
    base_name = os.path.splitext(os.path.basename(input_path))[0]
    output_path = os.path.join(output_dir, f"{base_name}_test_cases.json")

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    if verbose:
        print(f"\n📁 测试用例已保存: {output_path}")

    return report

# ============================================================
# 报告构建
# ============================================================

def _build_report(
    input_path: str,
    features: list[Feature],
    gen_result: GenerationResult,
    elapsed: float,
) -> dict:
    """构建最终输出 dict"""

    suites_json = []
    for suite in gen_result.suites:
        cases_json = []
        for tc in suite.test_cases:
            cases_json.append({
                "id": tc.id,
                "title": tc.title,
                "type": tc.type,
                "priority": tc.priority,
                "preconditions": tc.preconditions,
                "steps": tc.steps,
                "expected": tc.expected,
            })

        suites_json.append({
            "feature": {
                "name": suite.feature.name,
                "description": suite.feature.description,
                "sub_features": suite.feature.sub_features,
                "constraints": suite.feature.constraints,
                "inputs": suite.feature.inputs,
            },
            "test_cases": cases_json,
            "case_count": len(cases_json),
            "generation_mode": suite.generation_mode,
        })

    # 用例类型统计
    type_stats = {"正向": 0, "边界": 0, "异常": 0, "安全": 0, "性能": 0}
    priority_stats = {"P0": 0, "P1": 0, "P2": 0}
    for suite in gen_result.suites:
        for tc in suite.test_cases:
            type_stats[tc.type] = type_stats.get(tc.type, 0) + 1
            priority_stats[tc.priority] = priority_stats.get(tc.priority, 0) + 1

    return {
        "meta": {
            "source_file": input_path,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "pipeline_version": "1.0.0",
            "elapsed_seconds": round(elapsed, 1),
        },
        "summary": {
            "features_count": len(features),
            "total_cases": gen_result.total_cases,
            "success_count": gen_result.success_count,
            "failed_count": gen_result.failed_count,
            "case_type_distribution": type_stats,
            "priority_distribution": priority_stats,
        },
        "suites": suites_json,
    }


def _build_error_report(input_path: str, extraction_result: FeatureExtractionResult) -> dict:
    """构建错误报告"""
    return {
        "meta": {
            "source_file": input_path,
            "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "status": "failed",
            "stage": "feature_extraction",
        },
        "error": {
            "message": extraction_result.error_message,
            "raw_analysis": extraction_result.raw_analysis,
        },
        "suites": [],
    }


# ============================================================
# 流水线摘要打印
# ============================================================

def print_pipeline_summary(report: dict):
    """打印流水线结果的详细摘要"""
    meta = report.get("meta", {})
    summary = report.get("summary", {})

    print("\n" + "=" * 60)
    print("📊 生成结果摘要")
    print("=" * 60)
    print(f"📄 需求文档: {meta.get('source_file', 'N/A')}")
    print(f"📅 生成时间: {meta.get('generated_at', 'N/A')}")
    print(f"⏱ 总耗时: {meta.get('elapsed_seconds', 'N/A')}s")
    print()
    print(f"📦 功能点数: {summary.get('features_count', 0)}")
    print(f"📝 测试用例数: {summary.get('total_cases', 0)}")
    print(f"✅ 成功: {summary.get('success_count', 0)} | "
          f"❌ 失败: {summary.get('failed_count', 0)}")

    print("\n📈 用例类型分布:")
    for case_type, count in summary.get("case_type_distribution", {}).items():
        if count > 0:
            bar = "█" * min(count, 30)
            print(f"   {case_type:4s}: {bar} {count}")

    print("\n📈 优先级分布:")
    for priority, count in summary.get("priority_distribution", {}).items():
        if count > 0:
            bar = "█" * min(count, 30)
            print(f"   {priority:4s}: {bar} {count}")

    # 每个功能点的用例数
    print("\n📋 各功能点用例数:")
    for suite in report.get("suites", []):
        feature = suite.get("feature", {})
        print(f"   {feature.get('name', '?'):20s}: {suite.get('case_count', 0)} 个用例 "
              f"({suite.get('generation_mode', '?')})")

    print("=" * 60)

# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    import sys

    # 默认使用 login_requirement.md
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
    else:
        input_file = "docs/requirements/login_requirement.md"

    # 运行流水线
    report = run_pipeline(
        input_path=input_file,
        output_dir="outputs",
        verbose=True,
    )

    # 打印摘要
    print_pipeline_summary(report)

    print("\n🎉 端到端流水线执行完成！")