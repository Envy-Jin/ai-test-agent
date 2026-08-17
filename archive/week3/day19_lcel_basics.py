"""
Day 19 练习 1：LCEL 三大核心组件（RAG Chain 的积木）

掌握 RunnablePassthrough / format_docs / StrOutputParser：
  - RunnablePassthrough()：输入什么输出什么（透传用户问题）
  - format_docs(docs)：把 list[Document] 拼成 LLM 可读的文本
  - StrOutputParser()：把 AIMessage 转成纯 str

⚠️ Pyright 注意事项：
  - format_docs 的参数必须标注 list[Document]，返回类型标注 str
  - RunnablePassthrough() 是 Runnable，可以出现在 LCEL 链条中
  - StrOutputParser() 输出 str，不会出现 response.text 为 None 的问题
  - 本脚本不调用 LLM（除了实验 4 的 StrOutputParser 演示），纯演示类型与数据流

用法：直接运行跑全部实验，或在 main() 中注释掉不想跑的实验函数。
"""

from langchain_core.runnables import RunnablePassthrough
from langchain_core.documents import Document
from langchain_core.messages import AIMessage



# ═══════════════════════════════════════════════════════
# 模块级：format_docs（所有实验共用）
# ═══════════════════════════════════════════════════════

def format_docs(docs: list[Document]) -> str:
    """把检索到的文档片段拼成一段文本（RAG Chain 的核心格式化函数）。

    每个片段之间用两个换行分隔，方便 LLM 区分不同来源。
    """
    return "\n\n".join(doc.page_content for doc in docs)


# ═══════════════════════════════════════════════════════
# 实验 1：RunnablePassthrough —— 透传
# ═══════════════════════════════════════════════════════

def exp1_runnable_passthrough() -> None:
    """实验 1：RunnablePassthrough 输入什么就输出什么"""
    print("=" * 60)
    print("实验 1：RunnablePassthrough —— 透传")
    print("=" * 60)

    passthrough = RunnablePassthrough()

    # 单独使用：原样返回
    result: str = passthrough.invoke("登录功能需要哪些测试用例？")
    print(f"invoke 结果: {result}")
    print(f"输入输出相同: {result == '登录功能需要哪些测试用例？'}")

    # 在字典中使用：把输入透传到指定键
    mapper = {"question": RunnablePassthrough()}
    mapped: str = mapper["question"].invoke("支付安全要求")
    print(f"\n字典映射 invoke 结果: {mapped}")

    # 典型用途：作为 Chain 的入口之一
    print("\n💡 RunnablePassthrough 典型用途：")
    print("  {\"context\": retriever | format_docs, \"question\": RunnablePassthrough()}")
    print("  → context 键由检索器填充，question 键原样透传用户输入")


# ═══════════════════════════════════════════════════════
# 实验 2：format_docs —— 文档格式化
# ═══════════════════════════════════════════════════════

def exp2_format_docs() -> None:
    """实验 2：format_docs 把文档列表拼成文本"""
    print("\n" + "=" * 60)
    print("实验 2：format_docs —— 文档格式化")
    print("=" * 60)

    docs: list[Document] = [
        Document(page_content="登录功能：支持手机号+密码登录，连续输错5次锁定账号。", metadata={"source": "login.md"}),
        Document(page_content="密码规则：8-20位，必须包含字母和数字。", metadata={"source": "login.md"}),
    ]

    text: str = format_docs(docs)

    print(f"输入 {len(docs)} 个 Document")
    print(f"输出 {len(text)} 字符的文本:\n")
    print(text)

    # 验证分隔符
    separator_count: int = text.count("\n\n")
    print(f"\n💡 {len(docs) - 1} 个片段之间用 '\\n\\n' 分隔（出现了 {separator_count} 次）")

    # format_docs 可以直接放进 LCEL 链条
    # 注意：普通函数会自动被 LangChain 包装为 Runnable
    from langchain_core.runnables import RunnableLambda

    formatted_chain = RunnableLambda[list[Document], str](format_docs)
    same_text: str = formatted_chain.invoke(docs)
    print(f"通过 RunnableLambda 包装后输出一致: {same_text == text}")


# ═══════════════════════════════════════════════════════
# 实验 3：StrOutputParser —— 消息转字符串
# ═══════════════════════════════════════════════════════

def exp3_str_output_parser() -> None:
    """实验 3：StrOutputParser 把 AIMessage 转成纯文本"""
    print("\n" + "=" * 60)
    print("实验 3：StrOutputParser —— 消息转字符串")
    print("=" * 60)

    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.messages import AIMessage

    parser = StrOutputParser()

    # 模拟 LLM 返回的 AIMessage（type 为 str，可直接切片）
    message = AIMessage(content="基于需求文档，登录功能需要 5 个测试用例。")

    # 解析：取 .content
    text: str = parser.invoke(message)
    print(f"AIMessage.content 类型: {type(message.content).__name__}")
    print(f"解析后文本: {text}")
    print(f"解析后类型: {type(text).__name__}")
    print(f"可直接切片: {text[:10]}...")

    print("\n💡 关键点：AIMessage.content 是 str（不是 str | None），")
    print("   而新版 SDK 的 response.text 是 str | None 需要 safe_text()")
    print("   → RAG Chain 用 StrOutputParser 后，输出天然是纯 str")


# ═══════════════════════════════════════════════════════
# 实验 4：三件套组合 —— 模拟完整的 RAG 数据流
# ═══════════════════════════════════════════════════════

def exp4_combo() -> None:
    """实验 4：三件套组合，模拟 RAG Chain 的数据流（不调 LLM）"""
    print("\n" + "=" * 60)
    print("实验 4：三件套组合 —— 模拟 RAG 数据流")
    print("=" * 60)

    # 模拟检索器（返回固定文档，代替真实 retriever.invoke）
    def fake_retriever(query: str) -> list[Document]:
        print(f"  [检索器] 收到查询: \"{query}\"")
        return [
            Document(page_content="登录功能：手机号+密码登录。", metadata={"source": "login.md"}),
            Document(page_content="验证码：4位数字，有效期5分钟。", metadata={"source": "login.md"}),
        ]

    # 模拟 LLM（返回 AIMessage，代替真实 llm.invoke）
    def fake_llm(prompt_value: str) -> AIMessage:
        from langchain_core.messages import AIMessage
        print(f"  [LLM] 收到 Prompt（前 60 字符）: {str(prompt_value)[:60]}...")
        return AIMessage(content="根据文档，登录支持手机号+密码，验证码有效期5分钟。")

    # 手动走一遍数据流（对应 ①→②→③→④）
    question: str = "登录功能怎么实现？"

    # ① 检索 + 透传
    docs: list[Document] = fake_retriever(question)
    context: str = format_docs(docs)
    print(f"  [context] {len(context)} 字符")

    # ② 填 Prompt（此处简化为 f-string）
    prompt_text: str = f"基于以下文档回答：\n{context}\n问题：{question}"

    # ③ LLM 生成
    message = fake_llm(prompt_text)

    # ④ 解析为字符串
    from langchain_core.output_parsers import StrOutputParser
    answer: str = StrOutputParser().invoke(message)
    print(f"\n最终回答: {answer}")

    print("\n💡 这就是 RAG Chain 的完整数据流！")
    print("   步骤 2 将用真正的 retriever + llm 替换 fake 版本，并写成一条 | 链")



# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    # exp1_runnable_passthrough()
    # exp2_format_docs()
    # exp3_str_output_parser()
    exp4_combo()

    print("\n💡 小结：")
    print("  - RunnablePassthrough()：原样透传用户问题 → 填进 {question}")
    print("  - format_docs(docs: list[Document]) -> str：文档 → 文本")
    print("  - StrOutputParser()：AIMessage → str")
    print("  - 三件套是 RAG Chain 的积木，下一步拼成完整链条")