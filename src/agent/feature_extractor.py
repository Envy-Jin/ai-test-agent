"""
src/agent/feature_extractor.py —— 功能点提取器

Day 13 核心模块之二：用 Gemini 分析需求文档，提取结构化的功能点列表。

使用 SafeGeminiClient 作为底层调用，extract_json 作为提取策略，
每个功能点包含：名称、描述、子功能、输入字段、约束条件。
"""

import json
from dataclasses import dataclass, field, asdict
from safe_gemini_client import SafeGeminiClient
from json_extractor import extract_json_with_fallback
from logger_config import setup_logger

logger = setup_logger("ai_test_agent")

# ============================================================
# 数据结构定义
# ============================================================

@dataclass
class Feature:
    """单个功能点"""
    name: str                       # 功能名称
    description: str                # 功能描述
    sub_features: list[str] = field(default_factory=list)  # 子功能
    constraints: list[str] = field(default_factory=list)   # 约束条件
    inputs: list[str] = field(default_factory=list)        # 输入字段
    outputs: list[str] = field(default_factory=list)       # 预期输出


@dataclass
class FeatureExtractionResult:
    """功能提取结果"""
    features: list[Feature]
    raw_analysis: str               # 原始分析文本（用于调试）
    success: bool
    error_message: str = ""

# ============================================================
# FeatureExtractor
# ============================================================

FEATURE_EXTRACTOR_SYSTEM_PROMPT = (
    "你是一名资深的软件需求分析师，有 15 年软件测试经验。"
    "你擅长从需求文档中提取结构化的功能点，"
    "识别每个功能的输入、输出、约束和子功能。"
    "你的分析全面、精准、可直接用于测试用例设计。"
)

FEATURE_EXTRACTOR_PROMPT = """请分析以下需求文档，提取所有功能点。

需求文档：
{requirement_text}

请按以下思维链逐步分析：
1. **识别核心功能**：需求文档描述了哪些主要功能？
2. **识别子功能**：每个核心功能下有哪些子功能？
3. **识别输入字段**：每个功能接收哪些输入？（含字段名和约束）
4. **识别预期输出**：每个功能的预期输出是什么？
5. **识别约束条件**：有哪些业务规则、限制条件、非功能需求？

最终请输出如下 JSON 格式（不要添加任何额外文字）：
{{
  "features": [
    {{
      "name": "功能名称，如「用户登录」",
      "description": "功能的一句话描述",
      "sub_features": ["子功能1", "子功能2"],
      "inputs": [
        "字段名（含约束，如：手机号-11位数字，以1开头）",
        ...
      ],
      "outputs": [
        "预期输出描述",
        ...
      ],
      "constraints": [
        "业务规则或限制条件",
        ...
      ]
    }}
  ],
  "summary": "需求文档的整体概要（一句话）",
  "complexity": "low/medium/high",
  "estimated_test_scope": "预估的测试范围描述"
}}

注意：
- 每个功能的 inputs 要写清楚字段约束（如长度、格式、是否必填）
- 每个功能的 constraints 要写清楚业务规则
- sub_features 可以把同类型的变体放一起（如「手机号登录」「邮箱登录」）
"""

class FeatureExtractor:
    """
    功能点提取器

    职责：
    1. 接收需求文本 → 调用 Gemini 分析
    2. 从 LLM 输出中提取功能点 JSON
    3. 自动降级：单次大需求提取失败 → 分段提取

    使用示例：
        extractor = FeatureExtractor()
        result = extractor.extract(requirement_text)
        for feature in result.features:
            print(f"{feature.name}: {len(feature.sub_features)} 个子功能")
    """

    def __init__(self, temperature: float = 0.2):
        self.client = SafeGeminiClient()
        self.temperature = temperature
        logger.info("FeatureExtractor 初始化完成")

    def extract(self, requirement_text: str) -> FeatureExtractionResult:
        """
        从需求文本中提取功能点

        Args:
            requirement_text: 需求文档的纯文本

        Returns:
            FeatureExtractionResult（包含功能点列表和元信息）
        """
        logger.info(f"FeatureExtractor.extract() 开始: 文本长度={len(requirement_text)}")

        # 1. 构建 Prompt
        prompt = FEATURE_EXTRACTOR_PROMPT.format(requirement_text=requirement_text)

        # 2. 用 SafeGeminiClient 调用 Gemini
        raw_text = self.client.generate(
            prompt=prompt,
            system_instruction=FEATURE_EXTRACTOR_SYSTEM_PROMPT,
            temperature=self.temperature,
        )

        # 如果是系统错误提示，直接返回失败
        if raw_text.startswith("[系统提示]"):
            logger.error(f"功能提取失败: {raw_text}")
            return FeatureExtractionResult(
                features=[],
                raw_analysis=raw_text,
                success=False,
                error_message=raw_text,
            )

        # 3. 从 LLM 输出中提取 JSON
        data = extract_json_with_fallback(
            raw_text,
            fallback={"features": [], "summary": "提取失败", "complexity": "unknown", "estimated_test_scope": ""},
        )

        # 4. 验证必需字段
        if "features" not in data or not data.get("features"):
            logger.warning("LLM 输出中缺少 features 字段，尝试兜底")
            # 兜底：把整个输出当作一个功能点
            data["features"] = [{
                "name": "需求分析",
                "description": requirement_text[:100],
                "sub_features": [],
                "inputs": [],
                "outputs": [],
                "constraints": [],
            }]

        # 5. 构造 Feature 对象列表
        features = []
        for f in data.get("features", []):
            if isinstance(f, dict):
                feature = Feature(
                    name=f.get("name", "未命名功能"),
                    description=f.get("description", ""),
                    sub_features=f.get("sub_features", []),
                    constraints=f.get("constraints", []),
                    inputs=f.get("inputs", []),
                    outputs=f.get("outputs", []),
                )
                features.append(feature)

        logger.info(f"功能提取完成: {len(features)} 个功能点, "
                    f"复杂度: {data.get('complexity', 'unknown')}")

        return FeatureExtractionResult(
            features=features,
            raw_analysis=raw_text[:500] + "..." if len(raw_text) > 500 else raw_text,
            success=True,
        )

    def extract_from_file(self, file_path: str) -> FeatureExtractionResult:
        """
        从需求文档文件提取功能点（便捷方法）

        Args:
            file_path: 需求文档路径

        Returns:
            FeatureExtractionResult
        """
        from doc_reader import DocReader

        reader = DocReader()
        try:
            text = reader.parse_file(file_path)  # 抛异常时跳到 except
        except (FileNotFoundError, ValueError) as e:
            return FeatureExtractionResult(
                features=[],
                raw_analysis="",
                success=False,
                error_message=f"无法读取文件 {file_path}: {e}",
            )
        return self.extract(text)    


# ============================================================
# 自检
# ============================================================

def test_feature_extractor():
    """测试 FeatureExtractor"""
    print("=" * 60)
    print("🧪 测试 FeatureExtractor")
    print("=" * 60)

    extractor = FeatureExtractor()       

        # 测试需求文本
    test_requirement = """
用户注册功能：新用户通过手机号验证码注册。
输入：手机号（11位）、验证码（6位数字）、密码（8位+字母数字）、用户名（3-20字符）
约束：同手机号不可重复注册、同IP每小时限3次、密码不可为常见弱密码
"""

    result = extractor.extract(test_requirement)

    print(f"提取成功: {result.success}")
    print(f"功能点数: {len(result.features)}")
    print(f"错误信息: {result.error_message}")

    for i, feature in enumerate(result.features):
        print(f"\n--- 功能点 {i+1}: {feature.name} ---")
        print(f"  描述: {feature.description}")
        print(f"  子功能: {feature.sub_features}")
        print(f"  输入字段: {feature.inputs}")
        print(f"  约束条件: {feature.constraints}")
        print(f"  预期输出: {feature.outputs}")

    # 验证
    assert result.success, f"❌ 功能提取失败: {result.error_message}"
    assert len(result.features) > 0, "❌ 未提取到任何功能点"

    # 验证 Feature 对象结构
    for f in result.features:
        assert isinstance(f.name, str) and len(f.name) > 0, "❌ 功能名称无效"
        assert isinstance(f.inputs, list), "❌ inputs 不是 list"

    print("\n✅ FeatureExtractor 测试通过！")


if __name__ == "__main__":
    test_feature_extractor()    