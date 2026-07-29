"""
src/agent/test_case_generator.py —— 测试用例生成器（基于功能点）

Day 13 核心模块之三：为每个功能点独立生成正向 / 边界 / 异常测试用例。

使用 SafeGeminiClient.generate_schema() 强制 Schema 输出，
配合 extract_json 兜底，确保每个功能点都有覆盖完整的测试用例。
"""

import time
from dataclasses import dataclass, field, asdict
from safe_gemini_client import SafeGeminiClient, SafeChat
from json_extractor import extract_json_with_fallback
from logger_config import setup_logger
from feature_extractor import Feature
from case_schema import TestCase, TestCaseCollection  # 复用 Day 9

logger = setup_logger("ai_test_agent")

# ============================================================
# 数据结构
# ============================================================

@dataclass
class FeatureTestSuite:
    """单个功能点的测试用例套件"""
    feature: Feature                            # 来源功能点
    test_cases: list[TestCase]                  # 测试用例列表（Pydantic 对象）
    generation_mode: str = "schema"             # 生成模式（schema / json_fallback）
    raw_dict: dict | None = None                # 原始 dict（降级时保存）


@dataclass
class GenerationResult:
    """完整生成结果"""
    suites: list[FeatureTestSuite]
    total_cases: int
    success_count: int          # 成功生成的功能点数
    failed_count: int           # 失败的功能点数
    elapsed_seconds: float

# ============================================================
# Prompt 模板
# ============================================================

CASE_GENERATOR_SYSTEM_PROMPT = (
    "你是一名有 10 年经验的资深软件测试工程师。"
    "你精通等价类划分、边界值分析、场景法、错误推测法等测试设计技术。"
    "你生成的测试用例覆盖全面、优先级合理、步骤清晰可执行。"
)

CASE_GENERATOR_PROMPT = """请为以下功能设计完整的测试用例。

【功能名称】{feature_name}
【功能描述】{feature_description}
【子功能】{sub_features}
【输入字段】{inputs}
【约束条件】{constraints}

请生成覆盖以下类型的测试用例：
- **正向测试**（P0）：正常输入，功能正确执行；
  必须覆盖主流程完成后的后续行为（如注册成功后自动登录并跳转首页）
- **边界测试**（P1）：输入字段和约束条件中的数值边界
  （刚好满足 / 刚好不满足 / =边界值±1）
- **异常测试**（P1）：空值、类型错误、格式错误、违反业务规则
  （如手机号不合法、年龄超出范围、权限不足等）
- **安全测试**（P1）：SQL注入、XSS、越权访问等（如果适用）

要求：
1. 每条用例必须有明确的 preconditions（前置条件），描述执行前系统所处的状态；若无前置条件则填"无"
2. 输入字段描述和约束条件中的**每个数值约束**生成至少 2 个边界用例
3. 每个输入字段生成至少 1 个格式错误用例（类型不匹配、不符合业务规则）
4. 每个必填字段生成至少 1 个「缺失」用例
5. 正向用例必须覆盖功能完成的后续行为（如跳转、状态变更）
6. 步骤描述清晰，预期结果明确可验证
7. 优先使用等价类划分减少冗余用例

请输出 JSON 格式，字段为 feature_name 和 test_cases 数组。"""

# ============================================================
# TestCaseGenerator
# ============================================================

class TestCaseGenerator:
    """
    基于功能点的测试用例生成器

    职责：
    1. 为每个功能点独立生成测试用例
    2. 优先用 Schema 模式（generate_schema），自动降级到 JSON 提取
    3. 汇总所有功能点的用例，返回完整结果

    使用示例：
        generator = TestCaseGenerator()
        suite = generator.generate_for_feature(feature)
        print(f"生成了 {len(suite.test_cases)} 个测试用例")
    """

    def __init__(self, temperature: float = 0.2):
        self.client = SafeGeminiClient()
        self.temperature = temperature
        logger.info("TestCaseGenerator 初始化完成")

    def generate_for_feature(self, feature: Feature) -> FeatureTestSuite:
        """
        为单个功能点生成测试用例

        Args:
            feature: 功能点对象

        Returns:
            FeatureTestSuite（包含生成的测试用例）
        """
        logger.info(f"为功能点生成用例: {feature.name}")

        # 1. 构建 Prompt
        prompt = CASE_GENERATOR_PROMPT.format(
            feature_name=feature.name,
            feature_description=feature.description,
            sub_features=", ".join(feature.sub_features) if feature.sub_features else "无",
            inputs="\n".join(f"- " + inp for inp in feature.inputs) if feature.inputs else "未明确指定",
            constraints="\n".join(f"- " + c for c in feature.constraints) if feature.constraints else "未明确指定",
        )

        # 2. 调用 Gemini（优先 Schema 模式）
        result = self.client.generate_schema(
            prompt=prompt,
            schema_class=TestCaseCollection,
            system_instruction=CASE_GENERATOR_SYSTEM_PROMPT,
            temperature=self.temperature,
            fallback_to_json=True,  # Schema 失败时自动降级
        )

        # 3. 处理结果
        if isinstance(result, TestCaseCollection):
            # Schema 模式成功 — 返回 Pydantic 对象
            logger.info(f"✓ {feature.name}: {len(result.test_cases)} 个用例 (Schema)")
            return FeatureTestSuite(
                feature=feature,
                test_cases=result.test_cases,
                generation_mode="schema",
            )

        elif isinstance(result, dict):
            # 降级到 JSON 模式 — 需要手动构造 TestCase 对象
            cases_data = result.get("test_cases", [])
            test_cases = []
            for tc_data in cases_data:
                if isinstance(tc_data, dict):
                    try:
                        test_case = TestCase(**tc_data)
                        test_cases.append(test_case)
                    except Exception as e:
                        logger.warning(f"跳过无效用例: {tc_data.get('id', '?')} — {e}")
                elif isinstance(tc_data, TestCase):
                    test_cases.append(tc_data)

            logger.info(f"✓ {feature.name}: {len(test_cases)} 个用例 (JSON fallback)")
            return FeatureTestSuite(
                feature=feature,
                test_cases=test_cases,
                generation_mode="json_fallback",
                raw_dict=result,
            )

        else:
            # 完全失败
            logger.error(f"✗ {feature.name}: 生成失败，返回类型={type(result).__name__}")
            return FeatureTestSuite(
                feature=feature,
                test_cases=[],
                generation_mode="failed",
            )

    def generate_all(self, features: list[Feature], verbose: bool = True) -> GenerationResult:
        """
        为所有功能点生成测试用例（顺序执行，带进度显示）

        Args:
            features: 功能点列表
            verbose: 是否显示进度

        Returns:
            GenerationResult（汇总所有结果）
        """
        start_time = time.time()
        suites = []
        success_count = 0
        failed_count = 0

        total = len(features)
        for i, feature in enumerate(features):
            if verbose:
                print(f"[{i+1}/{total}] 正在为「{feature.name}」生成测试用例...")

            try:
                suite = self.generate_for_feature(feature)
                suites.append(suite)
                if suite.test_cases:
                    success_count += 1
                else:
                    failed_count += 1
            except Exception as e:
                logger.error(f"功能点 {feature.name} 生成异常: {e}")
                suites.append(FeatureTestSuite(
                    feature=feature,
                    test_cases=[],
                    generation_mode="failed",
                ))
                failed_count += 1

        elapsed = time.time() - start_time
        total_cases = sum(len(s.test_cases) for s in suites)

        logger.info(f"全部生成完成: {total} 功能点, {total_cases} 个用例, "
                    f"成功 {success_count}, 失败 {failed_count}, 耗时 {elapsed:.1f}s")

        return GenerationResult(
            suites=suites,
            total_cases=total_cases,
            success_count=success_count,
            failed_count=failed_count,
            elapsed_seconds=elapsed,
        )


# ============================================================
# 自检
# ============================================================

def test_case_generator():
    """测试 TestCaseGenerator"""
    print("=" * 60)
    print("🧪 测试 TestCaseGenerator")
    print("=" * 60)

    generator = TestCaseGenerator()

    # 构造测试功能点
    test_feature = Feature(
        name="用户登录",
        description="用户通过手机号和密码登录系统",
        sub_features=["手机号登录", "记住我"],
        inputs=[
            "手机号-11位数字，以1开头，必填",
            "密码-不少于8位，必填，必须含数字和字母",
        ],
        constraints=[
            "密码错误超过5次锁定30分钟",
            "登录成功返回JWT Token",
        ],
        outputs=["JWT Token", "用户信息"],
    )

    suite = generator.generate_for_feature(test_feature)

    print(f"功能: {test_feature.name}")
    print(f"生成模式: {suite.generation_mode}")
    print(f"用例数: {len(suite.test_cases)}")

    for tc in suite.test_cases[:5]:
        print(f"  [{tc.priority}] {tc.id} - {tc.title} [{tc.type}]")

    # 验证
    assert len(suite.test_cases) > 0, "❌ 未生成任何测试用例"
    # 验证 Pydantic 类型正确
    test_case = suite.test_cases[0]
    assert isinstance(test_case, TestCase), f"❌ 不是 TestCase 类型: {type(test_case)}"
    assert len(test_case.id) > 0, "❌ 用例 ID 为空"
    assert len(test_case.steps) > 0, "❌ 用例步骤为空"

    # 测试 generate_all
    print("\n--- 测试 generate_all ---")
    result = generator.generate_all([test_feature], verbose=True)

    print(f"\n汇总: 总用例 {result.total_cases}, 成功 {result.success_count}, "
          f"失败 {result.failed_count}, 耗时 {result.elapsed_seconds:.1f}s")

    assert result.total_cases > 0, "❌ generate_all 总用例数为 0"

    print("\n✅ TestCaseGenerator 测试通过！")


if __name__ == "__main__":
    test_case_generator()