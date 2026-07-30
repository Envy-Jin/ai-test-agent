"""
src/agent/prompt_lab.py —— Prompt 工程实验室

Day 9 核心练习：五大 Prompt 技巧的对比实验
通过「同一需求 + 不同 Prompt」直观感受 Prompt 的力量
"""
from google import genai
from google.genai import types
import os
import json
from dotenv import load_dotenv

# # 代理配置（按你的实际端口修改）
# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-3.1-flash-lite"

# 统一用的测试需求
REQUIREMENT = (
    "用户注册功能：需要手机号验证码，"
    "密码不少于8位且必须包含数字和字母，"
    "同一手机号不可重复注册，用户名长度3-20个字符。"
)

# ============================================================
# 实验 0：朴素 Prompt（baseline 基线）
# ============================================================

def naive_prompt():
    """最朴素的问法——啥技巧都不用"""
    print("=" * 60)
    print("🧪 实验 0：朴素 Prompt（基线）")
    print("=" * 60)

    prompt = f"帮我写测试用例：{REQUIREMENT}"
    print(f"Prompt: {prompt}\n")

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(temperature=0.2),
    )
    print("Gemini 输出：")
    print(response.text)
    print("\n" + "-" * 60)
    print("💡 观察点：输出是自由文本，格式不固定，字段不齐全，无法直接被程序解析")


# ============================================================
# 实验 A：朴素 + 强制 JSON（Day 8 已学）
# ============================================================

def naive_json_prompt():
    """朴素 Prompt + JSON 模式，但没说清楚要哪些字段"""
    print("\n" + "=" * 60)
    print("🧪 实验 A：朴素 Prompt + JSON 模式")
    print("=" * 60)

    prompt = f"帮我写测试用例：{REQUIREMENT}\n请以 JSON 格式输出"
    print(f"Prompt: {prompt}\n")

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )
    data = json.loads(response.text)
    print("Gemini 输出（已解析为 dict）：")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:500])
    print("\n" + "-" * 60)
    # print("💡 观察点：虽然是 JSON 了，但字段名和结构不固定——")
    # print("   每次跑可能 keys 都不一样，下游程序没法稳定消费")


# ============================================================
# 技巧一：角色设定 Role Prompting
# ============================================================

def role_prompting():
    """对比：无角色 vs 资深测试工程师角色"""
    print("\n" + "=" * 60)
    print("🧪 技巧一：角色设定 Role Prompting")
    print("=" * 60)

    # 版本 A：无角色（和实验 0 一样，作对照）
    print("\n--- 版本 A：无角色设定 ---")
    resp_a = client.models.generate_content(
        model=MODEL,
        contents=f"帮我分析这个需求的测试重点：{REQUIREMENT}",
        config=types.GenerateContentConfig(temperature=0.2),
    )
    print(resp_a.text[:400])

    # 版本 B：有角色（system_instruction）
    print("\n--- 版本 B：资深测试工程师角色 ---")
    system_prompt = (
        "你是一名有 10 年经验的资深软件测试工程师，"
        "精通等价类划分、边界值分析、场景法等测试设计技术。"
        "你擅长从需求文档中识别风险点，"
        "生成的测试用例覆盖正向、边界、异常三大类，"
        "并标注优先级（P0/P1/P2）。"
        "回答要专业、简洁、结构清晰。"
    )
    resp_b = client.models.generate_content(
        model=MODEL,
        contents=f"帮我分析这个需求的测试重点：{REQUIREMENT}",
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
        ),
    )
    print(resp_b.text[:400])

    # print("\n" + "-" * 60)
    # print("💡 观察点：")
    # print("   - 版本 B 是否更专业？是否提到了边界值/异常场景？")
    # print("   - 版本 B 是否自动给出了优先级分类？")
    # print("   - system_instruction 让 AI '始终以这个角色' 回答")

# ============================================================
# 技巧二：Few-Shot 少样本示例
# ============================================================

def few_shot_prompting():
    """用示例教 AI 按固定格式输出测试用例"""
    print("\n" + "=" * 60)
    print("🧪 技巧二：Few-Shot 少样本示例")
    print("=" * 60)

    system_prompt = (
        "你是一名资深软件测试工程师。"
        "请严格按照示例的格式生成测试用例。"
    )

    few_shot_prompt = f"""请参考以下示例，为新的需求生成测试用例。

【示例 1】
需求：用户登录功能，支持手机号和邮箱登录，密码不少于8位
输出：
{{
  "test_cases": [
    {{
      "id": "TC001",
      "title": "手机号正常登录",
      "type": "正向",
      "priority": "P0",
      "steps": ["输入有效手机号", "输入正确密码", "点击登录"],
      "expected": "登录成功，跳转到首页"
    }},
    {{
      "id": "TC002",
      "title": "密码少于8位",
      "type": "边界",
      "priority": "P1",
      "steps": ["输入有效手机号", "输入7位密码", "点击登录"],
      "expected": "提示密码格式错误，登录失败"
    }},
    {{
      "id": "TC003",
      "title": "手机号格式错误",
      "type": "异常",
      "priority": "P1",
      "steps": ["输入非数字字符的手机号", "输入正确密码", "点击登录"],
      "expected": "提示手机号格式错误，登录失败"
    }}
  ]
}}

【示例 2】
需求：搜索功能，支持关键词搜索，结果不超过1000条
输出：
{{
  "test_cases": [
    {{
      "id": "TC001",
      "title": "正常关键词搜索",
      "type": "正向",
      "priority": "P0",
      "steps": ["输入有效关键词", "点击搜索"],
      "expected": "返回相关结果，数量不超过1000条"
    }},
    {{
      "id": "TC002",
      "title": "搜索结果恰好1000条边界",
      "type": "边界",
      "priority": "P1",
      "steps": ["输入高频关键词", "点击搜索"],
      "expected": "返回结果正好1000条或提示结果过多"
    }}
  ]
}}

【现在请生成】
需求：{REQUIREMENT}
输出："""

    print(f"Few-Shot Prompt（含2个示例）已构建\n")

    response = client.models.generate_content(
        model=MODEL,
        contents=few_shot_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
            response_mime_type="application/json",
        ),
    )
    data = json.loads(response.text)

    print("Few-Shot 输出：")
    print(json.dumps(data, ensure_ascii=False, indent=2)[:600])

    # 验证格式是否稳定
    cases = data.get("test_cases", [])
    print(f"\n📊 生成用例数: {len(cases)}")
    for c in cases:
        print(f"   {c.get('id')} | {c.get('type')} | {c.get('priority')} | {c.get('title')}")

    print("\n" + "-" * 60)
    # print("💡 观察点：")
    # print("   - 字段名是否和示例完全一致？（id/title/type/priority/steps/expected）")
    # print("   - type 是否覆盖了 正向/边界/异常？")
    # print("   - 对比实验 A，格式稳定性是否大幅提升？")


# ============================================================
# 技巧三：思维链 Chain of Thought
# ============================================================

def cot_prompting():
    """让 AI 分步分析需求，再生成用例"""
    print("\n" + "=" * 60)
    print("🧪 技巧三：思维链 Chain of Thought")
    print("=" * 60)

    system_prompt = (
        "你是一名资深软件测试工程师。"
        "请严格按照指定的步骤分析需求，逐步推理后再输出最终结果。"
    )

    cot_prompt = f"""请按以下步骤分析需求并生成测试用例。

需求：{REQUIREMENT}

请严格按以下步骤思考（先输出分析过程，最后输出用例）：

## 第 1 步：提取核心功能点
列出需求中所有功能点和子功能。

## 第 2 步：识别输入与约束
列出每个输入字段及其约束条件（格式、长度、范围等）。

## 第 3 步：列出正常场景
针对每个功能点，列出正常使用的场景。

## 第 4 步：列出边界条件
针对每个约束，列出边界值（最小值、最大值、刚好满足、刚好不满足）。

## 第 5 步：列出异常场景
列出非法输入、空值、超长、特殊字符等异常情况。

## 第 6 步：输出完整测试用例
基于以上分析，输出 JSON 格式的测试用例列表，格式如下：
{{
  "analysis": "简要分析总结",
  "test_cases": [
    {{"id": "TC001", "title": "...", "type": "正向|边界|异常", "priority": "P0|P1|P2", "steps": [...], "expected": "..."}}
  ]
}}"""

    response = client.models.generate_content(
        model=MODEL,
        contents=cot_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
        ),
    )
    print("CoT 完整输出（含思考过程）：")
    print(response.text[:1200])

    print("\n" + "-" * 60)
    # print("💡 观察点：")
    # print("   - AI 是否真的分步思考了？分析过程是否合理？")
    # print("   - 经过思考后，用例覆盖度是否比直接生成更高？")
    # print("   - 边界条件是否更精确（如密码7位/8位/用户名2位/3位/20位/21位）？")


# ============================================================
# 技巧四：结构化输出 JSON Schema（Pydantic）
# ============================================================

# 导入 Schema（确保 case_schema.py 在同目录或 src/agent 下可导入
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
from case_schema import TestCaseCollection


def schema_prompting():
    """用 Pydantic Schema 锁定输出结构"""
    print("\n" + "=" * 60)
    print("🧪 技巧四：结构化输出 JSON Schema")
    print("=" * 60)

    system_prompt = (
        "你是一名资深软件测试工程师。"
        "请为给定需求生成测试用例，覆盖正向、边界、异常三类。"
    )

    prompt = f"""请为以下需求生成测试用例，覆盖正向、边界、异常场景。

需求：{REQUIREMENT}

要求：
- 每个约束条件至少有 1 个边界用例
- 异常用例覆盖空值、格式错误、超长输入
- 优先级 P0 给正向核心场景，P1 给边界和异常"""

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
            response_mime_type="application/json",
            response_schema=TestCaseCollection,  # 关键：传入 Pydantic 模型
        ),
    )

    # response_schema 保证输出严格符合结构，可直接反序列化为对象
    collection = TestCaseCollection.model_validate_json(response.text)

    print(f"功能名称: {collection.feature_name}")
    print(f"用例数量: {len(collection.test_cases)}\n")

    for tc in collection.test_cases:
        print(f"  {tc.id} [{tc.priority}] [{tc.type}] {tc.title}")
        print(f"     步骤: {' → '.join(tc.steps)}")
        print(f"     预期: {tc.expected}\n")

    # 验证：可以直接像对象一样访问字段
    for tc in collection.test_cases:
        assert tc.type in ["正向", "边界", "异常"]  # 枚举保证
        assert tc.priority in ["P0", "P1", "P2"]
    print("✅ 所有用例字段校验通过！")

    print("-" * 60)
    # print("💡 观察点：")
    # print("   - type 只会是 正向/边界/异常 三选一（Literal 枚举锁定）")
    # print("   - priority 只会是 P0/P1/P2（枚举锁定）")
    # print("   - 字段名、类型完全固定，可直接 TestCaseCollection 对象消费")
    # print("   - 对比实验 A 的'格式不稳定'，现在 100% 稳定！")


# ============================================================
# 技巧五：迭代优化
# ============================================================

def iterative_refinement():
    """模拟真实工作中的 Prompt 迭代过程"""
    print("\n" + "=" * 60)
    print("🧪 技巧五：迭代优化")
    print("=" * 60)

    system_prompt = (
        "你是一名资深软件测试工程师。"
        "请为给定需求生成测试用例。"
    )

    # ===== 第 1 轮：基础 Prompt =====
    print("\n--- 第 1 轮：基础 Prompt ---")
    v1_prompt = f"为以下需求生成测试用例：{REQUIREMENT}"
    resp1 = client.models.generate_content(
        model=MODEL,
        contents=v1_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
            response_mime_type="application/json",
            response_schema=TestCaseCollection,
        ),
    )
    c1 = TestCaseCollection.model_validate_json(resp1.text)
    print(f"生成 {len(c1.test_cases)} 个用例")
    boundary_count = sum(1 for tc in c1.test_cases if tc.type == "边界")
    print(f"其中边界用例: {boundary_count} 个")

    # ===== 第 2 轮：发现边界用例不够，追加要求 =====
    print("\n--- 第 2 轮：补充边界条件要求 ---")
    v2_prompt = f"""为以下需求生成测试用例。

需求：{REQUIREMENT}

特别注意：
- 对每个数值约束，生成「刚好满足」和「刚好不满足」两个边界用例
  例如「密码不少于8位」→ 7位（不满足）和 8位（满足）
  例如「用户名3-20个字符」→ 2位、3位、20位、21位
- 异常用例要包含：空值、SQL注入字符、超长输入
"""
    resp2 = client.models.generate_content(
        model=MODEL,
        contents=v2_prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
            response_mime_type="application/json",
            response_schema=TestCaseCollection,
        ),
    )
    c2 = TestCaseCollection.model_validate_json(resp2.text)
    boundary_count2 = sum(1 for tc in c2.test_cases if tc.type == "边界")
    print(f"生成 {len(c2.test_cases)} 个用例")
    print(f"其中边界用例: {boundary_count2} 个（第1轮只有 {boundary_count} 个）")

    # ===== 第 3 轮：用追问方式继续优化（多轮对话） =====
    print("\n--- 第 3 轮：多轮对话追问优化 ---")
    chat = client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
        ),
    )
    # 先发第 2 轮的 prompt
    chat.send_message(v2_prompt)
    # 追问：补充安全测试
    resp3 = chat.send_message(
        "以上用例中缺少安全性测试。请补充以下安全场景的测试用例："
        "1.验证码爆破 2.密码暴力破解 3.批量注册防护。"
        "只输出新增的用例。"
    )
    print("追问补充的安全用例：")
    print(resp3.text[:600])

    print("\n" + "-" * 60)
    # print("💡 迭代优化的三种方式：")
    # print("   1. 改 Prompt 本身（加约束、加示例、加步骤）")
    # print("   2. 用追问补充（多轮对话，基于已有结果继续优化）")
    # print("   3. 调参数（temperature 调低让输出更稳定）")


if __name__ == "__main__":
    # naive_prompt()
    # naive_json_prompt()
    # role_prompting()
    # few_shot_prompting()
    # cot_prompting()
    # schema_prompting()
    iterative_refinement()
    # print("\n✅ 认知实验完成！接下来用五大技巧逐个改进")

