"""
Day 16 练习 2：LCEL 管道组合深入

手动拆解管道 vs 一次性组合，理解 | 操作符的等价含义。

⚠️ Pyright 注意事项：
  - 拆分步骤时，中间变量的类型可能为 PromptValue / AIMessage
  - .content 在 AIMessage 上类型为 str，安全
  - 用 StrOutputParser 可以让管道返回 str 而非 AIMessage
"""

import os
from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.2,
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

prompt = ChatPromptTemplate.from_messages([
    ("system", "你是{role}，请按要求回答问题。"),
    ("human", "用一句话解释什么是{concept}，并举一个软件测试的例子。"),
])

test_input = {
    "role": "软件测试讲师",
    "concept": "等价类划分法",
}

# ═══════════════════════════════════════════════════════
# 实验 1：手动拆解管道（理解每一步的输入输出）
# ═══════════════════════════════════════════════════════

print("=" * 60)
print("实验 1：手动拆解 —— 看数据如何一步步流转")
print("=" * 60)

# 第 1 步：prompt 把 dict 变成 PromptValue
# ⚠️ Pyright 修复：不能直接标注 ChatPromptValue，因为 invoke() 实际返回 PromptValue（基类）
#    子类类型不能接收基类实例 → "Type 'PromptValue' is not assignable to declared type 'ChatPromptValue'"
# 正确做法：用 format_messages() 直接拿到 list[BaseMessage]，绕开 PromptValue 中间态
messages = prompt.format_messages(**test_input)
print(f"Step 1 - prompt.format_messages(dict)")
print(f"  输入类型: dict")
print(f"  输出类型: {type(messages).__name__}")
print(f"  消息数量: {len(messages)}")
print(f"  第1条消息类型: {type(messages[0]).__name__}")

# 备选：如果你想看 prompt 的字符串形式（用于调试），用 format()
prompt_str = prompt.format(**test_input)
print(f"  完整 Prompt（前 100 字符）:\n  {prompt_str[:100]}")
print()

# 第 2 步：llm 把 list[BaseMessage] 变成 AIMessage
# ⚠️ 注意：llm.invoke() 既能接 PromptValue，也能接 list[BaseMessage]
llm_output = llm.invoke(messages)
print(f"Step 2 - llm.invoke(messages)")
print(f"  输入类型: {type(messages).__name__}")
print(f"  输出类型: {type(llm_output).__name__}")
print(f"  内容长度: {len(llm_output.content)} 字符")
print(f"  内容预览: {llm_output.content[:80]}...")
print()

# 第 3 步：parser 把 AIMessage 变成 str
parser_output: str = StrOutputParser().invoke(llm_output)
print(f"Step 3 - parser.invoke(AIMessage)")
print(f"  输入类型: {type(llm_output).__name__}")
print(f"  输出类型: {type(parser_output).__name__}")
print(f"  最终结果: {parser_output[:80]}...")

# ═══════════════════════════════════════════════════════
# 实验 2：用 | 操作符一次性组合（等价于上面的三步）
# ═══════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("实验 2：管道组合 —— 等价于手动拆解，但代码更简洁")
print("=" * 60)

chain = prompt | llm | StrOutputParser()
result = chain.invoke(test_input)

print(f"  输入: dict（3个字段）")
print(f"  输出类型: {type(result).__name__}")
print(f"  结果: {result[:80]}...")


# ═══════════════════════════════════════════════════════
# 实验 3：管道是可以复用的
# ═══════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("实验 3：同一个 Chain，不同输入 → 复用能力")
print("=" * 60)

concepts = ["边界值分析法", "因果图法", "正交实验法"]

for concept in concepts:
    result = chain.invoke({"role": "测试讲师", "concept": concept})
    print(f"\n  📘 {concept}:")
    print(f"     {result[:120]}...")

print("\n💡 小结：")
print("  - prompt | llm | parser 等价于三步手动调用")
print("  - | 操作符让数据自动衔接，无需手动传递中间结果")
print("  - 同一个 Chain 可以反复调用不同的输入（真正的复用！）")