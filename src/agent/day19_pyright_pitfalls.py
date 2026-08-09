"""
Day 19 练习 6：Pyright 避坑实战 —— RAG Chain 场景

RAG Chain 引入后，有几个新的类型安全陷阱。本练习不调用 API，
纯演示「❌ 错误写法 vs ✅ 正确写法」。

⚠️ 所有标注 ❌ 的代码都在注释里说明原因，✅ 的可以放心照抄。

用法：直接运行，全部是演示性质，不含 API 调用。
"""

from langchain_core.documents import Document


# ═══════════════════════════════════════════════════════
# 坑 1：format_docs 的参数必须标注类型
# ═══════════════════════════════════════════════════════

def pitfall1_format_docs_type() -> None:
    """坑 1：format_docs 不标注参数类型 → Pyright 推断 Unknown"""

    # ❌ 错误：参数不标注
    # def format_docs(docs):
    #     return "\n\n".join(doc.page_content for doc in docs)
    # → doc 被推断为 Unknown，.page_content 没有类型检查保护

    # ✅ 正确：完整标注
    def format_docs(docs: list[Document]) -> str:
        return "\n\n".join(doc.page_content for doc in docs)

    docs: list[Document] = [Document(page_content="内容", metadata={})]
    text: str = format_docs(docs)
    print(f"✅ format_docs 类型标注正确，输出 {len(text)} 字符")

    print("  记忆口诀：format_docs 的参数写 list[Document]，返回写 str")


# ═══════════════════════════════════════════════════════
# 坑 2：Chain 字典里的 lambda 参数是 Unknown
# ═══════════════════════════════════════════════════════

def pitfall2_lambda_in_chain() -> None:
    """坑 2：{"context": lambda q: ...} 中 q 的类型是 Unknown"""

    # ❌ 错误（Pyright 提示 lambda 参数 q 为 Unknown）：
    # chain = {
    #     "context": lambda q: format_docs(retriever.invoke(q)),  # q: Unknown
    #     "question": RunnablePassthrough(),
    # }

    # ✅ 推荐：改用具名函数（参数类型明确，Pyright 零警告）
    def build_context(q: str) -> str:
        # 真实场景：docs = retriever.invoke(q); return format_docs(docs)
        return f"context of {q}"

    result: str = build_context("登录")
    print(f"✅ 具名函数替代 lambda，参数类型明确: {result}")
    print("  记忆口诀：Chain 内需要处理的逻辑 → 提出来写具名函数")


# ═══════════════════════════════════════════════════════
# 坑 3：similarity_search_with_score 的元组解包
# ═══════════════════════════════════════════════════════

def pitfall3_score_tuple() -> None:
    """坑 3：带分数检索结果的类型是 list[tuple[Document, float]]"""

    # ❌ 错误：不写类型注解时
    # results = vs.similarity_search_with_score(query, k=3)
    # for doc, score in results:   # doc 和 score 类型未知

    # ✅ 正确：显式注解（实际 IDE 能推断，显式写更稳）
    mock: list[tuple[Document, float]] = [
        (Document(page_content="片段A", metadata={}), 0.5),
        (Document(page_content="片段B", metadata={}), 1.2),
    ]
    filtered: list[Document] = [doc for doc, score in mock if score <= 1.0]
    print(f"✅ 分数过滤后保留 {len(filtered)} 个片段")
    print("  记忆口诀：score 元组 → 解包后 doc: Document, score: float")


# ═══════════════════════════════════════════════════════
# 坑 4：RunnableConfig 必须显式标注（Day 17 复习）
# ═══════════════════════════════════════════════════════

def pitfall4_runnable_config() -> None:
    """坑 4：对话式 RAG 的 config 参数必须显式标注 RunnableConfig"""

    from langchain_core.runnables import RunnableConfig

    # ❌ 错误：直接写 dict 字面量
    # chain.invoke({"question": q}, config={"configurable": {"session_id": "x"}})
    # → Pyright 报：dict[str, dict[str, str]] 不能赋给 RunnableConfig | None

    # ✅ 正确：显式标注
    session_config: RunnableConfig = {"configurable": {"session_id": "rag_demo"}}
    print(f"✅ RunnableConfig 显式标注: {session_config}")
    print("  记忆口诀：config 必须声明 RunnableConfig，否则 Pyright 必报红")


# ═══════════════════════════════════════════════════════
# 坑 5：MessagesPlaceholder 的导入路径
# ═══════════════════════════════════════════════════════

def pitfall5_messages_placeholder() -> None:
    """坑 5：MessagesPlaceholder 从 langchain_core.prompts 导入"""

    # ❌ 错误：从 langchain_core.messages 导入
    # from langchain_core.messages import MessagesPlaceholder  # ❌ 不存在

    # ✅ 正确：从 langchain_core.prompts 导入
    from langchain_core.prompts import MessagesPlaceholder

    placeholder = MessagesPlaceholder("chat_history")
    print(f"✅ MessagesPlaceholder 导入正确: {placeholder}")
    print("  记忆口诀：MessagesPlaceholder 属于 prompts 模块，不属于 messages")


# ═══════════════════════════════════════════════════════
# 坑 6：Pydantic 模型校验返回 Optional
# ═══════════════════════════════════════════════════════

def pitfall6_pydantic_optional() -> None:
    """坑 6：model_validate 可能失败，返回值要用 Optional 收窄"""

    from typing import Optional
    from pydantic import BaseModel, Field

    class TC(BaseModel):
        id: str = Field(description="编号")
        title: str = Field(description="标题")

    # ❌ 错误：直接 len(suite.test_cases) —— suite 可能是 None
    # suite = parse_suite(raw)
    # print(len(suite.test_cases))  # Pyright: Object is possibly "None"

    # ✅ 正确：先判空再使用（if suite is not None 收窄类型）
    def parse_suite(raw: object) -> Optional[TC]:
        if not isinstance(raw, dict):
            return None
        try:
            return TC.model_validate(raw)
        except Exception:
            return None

    suite: Optional[TC] = parse_suite({"id": "TC001", "title": "正常登录"})
    if suite is not None:
        print(f"✅ 判空后访问: {suite.id} / {suite.title}")
    print("  记忆口诀：Optional 返回值 → 用 if x is not None 收窄后再用")


# ═══════════════════════════════════════════════════════
# main
# ═══════════════════════════════════════════════════════

def main() -> None:
    pitfall1_format_docs_type()
    pitfall2_lambda_in_chain()
    pitfall3_score_tuple()
    pitfall4_runnable_config()
    pitfall5_messages_placeholder()
    pitfall6_pydantic_optional()

    print("\n💡 RAG Chain 场景 Pyright 避坑总结：")
    print("  1. format_docs 参数标注 list[Document]，返回 str")
    print("  2. Chain 中的处理逻辑用具名函数，不用 lambda")
    print("  3. similarity_search_with_score → list[tuple[Document, float]]")
    print("  4. config 显式标注 RunnableConfig")
    print("  5. MessagesPlaceholder 从 langchain_core.prompts 导入")
    print("  6. Pydantic 校验结果用 Optional + if is not None 收窄")


if __name__ == "__main__":
    main()
