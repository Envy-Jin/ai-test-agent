"""
Day 24 避坑实战：结构化输出场景的 Pyright 陷阱

坑 1：result["structured_response"] 取值是 object → 必须 isinstance 收窄
坑 2：Pydantic Literal 字段 —— 约束是给模型看的，静态类型上就是 str
坑 3：dict[str, object] 的 .get() 返回值是 object | None → 逐层收窄
坑 4：@tool 产物是 BaseTool，不是 StructuredTool → 容器注解用 BaseTool
坑 5：dict 值类型 invariant —— metadata 用 dict[str, str] 就别混 None

用法：python day24_pyright_pitfalls.py（纯本地逻辑，无 API）
"""

import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from typing import Literal

from pydantic import BaseModel, Field


class TestCaseItem(BaseModel):
    """坑 2 演示：Literal 字段。"""
    id: str = Field(description="用例编号")
    priority: Literal["P0", "P1", "P2"] = Field(description="优先级")


def demo_pydantic_literal() -> None:
    """坑 2：Literal 只是约束模型输出，代码里就是普通 str。"""
    item: TestCaseItem = TestCaseItem(id="TC001", priority="P0")
    print(f"priority={item.priority}，类型是 {type(item.priority).__name__}（运行时就是 str）")
    assert item.priority == "P0"


def extract_bundle(result: dict[str, object]) -> TestCaseItem | None:
    """坑 1 + 坑 3：dict 取值是 object，必须 isinstance 收窄。"""
    raw: object = result.get("structured_response")  # get 返回 object | None，但值本来就是 object
    if isinstance(raw, TestCaseItem):
        return raw
    return None


def demo_dict_get() -> None:
    """坑 3：get() 的返回值要逐层收窄。"""
    result: dict[str, object] = {"structured_response": TestCaseItem(id="TC001", priority="P0")}
    item: TestCaseItem | None = extract_bundle(result)
    if item is None:
        raise AssertionError("应拿到 TestCaseItem")
    print(f"✅ 收窄成功: {item.id}")


def demo_metadata_typing() -> None:
    """坑 5：dict 值类型 invariant —— metadata 统一 dict[str, str]。"""
    # 错误示范（会报错）：metadata: dict[str, str] = {"source": "a.md", "doc_type": "bug", "chunk_idx": 1}
    metadata: dict[str, str] = {"source": "a.md", "doc_type": "bug", "chunk_idx": "1"}
    source: str = metadata["source"]
    print(f"✅ metadata 用 dict[str, str] 统一类型: source={source}")


def main() -> None:
    demo_pydantic_literal()
    demo_dict_get()
    demo_metadata_typing()
    print("\n💡 坑位回顾：")
    print("   1. structured_response 是 object → isinstance 收窄（dict 取值没有自动收窄）")
    print("   2. Literal 字段运行时就是 str（约束是给模型的）")
    print("   3. .get() 返回值逐层收窄（dict[str, object] 没有智能）")
    print("   4. @tool 产物是 BaseTool（工具列表注解用 list[BaseTool]）")
    print("   5. dict 值类型 invariant（metadata 统一 dict[str, str]）")


if __name__ == "__main__":
    main()
