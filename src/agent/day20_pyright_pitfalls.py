"""
Day 20 练习 5：Pyright 避坑实战 —— 知识库场景

知识库项目引入的新类型陷阱。本练习不调用 API，纯演示
「❌ 错误写法 vs ✅ 正确写法」。

⚠️ 所有标注 ❌ 的代码都在注释里说明原因，✅ 的可以放心照抄。

用法：直接运行，全部是演示性质，不含 API 调用。
"""

from typing import Optional
from langchain_core.documents import Document


# ═══════════════════════════════════════════════════════
# 坑 1：metadata.get() 返回 Any，必须显式转换
# ═══════════════════════════════════════════════════════

def pitfall1_metadata_type() -> None:
    """坑 1：Document.metadata 是 dict[str, Any]"""

    doc = Document(page_content="登录需求", metadata={"doc_type": "requirement", "category": "login"})

    # ❌ 错误：doc_type 是 Any，后续 if doc_type == "bug" 失去类型检查
    # doc_type = doc.metadata.get("doc_type")

    # ✅ 正确：str() 显式转换
    doc_type: str = str(doc.metadata.get("doc_type", "unknown"))
    assert doc_type == "requirement"
    print(f"✅ metadata 取值用 str() 转换: doc_type={doc_type}")
    print("  记忆口诀：metadata.get() 是 Any → 一律 str()/int() 显式转换")


# ═══════════════════════════════════════════════════════
# 坑 2：Optional[Chroma] 判空收窄
# ═══════════════════════════════════════════════════════

def pitfall2_optional_chroma() -> None:
    """坑 2：_vectorstore 是 Optional[Chroma]，使用前必须判空"""

    # ❌ 错误：直接连续访问（Pyright 报 Object is possibly "None"）
    # self._vectorstore.similarity_search(query)
    # vs = self._vectorstore  # Optional[Chroma]
    # vs.similarity_search(query)  # ❌ 可能为 None

    # ✅ 正确：先收窄再使用
    from langchain_chroma import Chroma

    _vectorstore: Optional[Chroma] = None
    vs: Optional[Chroma] = _vectorstore
    if vs is None:
        raise RuntimeError("尚未建索引，请先调用 index()")
    # 此时 vs 已被 Pyright 收窄为 Chroma，可以放心调用
    print("✅ Optional 判空后收窄: if vs is None: raise ... 之后 vs 可用")
    print("  记忆口诀：Optional 成员变量 → 局部变量 + if is not None 收窄")


# ═══════════════════════════════════════════════════════
# 坑 3：filter 参数的类型
# ═══════════════════════════════════════════════════════

def pitfall3_filter_type() -> None:
    """坑 3：similarity_search 的 filter 类型注解过窄（langchain 第三方签名 bug）"""

    # ❌ 错误（Day 20 实测踩坑）：filter 用嵌套结构 {"$eq": ...} 后，
    #    即使标注 dict[str, object] 也报错：
    #    "dict[str, object] is not assignable to dict[str, str]"
    #    原因：langchain 基类签名是 filter: dict[str, str] | None（过窄），
    #    但 Chroma 1.x 运行时实际支持嵌套结构 —— 类型注解跟不上实现
    # vs.similarity_search(q, k=3, filter=filter_dict)  # ❌ Pyright 报错

    # ✅ 正确：嵌套 filter 保留 dict[str, object]，调用点加 # type: ignore[arg-type]
    #    （第三方库类型签名 bug → 调用点规避 + 注释说明，这是 # type: ignore 的正当用法）
    filter_dict: dict[str, object] = {"doc_type": {"$eq": "bug"}}
    print(f"✅ filter 嵌套结构运行时正确（Chroma 1.x 支持）：{filter_dict}")
    print("  记忆口诀：第三方库类型签名 bug → 调用点 # type: ignore[arg-type] + 注释")


# ═══════════════════════════════════════════════════════
# 坑 4：ThreadPoolExecutor 的 Future
# ═══════════════════════════════════════════════════════

def pitfall4_future_result() -> None:
    """坑 4：pool.submit() 返回 Future，用 .result() 取值"""

    from concurrent.futures import Future, ThreadPoolExecutor

    def add(a: int, b: int) -> int:
        return a + b

    # ✅ 正确：显式标注 Future[int]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures: list[Future[int]] = [pool.submit(add, i, i) for i in range(3)]
        results: list[int] = [f.result() for f in futures]

    assert results == [0, 2, 4]
    print(f"✅ Future 显式标注 + result() 取值: {results}")
    print("  记忆口诀：submit() → Future[T]，显式标注 list[Future[T]] 再 result()")


# ═══════════════════════════════════════════════════════
# 坑 5：Pydantic 嵌套校验 Optional 收窄
# ═══════════════════════════════════════════════════════

def pitfall5_pydantic_optional() -> None:
    """坑 5：model_validate 可能失败，Optional 结果必须收窄"""

    from pydantic import BaseModel, Field

    class BugAnalysis(BaseModel):
        bug_summary: str = Field(description="总结")
        severity: str = Field(description="严重度")

    def parse(raw: object) -> Optional[BugAnalysis]:
        if not isinstance(raw, dict):
            return None
        try:
            return BugAnalysis.model_validate(raw)
        except Exception:
            return None

    # ❌ 错误：直接访问 analysis.severity —— 可能为 None
    # analysis = parse({"bug_summary": "x"})   # severity 缺失 → 返回 None
    # print(analysis.severity)                  # ❌ Object is possibly "None"

    # ✅ 正确：if analysis is not None 收窄
    analysis: Optional[BugAnalysis] = parse({"bug_summary": "x", "severity": "严重"})
    if analysis is not None:
        print(f"✅ 收窄后访问: {analysis.bug_summary} / {analysis.severity}")
    print("  记忆口诀：Optional 校验结果 → if x is not None 收窄后再用")


# ═══════════════════════════════════════════════════════
# 坑 6：doc_type 常量避免魔法字符串
# ═══════════════════════════════════════════════════════

def pitfall6_constants() -> None:
    """坑 6：用常量替代魔法字符串（类型安全约定）"""

    DOC_TYPE_BUG: str = "bug"

    # ❌ 错误：魔法字符串拼写错误（如 "BUg"）Pyright 无法发现
    # filter_dict = {"doc_type": {"$eq": "BUg"}}   # 运行时静默失效！

    # ✅ 正确：用常量，拼错会被 IDE 标红
    filter_dict: dict[str, object] = {"doc_type": {"$eq": DOC_TYPE_BUG}}
    print(f"✅ 常量替代魔法字符串: {filter_dict}")
    print("  记忆口诀：类型标签用常量（DOC_TYPE_*），防拼写错误")


# ═══════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════

def main() -> None:
    pitfall1_metadata_type()
    pitfall2_optional_chroma()
    pitfall3_filter_type()
    pitfall4_future_result()
    pitfall5_pydantic_optional()
    pitfall6_constants()

    print("\n💡 知识库场景 Pyright 避坑总结：")
    print("  1. metadata.get() → str() 显式转换")
    print("  2. Optional[Chroma] → 局部变量 + if is not None 收窄")
    print("  3. filter 嵌套结构 → 调用点 # type: ignore[arg-type]（langchain 注解过窄）")
    print("  4. submit() → 标注 list[Future[T]]，用 result() 取值")
    print("  5. Pydantic 校验 → Optional + if is not None")
    print("  6. doc_type 用常量，不用魔法字符串")


if __name__ == "__main__":
    main()
