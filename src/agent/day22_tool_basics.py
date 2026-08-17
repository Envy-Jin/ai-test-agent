"""
Day 22 练习 1：@tool 装饰器 —— 定义你的第一批工具

纯本地练习（不联网、不调 LLM API），理解三件事：
  1. @tool 自动提取 docstring（说明书）+ 类型注解（参数 Schema）
  2. 工具的 .name / .description / .args 属性（模型看到的就是这些）
  3. 工具的两种调用：直接 .invoke()（调试用） vs 交给 Agent（练习 3）

⚠️ Pyright 注意事项：
  - StructuredTool.invoke(dict) 返回 Any（工具返回值类型不定）→ 接收后用
    isinstance 校验或 str() 转换，不要裸赋给具体类型
  - 工具函数签名必须写全参数注解（LangChain 靠它生成 Schema），
    这与 Pyright 的要求天然一致 —— 今天注解不是负担，是功能

用法：直接运行跑全部实验，或在 main() 中注释掉不想跑的实验函数。
"""

import sys
from datetime import datetime

# Windows 下控制台/重定向输出统一 UTF-8，防止 emoji/中文打印报 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from langchain_core.tools import BaseTool, tool

# ═══════════════════════════════════════════════════════
# 工具 1：最简单的工具（单参数 → 单返回值）
# ═══════════════════════════════════════════════════════

@tool
def get_word_length(word: str) -> int:
    """返回单词/字符串的字符长度。当需要统计字符数时使用。"""
    return len(word)


# ═══════════════════════════════════════════════════════
# 工具 2：测试场景工具（模拟"用例计数统计"）
# ═══════════════════════════════════════════════════════

@tool
def count_status(test_results: list[str]) -> dict[str, int]:
    """统计测试结果列表中各状态的数量。test_results 是状态字符串列表，
    每个元素应为 "pass"、"fail" 或 "skip" 之一。返回各状态的计数字典。"""
    counter: dict[str, int] = {}
    for status in test_results:
        counter[status] = counter.get(status, 0) + 1
    return counter


# ═══════════════════════════════════════════════════════
# 工具 3：当前时间工具（Agent 回答"今天"类问题的常用配件）
# ═══════════════════════════════════════════════════════

@tool
def get_current_time() -> str:
    """获取当前的本地日期和时间，格式为 YYYY-MM-DD HH:MM:SS。
    当问题涉及"现在/今天/当前时间"时使用。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ═══════════════════════════════════════════════════════
# 实验 1：观察工具的"身份证"（模型看到的三要素）
# ═══════════════════════════════════════════════════════

def exp1_tool_identity() -> None:
    """实验 1：打印工具的 name / description / args —— 模型选工具的依据"""
    print("=" * 60)
    print("实验 1：工具的身份证（name / description / args）")
    print("=" * 60)

    for t in (get_word_length, count_status, get_current_time):
        print(f"\n🔧 {t.name}")
        print(f"   说明: {t.description}")
        print(f"   参数 Schema: {t.args}")


# ═══════════════════════════════════════════════════════
# 实验 2：直接调用工具（开发调试方式）
# ═══════════════════════════════════════════════════════

def exp2_direct_invoke() -> None:
    """实验 2：.invoke() 直接执行工具 —— Agent 内部做的也是这件事"""
    print("\n" + "=" * 60)
    print("实验 2：直接调用工具")
    print("=" * 60)

    n: object = get_word_length.invoke({"word": "pytest"})
    print(f"get_word_length('pytest') = {n}（类型: {type(n).__name__}）")

    counter: object = count_status.invoke(
        {"test_results": ["pass", "fail", "pass", "skip", "pass"]}
    )
    print(f"count_status([...]) = {counter}")

    now: object = get_current_time.invoke({})
    print(f"get_current_time() = {now}")


# ═══════════════════════════════════════════════════════
# 实验 3：反例 —— docstring 缺失时会发生什么
# ═══════════════════════════════════════════════════════

def exp3_no_docstring() -> None:
    """实验 3：docstring 是工具说明书，缺失 = 模型不知道何时用这个工具"""
    print("\n" + "=" * 60)
    print("实验 3：docstring 缺失的后果")
    print("=" * 60)

    # ❌ 反例（注释保留供观察）：没有 docstring 的工具
    # @tool
    # def bad_tool(x: str) -> str:
    #     return x.upper()
    # → LangChain 会警告 "Tool has no description"；
    #   模型拿到的 description 是空串 → 永远不会选中它

    print("❌ 反例见源码注释：无 docstring 的 @tool 工具会被模型无视")
    print("✅ 正确：docstring 写清【干什么 + 什么时候用】，参数说明也写在里面")


# ═══════════════════════════════════════════════════════
# 实验 4：StructuredTool 类型确认（Pyright 视角）
# ═══════════════════════════════════════════════════════

def exp4_structured_tool_type() -> None:
    """实验 4：@tool 的返回值是 StructuredTool 实例（类型显式确认）"""
    print("\n" + "=" * 60)
    print("实验 4：@tool 的产物是 StructuredTool")
    print("=" * 60)

    t: BaseTool = get_word_length  # 显式标注验证类型兼容
    print(f"✅ get_word_length 的类型: {type(t).__name__}")
    print("   create_agent(tools=[...]) 接收的就是这个类型")


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    # exp1_tool_identity()
    # exp2_direct_invoke()
    # exp3_no_docstring()
    exp4_structured_tool_type()

    print("\n✅ @tool 基础完成！")
    print("   工具 = 函数 + docstring（说明书）+ 类型注解（参数 Schema）")
    print("   下一步：把 DuckDuckGo 搜索包成工具（练习 2）")

