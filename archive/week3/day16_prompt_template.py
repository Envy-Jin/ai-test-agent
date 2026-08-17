"""
Day 16 练习 1：ChatPromptTemplate 基础

对比两种模板创建方式，理解变量占位符的工作原理。

⚠️ Pyright 注意事项：
  - prompt.invoke()              返回类型为 ChatPromptValue，不是 dict
  - prompt.format_messages()      返回 list[BaseMessage]
  - prompt | llm                  链式调用时类型自动衔接
  - 不要直接在 prompt.invoke() 结果上访问 ['requirement']，它不是 dict
"""

import os
from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ============================================================
# 模型初始化（今日统一用 gemini-3.1-flash-lite）
# ============================================================

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.2,
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

# ═══════════════════════════════════════════════════════
# 实验 1：from_template() —— 单条消息模板
# ═══════════════════════════════════════════════════════

print("=" * 60)
print("实验 1：from_template() —— 单条消息模板")
print("=" * 60)

# 定义模板（整个 Prompt 就是一条 Human 消息）
simple_template = ChatPromptTemplate.from_template(
    "你是资深测试工程师。请为以下需求生成 3 个测试用例：\n\n{requirement}"
)

# 查看模板变量
print(f"模板变量: {simple_template.input_variables}")

# 方式 A：用 format_messages() 手动格式化（返回 list[BaseMessage]）
messages = simple_template.format_messages(
    requirement="手机号+验证码登录功能"
)
print(f"\n格式化后类型: {type(messages).__name__}")
print(f"消息数量: {len(messages)}")
print(f"消息内容（前100字符）:\n{messages[0].content[:100]}...")

# 方式 B：用 invoke() 自动格式化（返回 ChatPromptValue）
prompt_value = simple_template.invoke({"requirement": "手机号+验证码登录功能"})
print(f"\ninvoke() 返回类型: {type(prompt_value).__name__}")
# ⚠️ prompt_value 不是 dict！不能用 prompt_value["requirement"]
#    它需要传给 llm.invoke() 才能得到结果

# 方式 C：通过管道调用（这才是 LCEL 的标准用法）
simple_chain = simple_template | llm | StrOutputParser()
result = simple_chain.invoke({"requirement": "手机号+验证码登录功能"})
print(f"\n管道调用结果类型: {type(result).__name__}")
print(f"结果（前200字符）:\n{result[:200]}...")

# ═══════════════════════════════════════════════════════
# 实验 2：from_messages() —— 多角色模板（推荐）
# ═══════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("实验 2：from_messages() —— 支持 System + Human 角色")
print("=" * 60)

# 定义多角色模板
role_template = ChatPromptTemplate.from_messages([
    ("system", "你是{role}，有{experience}年经验。回答必须简洁专业。"),
    ("human", "需求：{requirement}\n测试类型：{test_type}"),
])

print(f"模板变量: {role_template.input_variables}")

# 注入不同变量，观察输出差异
# 场景 A：资深测试工程师 + 正向测试
result_a = (role_template | llm | StrOutputParser()).invoke({
    "role": "资深软件测试工程师",
    "experience": "10",
    "requirement": "用户注册功能：手机号+密码",
    "test_type": "正向功能测试",
})
print(f"\n场景 A（资深+正向）:\n{result_a[:200]}...")

# 场景 B：安全测试专家 + 安全测试
result_b = (role_template | llm | StrOutputParser()).invoke({
    "role": "安全测试专家",
    "experience": "15",
    "requirement": "用户注册功能：手机号+密码",
    "test_type": "安全渗透测试",
})
print(f"\n场景 B（安全专家+安全测试）:\n{result_b[:200]}...")

# ═══════════════════════════════════════════════════════
# 实验 3：partial() —— 部分填充模板
# ═══════════════════════════════════════════════════════

print("\n" + "=" * 60)
print("实验 3：partial() —— 部分填充（锁定角色不变）")
print("=" * 60)

# 锁定 system 角色和资历，只留 requirement 和 test_type 可变
partial_template = role_template.partial(
    role="资深测试工程师",
    experience="10",
)

print(f"部分填充后变量: {partial_template.input_variables}")

# 现在只需要 2 个变量
result_c = (partial_template | llm | StrOutputParser()).invoke({
    "requirement": "密码重置功能",
    "test_type": "边界值测试",
})
print(f"结果:\n{result_c[:200]}...")

print("\n💡 小结：")
print("  - from_template() 适合简单的一句话 Prompt")
print("  - from_messages() 适合有角色区分的复杂 Prompt")
print("  - partial() 可以锁定一部分变量，减少重复传参")
print("  - 模板的 invoke() 返回 PromptValue，不是 dict，不要直接索引")