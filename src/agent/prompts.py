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


# ============================================================
# UI 截图分析（Day 10）
# ============================================================

SYSTEM_UI_ANALYST = (
    "你是一名有 10 年经验的资深软件测试工程师，擅长 UI 测试和可用性测试。"
    "你只能根据截图中实际可见的内容进行分析，不会臆造看不见的元素。"
    "你能识别按钮、输入框、链接、Tab、第三方登录图标、二维码、协议链接等常见 UI 模式，"
    "并基于识别结果生成覆盖正向、边界、异常、视觉、交互的 UI 测试用例。"
    "对于每个数据约束（长度、数值范围、格式等），你必须同时覆盖「刚好满足」和「刚好不满足」两个方向，"
    "不能只写一个方向的边界用例。"
    "例如手机号是 11 位数字，你必须同时生成：恰好 11 位（满足）、少于 11 位（不满足）、多于 11 位（不满足）。"
    "对于断网、权限等无法从截图验证的场景，必须标注 test_scope 为「需环境模拟」。"
)

FEW_SHOT_SCREENSHOT = """
【示例输出结构】（字段名必须一致）
{
  "page_name": "用户登录页",
  "page_description": "手机号验证码登录页面",
  "analysis_summary": "中部为登录表单，含手机号与验证码输入；底部为协议链接。",
  "elements": [
    {
      "element_id": "EL001",
      "element_type": "输入框",
      "label": "手机号",
      "location": "表单区上部",
      "state": "正常"
    },
    {
      "element_id": "EL002",
      "element_type": "按钮",
      "label": "登录",
      "location": "表单区下部",
      "state": "置灰"
    }
  ],
  "test_cases": [
    {
      "id": "TC001",
      "title": "手机号验证码正常登录",
      "type": "正向",
      "priority": "P0",
      "target_element_id": "EL002",
      "target_element": "登录",
      "test_scope": "UI可测",
      "steps": ["输入11位有效手机号", "输入验证码", "点击登录"],
      "expected": "登录成功并跳转"
    },
    {
      "id": "TC002",
      "title": "空手机号提交",
      "type": "边界",
      "priority": "P1",
      "target_element_id": "EL001",
      "target_element": "手机号",
      "test_scope": "UI可测",
      "steps": ["不输入手机号", "点击登录"],
      "expected": "提示手机号不能为空或按钮保持置灰"
    },
    {
      "id": "TC003",
      "title": "手机号少于11位",
      "type": "边界",
      "priority": "P1",
      "target_element_id": "EL001",
      "target_element": "手机号",
      "test_scope": "UI可测",
      "steps": ["在手机号框输入10位数字", "点击登录"],
      "expected": "提示手机号格式错误或按钮保持置灰"
    },
    {
      "id": "TC004",
      "title": "手机号多于11位",
      "type": "边界",
      "priority": "P1",
      "target_element_id": "EL001",
      "target_element": "手机号",
      "test_scope": "UI可测",
      "steps": ["在手机号框输入12位数字", "点击登录"],
      "expected": "输入框限制输入或提示格式错误"
    }
  ],
  "visual_issues": ["登录按钮与输入框间距不一致"]
}
"""

SCREENSHOT_ANALYSIS_TEMPLATE = """{few_shot}

请分析这张应用界面截图，严格参考上方示例的 JSON 结构与字段名输出。

【重要原则】
- 仅识别截图中实际可见的元素和文字，不可见的不臆造
- 优先识别：Tab/标签页、输入框、按钮、链接、二维码、第三方登录图标、协议文字、弹窗等

【分析任务】
1. 填写 page_name、page_description
2. 在 analysis_summary 中简述：布局分区、主要交互流程、可见风险点
3. 列出所有可见 elements（element_id 从 EL001 起编号）
4. 为关键元素生成 test_cases（id 从 TC001 起编号），覆盖：
   - 正向：正常操作流程
   - 边界：对每个输入框有长度的字段，必须对称覆盖「空值」「刚好满足」「刚好不满足(=满足-1)」「明显超限(=满足+1)」四个方向。如手机号 11 位 → 0位/10位/11位/12位，每个方向成独立用例。对下拉框/复选框等也要覆盖所有选项组合。
   - 异常：仅写截图可推断的异常（如错误提示态）；断网/权限等标 test_scope=需环境模拟
   - 视觉：对齐、间距、文字溢出、遮挡
   - 交互：点击响应、焦点切换、置灰态按钮等
5. 列出 visual_issues（仅基于截图可见问题）

【优先级】
- P0：核心流程（如主按钮登录）
- P1：边界与 UI 可测异常
- P2：视觉与次要交互

【关联要求】
- test_cases.target_element_id 尽量填写对应 elements.element_id
- 每个按钮至少 1 个正向用例；每个输入框至少 3 个边界用例（空值 + 刚好不满足 + 明显超限）"""


def build_screenshot_prompt() -> str:
    """构建 UI 截图分析的完整 Prompt"""
    return SCREENSHOT_ANALYSIS_TEMPLATE.format(few_shot=FEW_SHOT_SCREENSHOT)
