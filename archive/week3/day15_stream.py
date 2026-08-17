"""
Day 15 练习 3：invoke() vs stream()

对比 LangChain 的两种调用方式。
注意：LangChain 的 stream() 和纯 SDK 的 generate_content_stream()
      返回类型不同 —— LangChain 返回 AIMessageChunk。
"""

import os
import time
from dotenv import load_dotenv

load_dotenv()

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.5,
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

messages = [
    SystemMessage(content="你是测试工程师，回答要详细。"),
    HumanMessage(content="详细解释一下等价类划分法，举一个登录功能的例子。"),
]

# ============================================================
# 方式 1：invoke() —— 一次返回
# ============================================================

print("=" * 60)
print("方式 1：invoke() —— 等全部生成完，一次返回")
print("=" * 60)

start = time.time()
response = llm.invoke(messages)
elapsed = time.time() - start

print(f"\n耗时: {elapsed:.1f}s")
print(f"响应类型: {type(response).__name__}")
print(f"内容长度: {len(response.content)} 字符")
print(f"\n内容预览（前 200 字符）:\n{response.content[:200]}...")

# ============================================================
# 方式 2：stream() —— 逐块返回
# ============================================================

print("\n" + "=" * 60)
print("方式 2：stream() —— 边生成边输出")
print("=" * 60)

full_text = []
start = time.time()

# 提前初始化 chunk（避免 Pyright 报 "possibly unbound"）
chunk = None

print("流式输出: ", end="", flush=True)
for chunk in llm.stream(messages):
    if chunk.content:
        print(chunk.content, end="", flush=True)
        full_text.append(chunk.content)

elapsed = time.time() - start
print(f"\n\n耗时: {elapsed:.1f}s")
print(f"总长度: {sum(len(t) for t in full_text)} 字符")
print(f"Chunk 类型: {type(chunk).__name__ if chunk else '无 chunk'}")

# ============================================================
# 对比总结
# ============================================================

print("\n" + "=" * 60)
print("对比总结")
print("=" * 60)
print(f"invoke() 一次性返回，内容立即可用")
print(f"stream() 逐块返回，适合 UI 实时展示")