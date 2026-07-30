"""
Day 15 练习 1：LangChain 第一个 Gemini 调用

和 Day 8 的 hello_gemini.py 做对比：
  - Day 8：直接用 google-genai SDK
  - Day 15：通过 LangChain 封装调用

核心对比点：
  1. SDK: genai.Client()          →  LangChain: ChatGoogleGenerativeAI()
  2. SDK: response.text            →  LangChain: response.content
  3. SDK: 参数在 generate_content() →  LangChain: 参数在构造函数
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# LangChain 调用（新方式）
# ============================================================

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

# 初始化 LLM（参数在构造函数中设定）
llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.2,
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

# 调用：invoke() 是 LangChain 的统一接口
response = llm.invoke("用一句话介绍什么是软件测试")

print("=" * 60)
print("LangChain 调用结果：")
print("=" * 60)
print(f"类型: {type(response).__name__}")
print(f"内容: {response.content}")
print()

# ============================================================
# 纯 SDK 调用（旧方式，作为对比）
# ============================================================

from google import genai

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
response_sdk = client.models.generate_content(
    model="gemini-3.1-flash-lite",
    contents="用一句话介绍什么是软件测试",
)

print("-" * 60)
print("纯 SDK 调用结果（对比）：")
print("-" * 60)
print(f"类型: {type(response_sdk).__name__}")
print(f"内容: {response_sdk.text}")