"""
Day 15 练习 4：SDK vs LangChain 深度对比

同一个任务 ——「根据需求生成测试用例」——
分别用纯 SDK 和 LangChain 实现，对比代码结构。
"""

import os
import time
from dotenv import load_dotenv
from utils import safe_text

load_dotenv()


# ============================================================
# 通用配置
# ============================================================

SYSTEM_PROMPT = """你是一名资深软件测试工程师。
请根据需求描述生成 3 个测试用例，以 JSON 格式输出：
{
  "test_cases": [
    {"id": "TC001", "title": "...", "type": "正向/边界/异常", "priority": "P0/P1/P2",
     "steps": ["步骤1", "步骤2"], "expected": "预期结果"}
  ]
}"""

REQUIREMENT = "用户登录功能：支持手机号+验证码登录，手机号格式为1开头的11位数字，验证码6位数字，有效期5分钟。"


# ============================================================
# 方案 A：纯 SDK（google-genai）
# ============================================================

print("=" * 60)
print("方案 A：纯 google-genai SDK")
print("=" * 60)

from google import genai
from google.genai import types

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

start = time.time()

response_a = client.models.generate_content(
    model="gemini-3.1-flash-lite",
    contents=[
        types.Content(
            role="user",
            parts=[types.Part.from_text(text=f"{SYSTEM_PROMPT}\n\n需求：{REQUIREMENT}")]
        )
    ],
    config=types.GenerateContentConfig(
        temperature=0.2,
    ),
)

text_a = safe_text(response_a)

elapsed_a = time.time() - start

print(f"耗时: {elapsed_a:.1f}s")
print(f"响应类型: {type(response_a).__name__}")
print(f"\n输出:\n{text_a[:300]}...")

# ============================================================
# 方案 B：LangChain
# ============================================================

print("\n" + "=" * 60)
print("方案 B：LangChain")
print("=" * 60)

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage, HumanMessage

llm = ChatGoogleGenerativeAI(
    model="gemini-3.1-flash-lite",
    temperature=0.2,
    google_api_key=os.getenv("GEMINI_API_KEY"),
)

start = time.time()

response_b = llm.invoke([
    SystemMessage(content=SYSTEM_PROMPT),
    HumanMessage(content=f"需求：{REQUIREMENT}"),
])

elapsed_b = time.time() - start

print(f"耗时: {elapsed_b:.1f}s")
print(f"响应类型: {type(response_b).__name__}")
print(f"\n输出:\n{response_b.content[:300]}...")  # AIMessage.content 始终是 str，无需 safe_text()

# ============================================================
# 对比分析
# ============================================================

print("\n" + "=" * 60)
print("对比分析")
print("=" * 60)
print(f"""
┌────────────────────┬──────────────────────────┬──────────────────────────┐
│ 维度               │ 方案 A：纯 SDK            │ 方案 B：LangChain        │
├────────────────────┼──────────────────────────┼──────────────────────────┤
│ 初始化             │ genai.Client(api_key=...) │ ChatGoogleGenerativeAI() │
│ 调用方法           │ generate_content()        │ invoke()                 │
│ 角色设定           │ 手动拼到 content 里        │ SystemMessage 显式标注   │
│ 参数配置           │ GenerateContentConfig     │ 构造函数参数             │
│ 响应获取           │ response.text             │ response.content         │
│ 耗时               │ {elapsed_a:.1f}s          │ {elapsed_b:.1f}s          │
│ 切换模型（GPT）     │ 需要改整段代码            │ 只改 ChatGoogle... → ChatOpenAI │
└────────────────────┴──────────────────────────┴──────────────────────────┘
""")

print("💡 核心结论：")
print("   LangChain 不改变底层模型的行为（耗时差不多），")
print("   但它提供了一个统一的抽象层，让代码更结构化、更易切换模型。")