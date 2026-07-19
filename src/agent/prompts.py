"""
src/agent/prompts.py —— Prompt 模板集中管理

把 Prompt 当作「代码资产」管理，方便复用和迭代
"""

# 角色设定
SYSTEM_TEST_ENGINEER = (
    "你是一名有 10 年经验的资深软件测试工程师，"
    "精通等价类划分、边界值分析、场景法等测试设计技术。"
    "你生成的测试用例覆盖正向、边界、异常三大类，"
    "对每个数值约束都生成「刚好满足」和「刚好不满足」的边界用例，"
    "并合理标注优先级（P0/P1/P2）。"
)

SYSTEM_BUG_ANALYST = (
    "你是一名资深测试专家，擅长分析 Bug 报告，"
    "能快速定位根因、给出复现步骤和回归测试建议。"
)

# Few-Shot 示例（完整 JSON，与 TestCaseCollection Schema 一致）
FEW_SHOT_CASES = """
【示例】
需求：用户登录功能，支持手机号登录，密码不少于8位

输出：
{
  "feature_name": "用户登录",
  "analysis_summary": "约束：密码≥8位。边界：7位不满足、8位满足。异常：空密码、格式错误手机号。",
  "test_cases": [
    {
      "id": "TC001",
      "title": "手机号密码正常登录",
      "type": "正向",
      "priority": "P0",
      "steps": ["输入有效手机号", "输入8位以上正确密码", "点击登录"],
      "expected": "登录成功，跳转到首页"
    },
    {
      "id": "TC002",
      "title": "密码7位边界不满足",
      "type": "边界",
      "priority": "P1",
      "steps": ["输入有效手机号", "输入7位密码", "点击登录"],
      "expected": "提示密码格式错误，登录失败"
    },
    {
      "id": "TC003",
      "title": "空密码异常",
      "type": "异常",
      "priority": "P1",
      "steps": ["输入有效手机号", "密码留空", "点击登录"],
      "expected": "提示密码不能为空，登录失败"
    }
  ]
}
"""

# 测试用例生成模板（含思维链）
CASE_GENERATION_TEMPLATE = """{few_shot}

请严格参考示例的 JSON 结构与字段名，为以下需求生成测试用例。

需求：{requirement}

请先在 analysis_summary 中简要完成以下分析（每个要点一行即可）：
1. 提取核心功能点
2. 识别每个输入字段的约束条件
3. 列出边界值（刚好满足 + 刚好不满足）
4. 列出异常场景（空值、格式错误、超长、特殊字符）

然后在 test_cases 中输出完整用例。

要求：
- feature_name 从需求中提取
- 正向用例标 P0，边界和异常用例标 P1
- 每个用例的 steps 至少 1 步，要具体可执行
- expected 要可验证
- id 从 TC001 起连续编号"""

REFINE_CONTEXT_TEMPLATE = """原始需求：
{requirement}

功能名称：{feature_name}

已有用例（JSON）：
{existing_cases}

已有用例 id 列表：{existing_ids}
新增用例 id 请从 {next_id} 起连续编号，不要与已有 id 重复。"""

REFINE_INSTRUCTION_TEMPLATE = """{instruction}

请只输出本次新增的用例（不要重复已有用例），并在 summary 中说明补充了哪些测试场景。"""

# Bug 分析模板
BUG_ANALYSIS_TEMPLATE = """请分析以下 Bug 报告：

Bug 报告：
{bug_report}

请按以下步骤分析：
1. 一句话总结 Bug
2. 判断 Bug 类型（功能/性能/UI/安全/兼容性）
3. 分析根因
4. 给出精简复现步骤
5. 建议需要补充的测试用例
6. 建议回归测试范围
"""


def build_case_prompt(requirement: str) -> str:
    """构建测试用例生成的完整 Prompt"""
    return CASE_GENERATION_TEMPLATE.format(
        few_shot=FEW_SHOT_CASES,
        requirement=requirement,
    )


def build_refine_context(
    requirement: str,
    feature_name: str,
    existing_cases_json: str,
    existing_ids: list[str],
    next_id: str,
) -> str:
    """构建 refine 多轮对话的上下文消息"""
    return REFINE_CONTEXT_TEMPLATE.format(
        requirement=requirement,
        feature_name=feature_name,
        existing_cases=existing_cases_json,
        existing_ids=", ".join(existing_ids) or "（无）",
        next_id=next_id,
    )


def build_refine_instruction(instruction: str) -> str:
    """构建 refine 的追问指令"""
    return REFINE_INSTRUCTION_TEMPLATE.format(instruction=instruction)
