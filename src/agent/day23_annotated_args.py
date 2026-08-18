"""
Day 23 练习 2：Annotated 参数说明 —— 给参数写"说明书"

@tool 的 docstring 是【工具级】说明书；Annotated 是【参数级】说明书：
  a: Annotated[float, "被除数"]
  → LangChain 把第二个元素（描述）写进参数 Schema 的 description 字段
  → 模型生成调用参数时，能看到每个参数"是什么意思、怎么填"

今日四件事：
  1. 用 Annotated 定义 run_api_test 工具（学习计划里的第二个测试工具）
  2. 打印 args schema，对比"有 Annotated vs 无 Annotated"的参数描述差异
  3. 工具内参数校验：非法 method → 返回错误文本（不发请求）
  4. 进阶：parse_docstring=True 从 docstring 的 Args: 段解析参数说明
     ⚠️ 坑：描述段和 Args: 段之间必须【空行】分隔，否则装饰时抛 ValueError

⚠️ Pyright 注意事项：
  - Annotated[类型, 描述] 只是给类型加元数据，类型本身不变（Pyright 无感知）
  - 默认值写法：timeout: Annotated[int, "说明"] = 10 —— 先 Annotated 再默认值
  - 工具函数统一返回 str（给 LLM 看的都是文本）→ 类型最稳
  - invoke 返回 Any → object 接收 + isinstance 收窄

用法：直接运行（本练习零 API：不发真实 HTTP 请求，只打印 Schema + 测校验逻辑）。
"""

import json
import sys

# Windows 下控制台/重定向输出统一 UTF-8，防止 emoji/中文打印报 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from typing import Annotated, Any

from langchain_core.tools import tool

# HTTP 方法白名单（工具内部校验用）
ALLOWED_METHODS: tuple[str, ...] = ("GET", "POST", "PUT", "DELETE")


@tool
def run_api_test(
    url: Annotated[str, "接口地址，如 http://127.0.0.1:8080/api/login"],
    method: Annotated[str, "HTTP 方法，可选：GET/POST/PUT/DELETE"],
    payload: Annotated[str, "请求体 JSON 字符串（GET 请求传空字符串）"],
    timeout: Annotated[int, "超时秒数，默认 10"] = 10,
) -> str:
    """执行一个 HTTP API 测试请求，返回「状态码 + 响应体」摘要。
    当需要实际调用接口验证其可用性时使用。"""
    method_upper: str = method.upper()
    if method_upper not in ALLOWED_METHODS:
        return f"❌ 非法 HTTP 方法: {method}（可选 {'/'.join(ALLOWED_METHODS)}）"

    try:
        import requests

        json_payload: dict[str, Any] = {}
        if payload.strip():
            json_payload = json.loads(payload)  # 非法 JSON → JSONDecodeError → 被 except 捕获

        resp = requests.request(method_upper, url, json=json_payload, timeout=timeout)
        return f"状态码: {resp.status_code}\n响应体: {resp.text[:200]}"
    except Exception as exc:
        return f"❌ 请求失败（{type(exc).__name__}）: {exc}"


# ═══════════════════════════════════════════════════════
# 实验 1：打印参数 Schema —— 模型填参的依据
# ═══════════════════════════════════════════════════════

def exp1_print_schema() -> None:
    """实验 1：Annotated 参数说明 → args schema 的 description 字段"""
    print("=" * 60)
    print("实验 1：Annotated 参数说明（模型看到的 Schema）")
    print("=" * 60)
    print(json.dumps(run_api_test.args, ensure_ascii=False, indent=2))
    print("\n💡 每个参数的 description 都来自 Annotated 的第二个元素")
    print("   模型据此生成正确的调用参数（URL 该传什么、timeout 默认 10）")


# ═══════════════════════════════════════════════════════
# 实验 2：对比 —— 没有 Annotated 时模型看到什么
# ═══════════════════════════════════════════════════════

def exp2_no_annotated_contrast() -> None:
    """实验 2：去掉 Annotated 对比 —— 参数 description 消失"""
    print("\n" + "=" * 60)
    print("实验 2：有/无 Annotated 的 Schema 对比")
    print("=" * 60)

    @tool
    def run_api_test_bare(url: str, method: str, payload: str, timeout: int = 10) -> str:
        """执行一个 HTTP API 测试请求。"""
        return "ok"

    print("有 Annotated:")
    for name, meta in run_api_test.args.items():
        print(f"  {name}: {meta}")
    print("\n无 Annotated:")
    for name, meta in run_api_test_bare.args.items():
        print(f"  {name}: {meta}")
    print("\n💡 无 Annotated 时只有类型信息（title/type），模型只能靠猜")


# ═══════════════════════════════════════════════════════
# 实验 3：工具内参数校验 —— 非法 method 直接返回错误文本
# ═══════════════════════════════════════════════════════

def exp3_validation_flow() -> None:
    """实验 3：校验在【发请求之前】完成 —— 非法 method 零网络接触"""
    print("\n" + "=" * 60)
    print("实验 3：工具内参数校验（不发请求）")
    print("=" * 60)

    raw: object = run_api_test.invoke(
        {"url": "http://127.0.0.1:8080/api/login", "method": "PATCH", "payload": ""}
    )
    text: str = raw if isinstance(raw, str) else str(raw)
    print(f"调用结果: {text}")
    assert "非法 HTTP 方法" in text
    print("\n✅ 校验通过/失败都返回 str —— 模型能看到原因并自我修正（换合法方法）")


# ═══════════════════════════════════════════════════════
# 实验 4（进阶）：parse_docstring=True —— 从 docstring 解析参数说明
# ═══════════════════════════════════════════════════════

def exp4_parse_docstring() -> None:
    """实验 4：parse_docstring 进阶（Google 风格 docstring）"""
    print("\n" + "=" * 60)
    print("实验 4：parse_docstring=True（进阶）")
    print("=" * 60)

    @tool(parse_docstring=True)
    def get_weather(city: str, days: int = 1) -> str:
        """查询指定城市的天气。

        Args:
            city: 城市名，如 北京
            days: 预报天数，默认 1
        """
        return f"{city} {days} 天天气"

    print(json.dumps(get_weather.args, ensure_ascii=False, indent=2))
    print("💡 Args: 段的描述进入了 Schema.description（与 Annotated 效果相同）")

    # ❌ 反例（注释保留）：描述段和 Args: 段之间没有空行 → 装饰时直接抛错
    # @tool(parse_docstring=True)
    # def bad_doc(city: str) -> str:
    #     """查询天气。
    #     Args:
    #         city: 城市名
    #     """
    #     return city
    # → ValueError: Found invalid Google-Style docstring.
    #   原因：docstring.split("\n\n") 后只有 1 个 block，@tool 默认
    #   error_on_invalid_docstring=True → 解析失败直接在装饰时爆炸
    print("\n⚠️ 反例见注释：Args: 前必须有【空行】分隔（否则装饰时抛 ValueError）")
    print("   结论：参数说明优先用 Annotated（稳定）；parse_docstring 是进阶玩法")


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════

if __name__ == "__main__":
    # exp1_print_schema()
    # exp2_no_annotated_contrast()
    # exp3_validation_flow()
    exp4_parse_docstring()

    print("\n✅ Annotated 参数说明完成！")
    print("   Annotated[类型, '说明'] → 参数级说明书，模型填参更准")
    print("   下一步：参数校验 + ToolErrorMiddleware（练习 3）")
