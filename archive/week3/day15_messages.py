"""
Day 15 练习 2：LangChain Message 体系

理解三种消息类型的用法和区别。
"""

import os
from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.2,
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

# # ============================================================
# # 实验 1：只有 HumanMessage（无角色设定）
# # ============================================================

# print("=" * 60)
# print("实验 1：仅 HumanMessage（无系统角色）")
# print("=" * 60)

# response = llm.invoke([
#     HumanMessage(content="生成一个登录功能的测试用例，格式为 JSON")
# ])
# print(response.content[:200])
# print("...\n")


# # ============================================================
# # 实验 2：SystemMessage + HumanMessage（有角色设定）
# # ============================================================

# print("=" * 60)
# print("实验 2：SystemMessage + HumanMessage")
# print("=" * 60)

# response = llm.invoke([
#     SystemMessage(content="你是一名资深软件测试工程师，有10年测试经验。你的回答必须严格按照 JSON 格式输出，不要添加任何额外的解释文字。"),
#     HumanMessage(content="生成一个登录功能的测试用例，格式为 JSON"),
# ])
# print(response.content[:200])
# print("...\n")


# # ============================================================
# # 实验 3：SystemMessage + HumanMessage + AIMessage（多轮对话）
# # ============================================================

# print("=" * 60)
# print("实验 3：带历史的多轮对话（手动拼接 Message）")
# print("=" * 60)

# # 第一轮
# round1 = llm.invoke([
#     SystemMessage(content="你是测试工程师，回答要简洁。"),
#     HumanMessage(content="登录功能需要哪些测试用例？列出 3 个。"),
# ])
# print(f"AI 第1轮: {round1.content[:100]}...\n")

# # 第二轮：把第一轮的问答带进去
# round2 = llm.invoke([
#     SystemMessage(content="你是测试工程师，回答要简洁。"),
#     HumanMessage(content="登录功能需要哪些测试用例？列出 3 个。"),
#     AIMessage(content=round1.content),  # ← 把上一轮 AI 的回答带进来
#     HumanMessage(content="请为刚才提到的第一个用例补充详细的测试步骤。"),
# ])
# print(f"AI 第2轮: {round2.content[:200]}...\n")

# ============================================================
# 实验 4：观察不同类型的输出差异
# ============================================================

print("=" * 60)
print("实验 4：对比 System vs 无 System 的差异")
print("=" * 60)

# 无角色
response_no_role = llm.invoke([
    HumanMessage(content="用 JSON 列出 2 个登录测试用例。")
])

# 有角色
response_with_role = llm.invoke([
    SystemMessage(content="你是资深测试工程师。所有回答必须是有效的 JSON 格式，不能包含任何 Markdown 标记、解释文字或代码块符号。"),
    HumanMessage(content="用 JSON 列出 2 个登录测试用例。"),
])

print(f"无角色（长度）: {len(response_no_role.content)} 字符")
print(f"无角色输出: {response_no_role.content}")
print(f"有角色（长度）: {len(response_with_role.content)} 字符")
print(f"有角色输出: {response_with_role.content}")
