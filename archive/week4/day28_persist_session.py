"""
Day 28 练习 4：SqliteSaver 跨进程会话 —— 记忆写进文件，重启进程读档继续

实验契约（同一个 DB 文件 + 同一个 thread_id = 同一段会话）：
  python day28_persist_session.py write    # 第一次运行：起 mock → 两轮对话 → 记忆落盘
  # 关掉进程（Ctrl+C / 关闭终端 / 重启电脑）
  python day28_persist_session.py verify   # 第二次运行（新进程）：同 DB 同 thread 读档 → 验证记忆

对比 Day 26 exp3（v3 + SqliteSaver(conn) 无 serde）：
  今天 = v4（TestReport）+ SqliteSaver(conn, serde=make_serde())
  → msgpack 白名单注册，反序列化不再警告（Day 26 教训：make_serde 在持久化场景才真正派上用场）

进阶（实测可用，注意绝对路径）：
  with SqliteSaver.from_conn_string(os.path.abspath(db_path)) as cp:
      agent = build_agent_v4(cp)   # 上下文管理自动建库建表 + 自动关连接

⚠️ ToolStrategy 停机机制：verify 的"复述结论"也要设计成测试任务（交 TestReport 才能停机）。
"""
import argparse
import os
import sqlite3
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()  # ⚠️ 必须在 langchain import 之前

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver

from day27_multi_tool_agent import build_agent_v4, extract_report, make_serde
from day27_report import render_test_report
from day28_mock_api import start_mock, stop_mock

# ═══════════════════════════════════════════════════════
# 常量
# ═══════════════════════════════════════════════════════

DB_PATH: str = os.path.join(os.path.dirname(__file__), "..", "..", "checkpoints.sqlite")
THREAD_ID: str = "persist-login"
PORT: int = 8766


def build_sqlite_agent(db_path: str = DB_PATH):
    """v4 + SqliteSaver（conn 手动管理，serde 注册 TestReport/ReportItem）。

    ⚠️ 返回注解留空（Day 26 口诀 25）：让 pyright 推断 CompiledStateGraph。
    ⚠️ check_same_thread=False：SqliteSaver 内部可能跨线程访问连接（Day 26 教训）。
    ⚠️ conn 生命周期：agent 构建后 checkpointer 持有 conn，进程结束前才 close；
       提前 close → 后续 invoke 抛 "Cannot operate on a closed database"。
    """
    conn = sqlite3.connect(db_path, check_same_thread=False)
    return build_agent_v4(SqliteSaver(conn, serde=make_serde())), conn


# ═══════════════════════════════════════════════════════
# write：写档（第一次运行）
# ═══════════════════════════════════════════════════════

def cmd_write() -> None:
    """第一次运行：起 mock → v4+SqliteSaver → 第一轮测登录 → 第二轮追问 → 记忆落盘。"""
    print("=" * 60)
    print(f"write 子命令：会话写入 {DB_PATH}（thread_id={THREAD_ID}）")
    server = start_mock(PORT)
    try:
        agent, conn = build_sqlite_agent()
        config: RunnableConfig = {"configurable": {"thread_id": THREAD_ID}, "recursion_limit": 50}
        # 第一轮：测登录接口（凭据走 kb_search）
        instruction1: str = (
            f"请为「用户登录」接口 http://127.0.0.1:{PORT}/api/login 做接口测试：\n"
            "1. 先用 kb_search 查询该接口的测试账号\n"
            "2. 生成 3 条用例：正确账号密码登录（期望 200）/ 密码少于8位（期望 400）/ 错误凭据（期望 401）\n"
            "3. 用 run_api_test 逐条执行（method=POST，payload 传 JSON 字符串，凭据用知识库里查到的测试账号）\n"
            "4. 结果整理成 TestReport 输出"
        )
        result1: dict[str, object] = agent.invoke(
            {"messages": [HumanMessage(content=instruction1)]}, config=config
        )
        print("  ① 第一轮：登录接口测试完成（若之前 verify 过，消息按 id 去重不会重复）")

        # 第二轮：追问补测（验证同进程记忆 + 写入更多 checkpoint）
        instruction2: str = (
            "很好。请再补充 2 条边界用例：① 空手机号（期望 400）② 手机号格式错误（期望 400）。\n"
            "用 run_api_test 执行后，**只输出新增用例**的 TestReport（feature 填 '用户登录-补充测试'）"
        )
        result2: dict[str, object] = agent.invoke(
            {"messages": [HumanMessage(content=instruction2)]}, config=config
        )
        print("  ② 第二轮：追问补测完成（增量 TestReport）")
        report = extract_report(result2)
        if report is not None:
            print(render_test_report(report)[:400])
        print("  ③ 记忆已写入 SQLite，现在可以【关掉本进程】再跑 verify 子命令")
        conn.close()
    finally:
        stop_mock()


# ═══════════════════════════════════════════════════════
# verify：读档（第二次运行，新进程）
# ═══════════════════════════════════════════════════════

def cmd_verify() -> None:
    """第二次运行（新进程）：同 DB + 同 thread_id → 模型从磁盘恢复记忆 → 复述上一轮结论。

    验证点：不重新执行接口测试（不起 mock），模型必须靠 SQLite 恢复的
    历史消息知道"测的是登录、接口地址、凭据、结论"——feature/base_url
    与上一轮一致才证明读档成功。
    """
    print("=" * 60)
    print(f"verify 子命令：从 {DB_PATH} 读档（thread_id={THREAD_ID}，新进程）")
    agent, conn = build_sqlite_agent()
    try:
        config: RunnableConfig = {"configurable": {"thread_id": THREAD_ID}, "recursion_limit": 50}
        instruction: str = (
            "我们上一轮在测哪个接口？请用 TestReport 复述上一轮的测试结论：\n"
            "1. **不要调用 run_api_test 重新执行测试**\n"
            "2. feature 必须填上一轮被测的功能模块名，base_url 必须填上一轮的接口地址（凭记忆，不是编的）\n"
            "3. items 复述上一轮的核心用例与执行结果，conclusion 复述上一轮结论"
        )
        result: dict[str, object] = agent.invoke(
            {"messages": [HumanMessage(content=instruction)]}, config=config
        )
        report = extract_report(result)
        if report is None:
            print("❌ 未拿到 TestReport（模型可能没理解'复述'任务，打开 LangSmith 看）")
            return
        feature_ok: bool = "登录" in report.feature
        url_ok: bool = str(report.base_url or "").startswith(f"http://127.0.0.1:{PORT}")
        print(f"  feature={report.feature!r}  base_url={report.base_url!r}  items={len(report.items)} 条")
        print(f"  → {'✅ 跨进程记忆恢复成功（记得测的是登录接口）' if (feature_ok and url_ok) else '❌ 记忆未恢复（检查 DB 路径/thread_id 一致性）'}")
        print(render_test_report(report)[:500])
    finally:
        conn.close()




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Day 28 练习 4：SqliteSaver 跨进程会话")
    parser.add_argument("cmd", choices=["write", "verify"], help="write=写档（第一次运行）；verify=读档验证（新进程）")
    args = parser.parse_args()
    if args.cmd == "write":
        cmd_write()
    else:
        cmd_verify()
