"""
Day 15 练习 5：AIMessage 探索 + StrOutputParser

理解 LangChain 的响应结构和输出解析器的角色。
"""

import os
from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.output_parsers import StrOutputParser

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.2,
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

# ============================================================
# 实验 1：探索 AIMessage 的完整结构
# ============================================================

print("=" * 60)
print("实验 1：AIMessage 内部结构")
print("=" * 60)

response = llm.invoke([
    SystemMessage(content="用一句话回答。"),
    HumanMessage(content="什么是等价类划分？"),
])

print(f"类型: {type(response).__name__}")
print(f"content: {response.content[:80]}...")
print(f"id: {response.id}")
print(f"response_metadata: {response.response_metadata}")
print(f"usage_metadata: {response.usage_metadata}")
print()

# ============================================================
# 实验 2：StrOutputParser 自动提取文本
# ============================================================

print("=" * 60)
print("实验 2：llm | StrOutputParser()")
print("=" * 60)

# 方式 A：手动 .content
result_a = llm.invoke("用一句话介绍软件测试")
print(f"方式 A（手动 .content）: {type(result_a.content).__name__} = '{result_a.content[:50]}...'")

# 方式 B：StrOutputParser
chain = llm | StrOutputParser()
result_b = chain.invoke("用一句话介绍软件测试")
print(f"方式 B（StrOutputParser）: {type(result_b).__name__} = '{result_b[:50]}...'")

print(f"\n💡 方式 B 返回的就是纯 str，不需要 .content")