"""
Day 26 练习 3：checkpointer 对话记忆 —— Agent v3（解决 Day 25 遗留问题）

升级链：
  Day 24 Agent     = 5 工具 + ToolStrategy(TestCaseBundle)              ← 能干活
  Day 25 Agent v2  = + LangSmith 追踪 + ModelRetry/Fallback + ToolRetry/ToolError
                     + recursion_limit                                  ← 能看、能救
  Day 26 Agent v3  = + checkpointer（InMemorySaver / SqliteSaver）      ← 有记忆

两条路径：
  路径 A：InMemorySaver —— 进程内记忆（开发调试，脚本退出即忘）
  路径 B：SqliteSaver   —— SQLite 文件持久化（跨进程重启仍记得）

会话隔离：config = {"configurable": {"thread_id": "xxx"}}
  同一 thread_id → 共享记忆；不同 thread_id → 完全隔离（多用户并发安全）

⚠️ 联网确认（2026-08-22）：
  - create_agent 原生支持 checkpointer 参数（官方 reference 签名确认）
  - 官方 quickstart 用 InMemorySaver（MemorySaver 是旧名）
  - SqliteSaver 新版拆到独立包 langgraph-checkpoint-sqlite（缺包先 pip install）

用法：
  python day26_checkpointer_memory.py                 # 全部实验（真实 API）
  python -c "from day26_checkpointer_memory import build_agent_v3, build_smoke_v3; build_agent_v3(InMemorySaver()); build_smoke_v3(); print('✅ 冒烟通过')"
"""

import os
import sqlite3
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()  # ⚠️ 必须在 langchain import 之前（LangSmith 静默失效的坑，Day 25 口诀）

from langchain.agents import create_agent
from langchain.agents.middleware import (
    ModelFallbackMiddleware,
    ModelRetryMiddleware,
    ToolErrorMiddleware,
    ToolRetryMiddleware,
)
from langchain.agents.structured_output import ToolStrategy
from langchain_core.language_models.fake_chat_models import FakeChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import InMemorySaver

from day25_error_handling import on_tool_error
from day25_test_agent_v2 import AGENT_TOOLS, TestCaseBundle, extract_bundle, llm

# ═══════════════════════════════════════════════════════
# 常量 + checkpointer
# ═══════════════════════════════════════════════════════

FALLBACK_MODEL: str = "google_genai:gemini-3.5-flash"  # ⚠️ 2026-05 新模型，Premium 付费；计费敏感改回 gemini-3.1-flash
DB_PATH: str = os.path.join(os.path.dirname(__file__), "..", "..", "checkpoints.sqlite")


def build_agent_v3(checkpointer):
    """Agent v3 = v2 + checkpointer（对话记忆）。

    与 build_agent_v2 的唯一区别：最后多了 checkpointer= 参数。
    """
    return create_agent(
        model=llm,
        tools=AGENT_TOOLS,
        system_prompt=(
            "你是一名资深软件测试工程师的 AI 助手。\n"
            "1. 用户要求生成测试用例 → 先 kb_search 参考知识库，再 generate_test_cases\n"
            "2. 用户提到 Bug → analyze_bug_report\n"
            "3. 用户给了接口地址 → run_api_test\n"
            "4. 新文档入库 → kb_import\n"
            "5. 工具返回错误消息 → 修正参数重试\n"
            "6. 用户会跨轮对话：记住前面聊过的内容（如用户介绍的背景、已确认的测试范围）\n"
            "最后：只有当需要交付完整测试用例时，才把用例整理进 TestCaseBundle 输出"
        ),
        response_format=ToolStrategy(TestCaseBundle),
        middleware=[
            ToolErrorMiddleware(on_error=on_tool_error),      # 外层
            ToolRetryMiddleware(max_retries=2, on_failure="error"),  # 内层（Day 25 顺序陷阱）
            ModelFallbackMiddleware(FALLBACK_MODEL),          # 外层
            ModelRetryMiddleware(max_retries=2, on_failure="error"),  # 内层
        ],
        checkpointer=checkpointer,  # ← Day 26 新增：一行装记忆
    )


def build_smoke_v3():
    """零 API 冒烟：FakeChatModel + InMemorySaver（不含 Fallback，构建期需 key 的排除）。"""
    return create_agent(
        model=FakeChatModel(),
        tools=AGENT_TOOLS,
        middleware=[
            ToolErrorMiddleware(on_error=on_tool_error),
            ToolRetryMiddleware(max_retries=1, on_failure="error"),
            ModelRetryMiddleware(max_retries=1, on_failure="error"),
        ],
        checkpointer=InMemorySaver(),
    )

def _last_text(result: dict[str, object]) -> str:
    """从 invoke 结果取最后一条消息文本（pyright 收窄教学点）。"""
    msgs_obj: object = result.get("messages", [])
    if isinstance(msgs_obj, list) and msgs_obj:
        content: object = msgs_obj[-1].content
        return str(content)[:300]
    return "(无消息)"


# ═══════════════════════════════════════════════════════
# 实验
# ═══════════════════════════════════════════════════════

def exp1_smoke() -> None:
    """实验 1：零 API 冒烟——v3 构建不炸（checkpointer 参数签名正确）。"""
    print("=" * 60)
    print("实验 1：Agent v3 无 API 冒烟构建（FakeChatModel + InMemorySaver）")
    agent = build_smoke_v3()
    print(f"✅ 构建成功: {type(agent).__name__}")


def exp2_memory_in_process() -> None:
    """实验 2：进程内记忆（InMemorySaver）——同 thread 记得，异 thread 隔离。

    ⚠️ 记忆验证问题必须落在"测试职责内"：Agent v3 绑了
    response_format=ToolStrategy(TestCaseBundle)，机制上强制模型必须调用工具、
    且只有"交 Bundle"或"无工具调用"才能停机（tool_choice="any"，源码确认）——
    问闲聊问题（"我叫什么"）模型无法退出 → GraphRecursionError。
    所以三个问题都设计成"不带答案、必须靠记忆才能答对"的测试任务。
    """
    print("=" * 60)
    print("实验 2：InMemorySaver 对话记忆（记忆验证三部曲）")
    agent = build_agent_v3(InMemorySaver())

    # ① 第一轮：交代名字 + 登录功能任务（正常走流程交 Bundle）
    config_a: RunnableConfig = {"configurable": {"thread_id": "study-session"}, "recursion_limit": 25}
    agent.invoke(
        {"messages": [HumanMessage(content="你好，我叫小测，是一名软件测试工程师。请为「登录功能」生成测试用例")]},
        config=config_a,
    )
    print("① 第一轮：自我介绍 + 登录功能用例  →  已回复")

    # ② 第二轮（同一 thread_id）：问题里【不】提登录，模型必须读记忆才知道测的是哪个功能
    #    同时"继续补充用例"是测试任务 → 模型正常交 Bundle，不会死循环
    result2: dict[str, object] = agent.invoke(
        {"messages": [HumanMessage(content="我们刚才在测哪个功能？继续为它补充 2 条边界值用例")]},
        config=config_a,
    )
    text2: str = _last_text(result2)
    print(f"② 第二轮（同 thread）：{text2[:120]}")
    print(f"   → {'✅ 记得范围（feature=登录）' if ('登录' in text2) else '❌ 没记住（检查 checkpointer 是否生效）'}")

    # ③ 第三轮（换 thread_id）：全新会话做新任务，不应带上旧会话的"登录"
    config_b: RunnableConfig = {"configurable": {"thread_id": "another-session"}, "recursion_limit": 25}
    result3: dict[str, object] = agent.invoke(
        {"messages": [HumanMessage(content="请为「支付功能」生成测试用例")]},
        config=config_b,
    )
    text3: str = _last_text(result3)
    print(f"③ 第三轮（换 thread）：{text3[:120]}")
    print(f"   → {'✅ 隔离生效（新会话没串入旧会话的登录）' if ('登录' not in text3) else '⚠️ 串话了（thread_id 没隔离）'}")


def exp3_memory_persist() -> None:
    """实验 3：SqliteSaver 持久化——跨进程重启仍记得。

    原理：记忆写进 checkpoints.sqlite 文件；进程退出后文件还在，
    下次脚本运行用同一个 DB 连接 + 同一个 thread_id → 自动读档继续。

    ⚠️ 验证问题同样落在测试职责内（原因见 exp2 docstring）：
    第一轮为登录生成用例；第二轮问题里【不】提登录，必须靠 Sqlite 恢复的历史才知道。
    """
    print("=" * 60)
    print("实验 3：SqliteSaver 持久化（跨进程重启仍记得）")
    try:
        from langgraph.checkpoint.sqlite import SqliteSaver  # noqa: PLC0415
    except ImportError:
        print("   ❌ 缺包：先执行 pip install langgraph-checkpoint-sqlite")
        return

    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    agent = build_agent_v3(checkpointer)

    thread: str = "persist-session"
    config: RunnableConfig = {"configurable": {"thread_id": thread}, "recursion_limit": 25}
    # 本轮写一条记忆（如果之前跑过，重复跑也无妨——消息按 id 去重）
    agent.invoke(
        {"messages": [HumanMessage(content="请为「登录功能」生成测试用例")]},
        config=config,
    )
    result: dict[str, object] = agent.invoke(
        {"messages": [HumanMessage(content="我们刚才在测什么功能？继续为它补充 2 条异常场景用例")]},
        config=config,
    )
    text: str = _last_text(result)
    print(f"   本轮回复：{text[:120]}")
    print(f"   → {'✅ 记忆已持久化到 SQLite（记得 feature=登录）' if ('登录' in text) else '⚠️ 未命中（多跑几轮或检查 DB 路径）'}")
    print(f"   💡 重启进程（重新 python day26_checkpointer_memory.py 或新脚本同 DB + 同 thread）仍记得")
    conn.close()

if __name__ == "__main__":
    # exp1_smoke()
    # exp2_memory_in_process()
    exp3_memory_persist()
    print("\n💡 要点回顾：")
    print("   Agent v3 = v2 + checkpointer —— 一行解决 Day 25 遗留的'无对话记忆'")
    print("   thread_id 是会话身份证：同 id 共享记忆，异 id 完全隔离")
    print("   InMemorySaver 进程内；SqliteSaver 跨进程（真实项目用这个）")
    print("   记忆的本质 = 每次节点执行后存档，下次按 thread_id 读档继续")
