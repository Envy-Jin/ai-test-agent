"""
Day 28 练习 5：第 4 周目标验收清单 + Pyright 避坑演示

实验 1：能力矩阵验收——对照学习计划"周目标检验"，检测 Day 22-28 关键交付物
  三级验证强度：
    ① 文件存在（弱）：os.path.isfile
    ② 模块可解析（中）：importlib.util.find_spec（只解析不执行，零副作用）
    ③ 符号可导入（强）：真 import + getattr（会执行模块级代码，如 llm 构造——需要 .env 的 key）
  输出 Markdown 验收清单。

实验 2：Pyright 避坑演示
  坑 1：多轮会话 messages 是混合容器（System/Human/AI/Tool）→ 取 AI 文本要 isinstance 收窄
        （AIMessage.content 可能是 str 或 content blocks 列表）
  坑 2：merge_reports 拼接后仍要过 Pydantic 校验——外部数据（dict）进模型用 model_validate，
        字段缺失/类型错 → ValidationError（模型构造的缺参由 pyright 静态拦住，运行时不触发）
  坑 3：SqliteSaver 持有 sqlite conn → 进程结束才 close；from_conn_string 上下文管理自动关

用法：
  python day28_week4_review.py                  # 默认验收（文件存在 + 模块解析）
  python day28_week4_review.py --deep           # 深度验收（真 import + 符号检查）
  python day28_week4_review.py --demo           # 只跑避坑演示
  环境变量 AI_TEST_AGENT_DIR 可覆盖被测目录（冒烟测试用）
"""
import importlib.util
import os
import sys
from importlib.machinery import ModuleSpec

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field, ValidationError

# ═══════════════════════════════════════════════════════
# 常量：能力矩阵（周目标 → Day 22-28 交付物）
# ═══════════════════════════════════════════════════════

AGENT_DIR: str = os.environ.get("AI_TEST_AGENT_DIR", os.path.dirname(os.path.abspath(__file__)))

# (周目标, 文件名, 关键符号, 验收说明)
CAPABILITY_MATRIX: list[tuple[str, str, str, str]] = [
    ("理解 ReAct 和 Function Calling 两种 Agent 模式", "day22_agent_multi.py", "build_multi_tool_agent", "Day 22 预置工具 Agent"),
    ("能自定义 Tool 并注册到 Agent", "day23_case_tools.py", "generate_test_cases", "Day 23 自定义工具"),
    ("能用结构化输出拿到 Pydantic 数据", "day24_case_agent.py", "TestCaseBundle", "Day 24 结构化输出"),
    ("能配置 LangSmith 可视化追踪", "day25_langsmith_tracing.py", "check_tracing_env", "Day 25 LangSmith"),
    ("能给 Agent 加模型级容错（重试+备用模型）", "day25_test_agent_v2.py", "ModelRetryMiddleware", "Day 25 容错"),
    ("理解 LangGraph 状态机 + Agent 记忆", "day26_state_graph.py", "StateGraph", "Day 26 状态图"),
    ("自然语言 → 规划 → 调工具 → Markdown 报告", "day27_multi_tool_agent.py", "build_agent_v4", "Day 27 端到端 v4"),
    ("多轮追问 / 失败重测 / 持久化会话", "day28_persist_session.py", "SqliteSaver", "Day 28 打磨收官"),
]


# ═══════════════════════════════════════════════════════
# 实验 1：能力矩阵验收
# ═══════════════════════════════════════════════════════

def _file_exists(filename: str) -> bool:
    return os.path.isfile(os.path.join(AGENT_DIR, filename))


def _module_resolvable(filename: str) -> bool:
    """模块可解析：find_spec 只解析不执行（比 import 安全，模块级代码不跑）。"""
    module_name: str = filename.removesuffix(".py")
    spec: ModuleSpec | None = importlib.util.find_spec(module_name)
    return spec is not None


def _symbol_importable(filename: str, symbol: str) -> bool:
    """符号可导入：真 import + getattr（会执行模块级代码——需要 .env 的 key）。"""
    module_name: str = filename.removesuffix(".py")
    try:
        module = importlib.import_module(module_name)
        return hasattr(module, symbol)
    except Exception:
        return False


def exp1_review(deep: bool = False) -> None:
    """实验 1：能力矩阵验收，输出 Markdown 清单。"""
    print("=" * 60)
    print(f"实验 1：第 4 周能力矩阵验收（目录: {AGENT_DIR}）")
    if deep:
        print("  深度模式：文件存在 + 模块解析 + 符号导入（会执行模块级代码）")
    lines: list[str] = ["# 第 4 周能力矩阵验收清单", "", "| 周目标 | 交付物 | 验收 | 说明 |", "|--------|--------|------|------|"]
    passed: int = 0
    for goal, filename, symbol, note in CAPABILITY_MATRIX:
        exists: bool = _file_exists(filename)
        resolvable: bool = exists and _module_resolvable(filename)
        if deep:
            symbol_ok: bool = resolvable and _symbol_importable(filename, symbol)
            ok: bool = exists and resolvable and symbol_ok
        else:
            ok = exists and resolvable
        passed += 1 if ok else 0
        mark: str = "✅" if ok else "❌"
        detail: str = f"{note}（{filename}: {symbol}）"
        lines.append(f"| {goal} | {filename} | {mark} | {detail} |")
    lines.append("")
    lines.append(f"**验收结果：{passed}/{len(CAPABILITY_MATRIX)} 项达成**")
    print("\n".join(lines))
    print(f"\n→ {'✅ 第 4 周目标全部达成，可以进入第 5 周' if passed == len(CAPABILITY_MATRIX) else '❌ 有未达成项，回看对应 Day 文档'}")

    # 落到 docs/day28_notes.md 同目录的验收文件（可交付）
    out_dir: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "outputs")
    os.makedirs(out_dir, exist_ok=True)
    out_path: str = os.path.join(out_dir, "week4_review.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"  验收清单已保存: {out_path}")


# ═══════════════════════════════════════════════════════
# 实验 2：Pyright 避坑演示
# ═══════════════════════════════════════════════════════

class _DemoItem(BaseModel):
    """避坑演示用：model_validate 外部 dict 时字段缺失/类型错会触发 ValidationError。"""

    id: str = Field(description="编号")
    status: str = Field(description="PASS/FAIL")


def _ai_text(msg: object) -> str | None:
    """坑 1：AIMessage.content 可能是 str 或 content blocks 列表（Day 27 后模型常见 list）。"""
    if not isinstance(msg, AIMessage):
        return None
    content: object = msg.content
    if isinstance(content, str):
        return content[:100]
    if isinstance(content, list):
        parts: list[str] = [str(block.get("text", "")) for block in content if isinstance(block, dict)]
        return "".join(parts)[:100]
    return None


def exp2_pyright_demos() -> None:
    """实验 2：三个今日新坑演示（纯逻辑，零 API）。"""
    print("=" * 60)
    print("实验 2：Pyright 避坑演示")

    # 坑 1：messages 累积 + isinstance 收窄
    from langchain_core.messages import HumanMessage  # noqa: PLC0415

    mixed: list[object] = [
        HumanMessage(content="第一轮：测登录"),
        AIMessage(content=[{"type": "text", "text": "我调用工具后返回了结果"}]),  # content blocks
        AIMessage(content="第二轮结论：全部通过"),
    ]
    last_text: str | None = _ai_text(mixed[-1])
    print(f"  坑1 messages 累积收窄：最后一条 AI 文本 = {last_text!r}")
    assert last_text is not None and "第二轮" in last_text

    # 坑 2：Pydantic 合并/外部数据校验（model_validate 从 dict 进模型）
    raw: dict[str, object] = {"id": "TC001", "status": 123}  # status 类型错（应为 str）
    try:
        _DemoItem.model_validate(raw)
        print("  坑2 Pydantic 校验：❌ 没报错（意外）")
    except ValidationError as exc:
        print(f"  坑2 Pydantic 校验：✅ 类型错误被拦截（{len(exc.errors())} 个字段错误）")

    # 坑 3：SqliteSaver 连接生命周期（只讲不跑，避免引入 sqlite 副作用）
    print("  坑3 SqliteSaver conn 生命周期：")
    print("     conn = sqlite3.connect(path, check_same_thread=False) → SqliteSaver(conn, serde=...)")
    print("     构建期自动建表；进程结束前才 conn.close()；提前 close → invoke 抛 'closed database'")
    print("     进阶：with SqliteSaver.from_conn_string(os.path.abspath(db)) 自动建库+自动关（长驻进程慎用）")
    print("✅ 三个避坑演示完成")


def main() -> None:
    import argparse  # noqa: PLC0415

    parser = argparse.ArgumentParser(description="Day 28 练习 5：第 4 周目标验收 + 避坑演示")
    parser.add_argument("--deep", action="store_true", help="深度验收（真 import + 符号检查）")
    parser.add_argument("--demo", action="store_true", help="只跑避坑演示")
    args = parser.parse_args()
    if args.demo:
        exp2_pyright_demos()
        return
    exp1_review(deep=args.deep)
    exp2_pyright_demos()


if __name__ == "__main__":
    main()
