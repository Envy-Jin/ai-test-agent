"""
src/agent/case_generator.py —— 高质量测试用例生成器

融合五大 Prompt 技巧：
1. 角色设定（system_instruction）
2. Few-Shot（内置示例）
3. 思维链（分步分析）
4. 结构化输出（Pydantic Schema）
5. 迭代优化（refine 方法）
"""

from google import genai
from google.genai import types
import os
import json
from dotenv import load_dotenv
from case_schema import TestCaseCollection, TestCase

# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

load_dotenv()
_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-3.1-flash-lite"

SYSTEM_PROMPT = (
    "你是一名有 10 年经验的资深软件测试工程师，"
    "精通等价类划分、边界值分析、场景法等测试设计技术。"
    "你生成的测试用例覆盖正向、边界、异常三大类，"
    "对每个数值约束都生成「刚好满足」和「刚好不满足」的边界用例，"
    "并合理标注优先级（P0/P1/P2）。"
)

# Few-Shot 示例（精简版）
FEW_SHOT = """
参考以下示例格式：
需求：用户登录，密码不少于8位
用例：TC001 正向 P0 "正常登录" | TC002 边界 P1 "密码7位" | TC003 异常 P1 "空密码"
"""

class CaseGenerator:
    """测试用例生成器"""

    def __init__(self, model: str = MODEL):
        self.model = model

    def generate(self, requirement: str) -> TestCaseCollection:
        """
        根据需求生成测试用例（融合角色 + Few-Shot + CoT + Schema）

        Args:
            requirement: 需求文本

        Returns:
            TestCaseCollection 对象
        """
        prompt = f"""{FEW_SHOT}

请按以下步骤分析并生成测试用例：

需求：{requirement}

分析步骤：
1. 提取核心功能点
2. 识别每个输入字段的约束条件
3. 为每个约束生成边界用例（刚好满足 + 刚好不满足）
4. 列出异常场景（空值、格式错误、超长、特殊字符）
5. 汇总输出测试用例

要求：
- 正向用例标 P0，边界和异常用例标 P1
- 每个用例的 steps 要具体可执行
- expected 要可验证"""

        response = _client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=TestCaseCollection,
            ),
        )
        return TestCaseCollection.model_validate_json(response.text)

    def refine(self, collection: TestCaseCollection, instruction: str) -> str:
        """
        基于已有用例，用自然语言追问来优化补充

        Args:
            collection: 已生成的用例集合
            instruction: 优化指令，如"补充安全性测试用例"

        Returns:
            AI 的补充说明文本
        """
        chat = _client.chats.create(
            model=self.model,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.2,
            ),
        )
        # 把已有用例作为上下文
        chat.send_message(
            f"需求：{collection.feature_name}\n"
            f"已有用例：{collection.model_dump_json(indent=2)}"
        )
        resp = chat.send_message(instruction)
        return resp.text

    def to_markdown(self, collection: TestCaseCollection) -> str:
        """把用例集合转为 Markdown 表格"""
        lines = [f"# {collection.feature_name} 测试用例\n"]
        lines.append("| ID | 类型 | 优先级 | 标题 | 步骤 | 预期结果 |")
        lines.append("|----|------|--------|------|------|----------|")
        for tc in collection.test_cases:
            steps = "<br>".join(tc.steps)
            lines.append(
                f"| {tc.id} | {tc.type} | {tc.priority} | {tc.title} | {steps} | {tc.expected} |"
            )
        return "\n".join(lines)


# ============================================================
# 自检
# ============================================================
if __name__ == "__main__":
    print("🧪 测试 CaseGenerator...\n")

    gen = CaseGenerator()

    requirement = (
        "用户注册功能：需要手机号验证码，"
        "密码不少于8位且必须包含数字和字母，"
        "同一手机号不可重复注册，用户名长度3-20个字符。"
    )

    # 生成
    print("生成测试用例中...")
    collection = gen.generate(requirement)
    print(f"\n功能: {collection.feature_name}")
    print(f"用例数: {len(collection.test_cases)}")

    # 统计
    types_count = {}
    for tc in collection.test_cases:
        types_count[tc.type] = types_count.get(tc.type, 0) + 1
    print(f"类型分布: {types_count}")

    # 打印 Markdown
    print("\n" + gen.to_markdown(collection))

    # 迭代优化
    print("\n\n--- 迭代优化：补充安全测试 ---")
    supplement = gen.refine(collection, "请补充 SQL注入、XSS、暴力破解相关的安全性测试用例说明")
    print(supplement[:500])

    print("\n✅ CaseGenerator 测试通过！")    