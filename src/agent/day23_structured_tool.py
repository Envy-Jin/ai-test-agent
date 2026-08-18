"""
Day 23 练习 1：StructuredTool.from_function —— 从已有函数生成工具

Day 22 学的是 @tool 装饰器（最常用）。今天学习第二种定义方式：
StructuredTool.from_function() —— 从【已存在的普通函数】创建工具，
适合"函数已经写好，给它套个工具壳"的场景（比如把 Day 12 的纯函数包进 Agent）。

四个能力的递进：
  1. 最简：from_function(func=函数) → 自动提取 name/description/args
  2. 自定义：name= / description= 覆盖默认值
  3. args_schema：用 Pydantic 类精确定义参数结构（默认值、说明、约束）
  4. 实战：把 Day 12 的 json_extractor 纯函数包成工具壳

⚠️ Pyright 注意事项：
  - StructuredTool.invoke() 返回 Any → 接收后用 object + isinstance 收窄（Day 22 坑 1）
  - Pydantic args_schema 校验失败会抛 ValidationError → 演示时 try/except 捕获
  - from_function(func=...) 要求函数有完整类型注解（自动推断 Schema 的前提）
  - 函数 docstring = 工具说明书（和 @tool 一样），别省略

用法：直接运行跑全部实验，或在 main() 中注释掉不想跑的实验函数。
"""

import sys

# Windows 下控制台/重定向输出统一 UTF-8，防止 emoji/中文打印报 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from pydantic import BaseModel, Field

from langchain_core.tools import BaseTool, StructuredTool, tool

from json_extractor import extract_json, validate_json_schema


# ═══════════════════════════════════════════════════════
# 工具 1：最简用法 —— 从普通函数创建工具
# ═══════════════════════════════════════════════════════

def count_cases(cases: list[dict[str, str]]) -> int:
    """统计测试用例列表的数量。"""
    return len(cases)


count_cases_tool = StructuredTool.from_function(func=count_cases)


# ═══════════════════════════════════════════════════════
# 工具 2：自定义 name / description —— 覆盖函数默认值
# ═══════════════════════════════════════════════════════

json_extract_tool = StructuredTool.from_function(
    func=extract_json,
    name="extract_json",
    description=(
        "从 LLM 输出文本中提取 JSON 对象或数组。"
        "当文本可能被代码块包裹、带前后缀文字、或格式不纯净时使用。"
    ),
)


# ═══════════════════════════════════════════════════════
# 工具 3：args_schema 用 Pydantic 自定义（默认值/说明/约束）
# ═══════════════════════════════════════════════════════

class AnalyzeBugInput(BaseModel):
    """Bug 报告分析的输入参数。"""
    bug_text: str = Field(description="Bug 报告的原始文本内容")
    severity_filter: str = Field(
        default="all", description="严重级别过滤：all/critical/major/minor"
    )


def analyze_bug(bug_text: str, severity_filter: str = "all") -> str:
    """分析 Bug 报告文本（纯本地演示函数，返回格式化摘要）。"""
    stripped: str = bug_text.strip()
    first_line: str = stripped.splitlines()[0] if stripped else "（空报告）"
    return f"[过滤:{severity_filter}] Bug 摘要: {first_line[:60]}"


analyze_bug_tool = StructuredTool.from_function(
    func=analyze_bug,
    args_schema=AnalyzeBugInput,
)


# ═══════════════════════════════════════════════════════
# 工具 4：把 Day 12 的 validate_json_schema 包成工具壳
# ═══════════════════════════════════════════════════════

validate_schema_tool = StructuredTool.from_function(
    func=validate_json_schema,
    name="validate_json_schema",
    description=(
        "校验 JSON 对象是否包含全部必需字段。"
        "当需要检查 LLM 输出/接口响应的结构完整性时使用。"
    ),
)


# ═══════════════════════════════════════════════════════
# 实验 1：工具的身份证（@tool 与 from_function 产物相同）
# ═══════════════════════════════════════════════════════

def exp1_tool_identity() -> None:
    """实验 1：打印工具的 name / description / args —— 与 @tool 产物完全同型"""
    print("=" * 60)
    print("实验 1：from_function 产物的身份证")
    print("=" * 60)

    for t in (count_cases_tool, json_extract_tool, validate_schema_tool):
        print(f"\n🔧 {t.name}")
        print(f"   说明: {t.description}")
        print(f"   参数 Schema: {t.args}")
        # print(f"   schema类型: {type(t.args)}")

    t: StructuredTool = count_cases_tool  # 显式标注验证类型
    print(f"\n✅ 类型确认: {type(t).__name__}（与 @tool 的产物同型）")


# ═══════════════════════════════════════════════════════
# 实验 2：直接调用（.invoke() 调试方式）
# ═══════════════════════════════════════════════════════

def exp2_direct_invoke() -> None:
    """实验 2：.invoke() 直接调用 —— Agent 内部做的也是这件事"""
    print("\n" + "=" * 60)
    print("实验 2：直接调用")
    print("=" * 60)

    n: object = count_cases_tool.invoke(
        {"cases": [{"id": "TC001", "title": "登录"}, {"id": "TC002", "title": "注册"}]}
    )
    print(f"count_cases = {n}（类型: {type(n).__name__}）")

    obj: object = json_extract_tool.invoke(
        {"text": "结果：```json\n{\"test_cases\": [{\"id\": \"TC001\"}]}\n```"}
    )
    print(f"extract_json = {obj}")

    ok: object = validate_schema_tool.invoke(
        {"data": {"test_cases": []}, "required_keys": ["test_cases"]}
    )
    print(f"validate_json_schema = {ok}（预期 True）")


# ═══════════════════════════════════════════════════════
# 实验 3：args_schema 生效 —— 默认值 + 参数说明
# ═══════════════════════════════════════════════════════

def exp3_args_schema() -> None:
    """实验 3：Pydantic args_schema → 参数默认值/说明进入 Schema"""
    print("\n" + "=" * 60)
    print("实验 3：args_schema 生效")
    print("=" * 60)

    print("Schema 内容:")
    print(f"  {analyze_bug_tool.args}")

    raw: object = analyze_bug_tool.invoke(
        {"bug_text": "登录后跳转空白页", "severity_filter": "critical"}
    )
    print(f"显式传参: {raw if isinstance(raw, str) else str(raw)}")

    raw2: object = analyze_bug_tool.invoke({"bug_text": "偶发 500"})
    print(f"缺省参数: {raw2 if isinstance(raw2, str) else str(raw2)}（severity_filter 用了默认值 all）")


# ═══════════════════════════════════════════════════════
# 实验 4：非法参数 —— Pydantic 校验拦截（函数体不会执行）
# ═══════════════════════════════════════════════════════

def exp4_validation_block() -> None:
    """实验 4：非法参数被 Pydantic 拦截（在函数执行前）"""
    print("\n" + "=" * 60)
    print("实验 4：参数校验拦截")
    print("=" * 60)

    try:
        analyze_bug_tool.invoke({"bug_text": "x", "severity_filter": 123})  # 类型错误
    except Exception as exc:
        print(f"⚠️ 校验拦截: {type(exc).__name__}")
        print("   severity_filter=123 不是 str → Pydantic 在调用函数前就拒绝了")
        print("   （函数体没有执行 —— 这就是 args_schema 的免费参数校验）")


# ═══════════════════════════════════════════════════════
# 实验 5：对比 —— @tool 与 from_function 等价互换
# ═══════════════════════════════════════════════════════

def exp5_compare_decorator() -> None:
    """实验 5：同一个函数，两种定义方式产物等价"""
    print("\n" + "=" * 60)
    print("实验 5：@tool vs from_function（等价互换）")
    print("=" * 60)

    @tool
    def multiply(a: int, b: int) -> int:
        """两个整数相乘，返回积。"""
        return a * b

    def multiply_fn(a: int, b: int) -> int:
        """两个整数相乘，返回积。"""
        return a * b

    t1: BaseTool = multiply  # @tool 产物（类型是 BaseTool）
    t2: BaseTool = StructuredTool.from_function(func=multiply_fn)  # 等价（BaseTool 子类）

    print(f"@tool:          name={t1.name} args={t1.args}")
    print(f"from_function:  name={t2.name} args={t2.args}")
    print(f"调用一致: {t1.invoke({'a': 3, 'b': 4})} / {t2.invoke({'a': 3, 'b': 4})}")
    print("💡 区别在【改造力】：from_function 能覆盖 name/description/args_schema，")
    print("   @tool 的产物基本固定（这也是为什么已有函数更适合 from_function 套壳）")


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    exp1_tool_identity()
    # exp2_direct_invoke()
    # exp3_args_schema()
    # exp4_validation_block()
    # exp5_compare_decorator()

    print("\n✅ StructuredTool.from_function 完成！")
    print("   已有函数 → 工具壳：from_function(func=..., name=..., description=..., args_schema=...)")
    print("   下一步：Annotated 参数说明（练习 2）")
