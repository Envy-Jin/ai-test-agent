"""
Day 23 练习 5：Pyright 避坑实战 —— 自定义 Tool 场景

Day 23 引入的新类型陷阱。本练习不调用 API，纯演示
「❌ 错误写法 vs ✅ 正确写法」。

⚠️ 所有标注 ❌ 的代码都在注释里说明原因，✅ 的可以放心照抄。

用法：直接运行，全部是演示性质，不含 API 调用。
"""

import sys
from typing import Annotated

# Windows 下控制台/重定向输出统一 UTF-8，防止 emoji/中文打印报 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from langchain.agents.middleware import ToolCallRequest
from langchain_core.tools import tool


# ═══════════════════════════════════════════════════════
# 坑 1：StructuredTool.invoke 返回 Any（Day 22 坑 1 的延伸）
# ═══════════════════════════════════════════════════════

def pitfall1_invoke_any() -> None:
    """坑 1：工具 .invoke() 的返回类型是 Any → object 接收再收窄"""

    @tool
    def get_length(word: str) -> int:
        """返回字符串长度。"""
        return len(word)

    # ❌ 错误：n: int = get_length.invoke({"word": "pytest"})
    #    invoke 返回 Any，Pyright 严格模式不允许 Any 直接赋给具体类型

    # ✅ 正确：object 接收 + isinstance 收窄
    raw: object = get_length.invoke({"word": "pytest"})
    n: int = raw if isinstance(raw, int) else int(str(raw))
    assert n == 6
    print(f"✅ 坑 1：invoke 返回 Any → object 收窄（n={n}）")
    print("   from_function 产物的 invoke 同样是 Any，处理方式一致")


# ═══════════════════════════════════════════════════════
# 坑 2：工具返回值统一 str（不要返回 dict）
# ═══════════════════════════════════════════════════════

def pitfall2_return_str() -> None:
    """坑 2：工具返回 dict 时，模型/日志看到的是 repr 字符串 → 统一返回 str"""

    # ❌ 错误：返回 dict → Agent 收到的是 {'x': '登录'} 的 repr，模型理解困难
    # @tool
    # def get_info(x: str) -> dict:
    #     """返回信息字典。"""
    #     return {"x": x}

    # ✅ 正确：返回 JSON 字符串（结构清晰，模型直接可读）
    @tool
    def get_info(x: str) -> str:
        """返回信息（JSON 字符串）。"""
        import json

        return json.dumps({"x": x}, ensure_ascii=False)

    print(f"✅ 坑 2：工具返回 str（{get_info.invoke({'x': '登录'})}）")
    print("   口诀：Observation 全是文本 → 返回 str，需要结构就 json.dumps")


# ═══════════════════════════════════════════════════════
# 坑 3：ToolCall TypedDict 取值（on_error / tool_calls 场景）
# ═══════════════════════════════════════════════════════

def pitfall3_tool_call_typeddict() -> None:
    """坑 3：ToolCall 是 TypedDict → 取字段用 .get / 索引，配合 str() 转换"""

    # 模拟 request.tool_call（ToolCall TypedDict：name/args/id/type）
    tool_call: dict[str, object] = {
        "name": "generate_test_cases",
        "args": {"requirement": "登录"},
        "id": "call_1",
        "type": "tool_call",
    }

    # ❌ 错误：name: str = tool_call["name"] —— 万一缺键直接 KeyError
    # ✅ 正确：.get + str() 防御性转换
    name: str = str(tool_call.get("name", "unknown"))
    assert name == "generate_test_cases"
    print(f"✅ 坑 3：TypedDict 取值 .get + str()（name={name}）")
    print("   口诀：外部数据（LLM/工具请求）一律 .get + 显式转换")


# ═══════════════════════════════════════════════════════
# 坑 4：on_error 回调签名（str | None 的双语义）
# ═══════════════════════════════════════════════════════

def pitfall4_on_error_signature() -> None:
    """坑 4：ToolErrorMiddleware 回调必须返回 str | None（None = 放行异常）"""

    def on_error(exc: Exception, request: ToolCallRequest) -> str | None:
        # ❌ 错误：把不想处理的异常也"返回文本"吞掉 → 中间件形同虚设
        #   return "出错了"  # 所有异常都变成文本，真正该中断的也被吞了
        # ✅ 正确：只处理关心的异常，其余返回 None（放行）
        if isinstance(exc, ValueError):
            return f"工具 {request.tool_call.get('name', 'unknown')} 参数有误"
        return None

    req = ToolCallRequest(
        tool_call={"name": "divide", "args": {}, "id": "c1", "type": "tool_call"},
        tool=None,
        state=None,
        runtime=None,  # type: ignore[arg-type]
    )
    msg: str | None = on_error(ValueError("除数不能为 0"), req)
    assert msg is not None and "divide" in msg
    print(f"✅ 坑 4：on_error 返回 str | None（msg={msg}）")
    print("   None = 放行（异常继续传播）；只处理关心的异常类型")


# ═══════════════════════════════════════════════════════
# 坑 5：用 | None 替代 Optional（项目规范）
# ═══════════════════════════════════════════════════════

def pitfall5_union_none() -> None:
    """坑 5：可空类型统一写 xxx | None（项目规范，不用 Optional）"""

    # ❌ 错误：from typing import Optional; def parse(text: str) -> Optional[dict]:
    #    老写法，两种风格混用会让项目不一致

    # ✅ 正确：dict | None（Python 3.10+ 内置联合类型）
    def parse(text: str) -> dict | None:
        if not text.strip():
            return None
        return {"len": len(text)}

    result: dict | None = parse("")
    assert result is None
    print("✅ 坑 5：可空类型用 xxx | None（parse('') → None）")
    print("   口诀：Optional[X] → X | None，全项目统一")


# ═══════════════════════════════════════════════════════
# 坑 6：Annotated 默认值顺序 + parse_docstring 装饰时爆炸
# ═══════════════════════════════════════════════════════

def pitfall6_annotated_and_parse() -> None:
    """坑 6：Annotated 默认值写法 + parse_docstring 的装饰时抛错"""

    # ✅ Annotated + 默认值：limit: Annotated[int, "说明"] = 5（先 Annotated 再默认值）
    @tool
    def probe(
        query: Annotated[str, "查询关键词"],
        limit: Annotated[int, "返回条数"] = 5,
    ) -> str:
        """示例工具：返回查询说明。"""
        return f"query={query}, limit={limit}"

    print(f"✅ 坑 6a：Annotated 默认值（{probe.args}）")

    # ⚠️ parse_docstring=True 时，docstring 格式错了会在【装饰时】抛 ValueError
    # ❌ @tool(parse_docstring=True)
    #    def bad(city: str) -> str:
    #        """查询天气。
    #        Args:
    #            city: 城市名
    #        """
    #        return city
    #    → ValueError: Found invalid Google-Style docstring.（Args: 前缺空行）
    print("   ⚠️ 坑 6b：parse_docstring 的 Args: 前必须空行，否则装饰时抛错")
    print("   结论：参数说明优先 Annotated，parse_docstring 留作进阶")


# ═══════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════

def main() -> None:
    pitfall1_invoke_any()
    pitfall2_return_str()
    pitfall3_tool_call_typeddict()
    pitfall4_on_error_signature()
    pitfall5_union_none()
    pitfall6_annotated_and_parse()

    print("\n💡 Day 23 场景 Pyright 避坑总结：")
    print("  1. invoke 返回 Any → object 接收 + isinstance 收窄")
    print("  2. 工具统一返回 str（要结构就 json.dumps）")
    print("  3. ToolCall TypedDict → .get + str() 转换")
    print("  4. on_error 返回 str | None（None = 放行异常）")
    print("  5. 可空类型用 xxx | None（不用 Optional）")
    print("  6. Annotated 默认值：先 Annotated 再默认值；parse_docstring 有装饰时抛错坑")


if __name__ == "__main__":
    main()
