"""
Day 21 练习 4：chat 子命令 —— 交互式对话 + 会话历史持久化（进阶）

把练习 3 的对话式问答（chat_turn）包装成交互式 REPL（命令行聊天界面）：
  python day21_kb_chat_cli.py --session-id s01

会话历史持久化（重启不丢，MEMORY 待办）：
  sessions.json 文件（{session_id: [{"role": ..., "content": ...}, ...]}）
  - 启动时加载 → 恢复到 InMemoryChatMessageHistory（restore_history）
  - 每轮对话结束 → 追加保存（save_sessions）

⚠️ Pyright 注意事项：
  - json.load 返回 Any → isinstance 校验后逐层转换为 dict[str, list[dict[str, str]]]
  - 文件不存在/损坏 → except 兜底返回空 dict（探测函数只返回空值，不 raise）
  - role/content 取值用 str() 显式转换（r 可能是任意 dict）
  - input() 循环用 try/except (EOFError, KeyboardInterrupt) 优雅退出

用法：命令行直接运行（见顶部示例）。
"""

import argparse
import json
import os
import sys

# Windows 下控制台/重定向输出统一 UTF-8，防止 emoji/中文打印报 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()

from langchain_core.chat_history import InMemoryChatMessageHistory

from day20_knowledge_loader import KNOWLEDGE_DIR, ensure_sample_data
from day21_kb_chat import chat_turn, get_session_history
from day21_kb_persist import KnowledgeIndexerV2


# ═══════════════════════════════════════════════════════
# 模块级：配置
# ═══════════════════════════════════════════════════════

CHROMA_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "chroma_db")
SESSION_FILE: str = os.path.join(os.path.dirname(__file__), "..", "..", "sessions.json")


# ═══════════════════════════════════════════════════════
# 会话持久化（JSON 文件）
# ═══════════════════════════════════════════════════════

def load_sessions(path: str = SESSION_FILE) -> dict[str, list[dict[str, str]]]:
    """从 JSON 文件加载会话历史（不存在/损坏 → 空 dict）。

    遵循项目规范：探测类函数只返回空值/None，不 raise。
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw: object = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

    if not isinstance(raw, dict):
        return {}

    sessions: dict[str, list[dict[str, str]]] = {}
    for sid, records in raw.items():
        if isinstance(records, list):
            cleaned: list[dict[str, str]] = []
            for r in records:
                if isinstance(r, dict):
                    cleaned.append(
                        {
                            "role": str(r.get("role", "user")),
                            "content": str(r.get("content", "")),
                        }
                    )
            sessions[str(sid)] = cleaned
    return sessions


def save_sessions(sessions: dict[str, list[dict[str, str]]], path: str = SESSION_FILE) -> None:
    """把会话历史写回 JSON 文件（ensure_ascii=False 保留中文）。"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sessions, f, ensure_ascii=False, indent=2)


def restore_history(history: InMemoryChatMessageHistory, records: list[dict[str, str]]) -> None:
    """把磁盘上的历史记录恢复到 InMemoryChatMessageHistory。"""
    for r in records:
        role: str = r["role"]
        content: str = r["content"]
        if role == "user":
            history.add_user_message(content)
        else:
            history.add_ai_message(content)


# ═══════════════════════════════════════════════════════
# 交互式 REPL
# ═══════════════════════════════════════════════════════

def run_chat(session_id: str) -> None:
    """交互式对话主循环（输入 exit / quit / q 退出）。"""
    ensure_sample_data()

    # 1. 恢复会话（磁盘 → 内存）
    sessions: dict[str, list[dict[str, str]]] = load_sessions()
    records: list[dict[str, str]] = sessions.get(session_id, [])
    history: InMemoryChatMessageHistory = get_session_history(session_id)
    restore_history(history, records)
    print(f"💬 会话 [{session_id}] 已恢复 {len(records)} 条历史记录")
    print("   输入 exit / quit / q 退出\n")

    # 2. 构建对话引擎（持久化索引器：有落盘则加载，无则建库）
    indexer: KnowledgeIndexerV2 = KnowledgeIndexerV2(
        root_dir=KNOWLEDGE_DIR, persist_directory=CHROMA_DIR
    )
    indexer.index()

    # 3. 对话循环
    while True:
        try:
            user_input: str = input("你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见")
            break

        if user_input in ("exit", "quit", "q"):
            print("👋 再见")
            break
        if not user_input:
            continue

        answer: str = chat_turn(indexer, session_id, user_input)
        print(f"\n🤖 {answer}\n")

        # 4. 保存会话（内存 → 磁盘，每轮落盘）
        records.append({"role": "user", "content": user_input})
        records.append({"role": "assistant", "content": answer})
        sessions[session_id] = records
        save_sessions(sessions)


# ═══════════════════════════════════════════════════════
# argparse 入口
# ═══════════════════════════════════════════════════════

def build_parser() -> argparse.ArgumentParser:
    """构建解析器：--session-id 指定会话（默认 default）。"""
    parser = argparse.ArgumentParser(
        prog="kb-chat",
        description="智能测试知识库 —— 交互式对话（Day 21）",
    )
    parser.add_argument("--session-id", default="default", help="会话 ID（默认 default）")
    return parser


if __name__ == "__main__":
    parser = build_parser()
    args: argparse.Namespace = parser.parse_args()
    session_id: str = str(args.session_id)
    run_chat(session_id)