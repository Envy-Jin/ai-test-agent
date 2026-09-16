# FILE: day40_concurrency_lab.py
"""Day 40 练习3：把并发接到真实链上——`analyze_bug_batch_async`（教学原型）

练习 2 用的是假任务。这一步把"并发"接到**真实项目的调用形状**上，但**不调 API**：
用 LangChain 的 `RunnableLambda` 冒充分析链，跑通"分割 → 并发 → 收口"的骨架，
证明补丁的形状对了，再进步骤 5 把它落到 `day31_bug_analyzer.py`。

为什么先做原型：真实补丁要动 `day31_bug_analyzer`（一个 500+ 行的成品模块），
一旦在里面边改边试，出错时分不清是"并发写法错"还是"业务逻辑错"。
原型是"只留骨架的最小复现"——这是 Day 39 学到的做法（先证明形状，再落地）。

教学点：
  1. **并发改造的三种落点**（今天选第 2 种）：
     ① 改调用方（`analyze_bug_batch` 内部变 async）—— 影响面大，所有调用方要加 await；
     ② **新增 async 版本，保留同步版**（今天选）—— 零破坏，调用方按需选；
     ③ 在同步版里 `asyncio.run(...)` 包一层 —— 看起来"不用改调用方"，但
        **在已有事件循环里会炸**（`RuntimeError: asyncio.run() cannot be called from
        a running event loop`），且把"同步/异步"这件重要的事藏起来 → 不推荐。
  2. 链路里每一个可等待点都必须是"可 await 的"，否则并发退化成串行。
  3. 保留顺序：并发返回后仍要按原 sections 顺序装配结果（不能"谁快谁在前"）。
  4. ⚠️ **实测踩到的坑（写原型时真炸了一次）**：`RunnableLambda(协程函数)` 之后
     只能 `ainvoke`，不能 `invoke` —— 会抛
       `TypeError: Cannot invoke a coroutine function synchronously. Use `ainvoke` instead.`
     含义：**"是不是异步"是函数的固有属性，不是调用方的选择**。所以"串行基线"
     必须另写一个同步函数（本实验就是 `_slow_chain_sync`），不能拿同一个协程函数
     既 invoke 又 ainvoke。这条也解释了为什么"同步版批量分析"必须保留——
     它是另一条代码路径，不是"同一个函数的另一种调法"。

实验↔步骤↔运行命令：
  exp1_async_batch_shape() → 真实形状的并发批处理骨架（零 API）
  exp2_await_required()    → 反证：链路里放了同步阻塞 → 并发加速消失（零 API）
  main()                   → 两实验串跑
  运行（cd src/agent）：
    python -c "from day40_concurrency_lab import main; main()"
"""
from __future__ import annotations

import asyncio
import sys
import time
from typing import Any

from langchain_core.runnables import RunnableLambda

if sys.platform == "win32":
    _stdout: Any = sys.stdout
    _stdout.reconfigure(encoding="utf-8", errors="replace")

LATENCY_S: float = 0.15


def _split_reports(text: str) -> list[str]:
    """模拟 day31 的 `split_bug_reports`：按标题切段（确定性代码，不靠模型）。"""
    return [block.strip() for block in text.split("## BUG-") if block.strip()]


async def _one_analysis(chain: Any, section: str) -> str:
    """一条分析：走链路的 ainvoke（真实补丁里这里是 Chain.ainvoke）。"""
    out: Any = await chain.ainvoke(section)
    return str(out)


async def analyze_batch_async(chain: Any, sections: list[str]) -> list[str]:
    """并发版批量分析（= 未来 `day31.analyze_bug_batch_async` 的形状）。

    ⚠️ `asyncio.gather(*tasks)` 保序：返回 list 与 sections 一一对应。
    """
    tasks = [_one_analysis(chain, s) for s in sections]
    results: list[str] = await asyncio.gather(*tasks)
    return results


def exp1_async_batch_shape() -> None:
    """实验1：真实形状的并发批处理（用假链，零 API）。"""
    print("=" * 72)
    print("exp1_async_batch_shape：并发骨架（4 段 Bug 报告）")
    text: str = "".join(f"## BUG-{i:03d}\n登录接口返回 500\n" for i in range(1, 5))
    sections: list[str] = _split_reports(text)
    print(f"  分割得到 {len(sections)} 段")

    async def _slow_chain(x: Any) -> str:
        await asyncio.sleep(LATENCY_S)
        return f"分析<{str(x)[:12]}...>"

    chain = RunnableLambda(_slow_chain)

    # 串行基线：必须用**同步**函数（同一个协程函数不能 invoke，见下方 ⚠️）
    def _slow_chain_sync(x: Any) -> str:
        time.sleep(LATENCY_S)
        return f"分析<{str(x)[:12]}...>"

    t0: float = time.perf_counter()
    serial: list[str] = [str(RunnableLambda(_slow_chain_sync).invoke(s)) for s in sections]
    serial_s: float = time.perf_counter() - t0

    t1: float = time.perf_counter()
    concurrent: list[str] = asyncio.run(analyze_batch_async(chain, sections))
    concurrent_s: float = time.perf_counter() - t1

    print(f"  串行 {serial_s:.2f}s → 并发 {concurrent_s:.2f}s（加速 {serial_s / concurrent_s:.1f}x）")
    assert serial == concurrent, "并发结果与串行结果必须逐字一致（否则并发改变了语义）"
    assert concurrent_s < serial_s, "并发没变快"
    print("  ✅ 结果逐字一致 + 显著变快（并发不改变语义，只改变调度）")


def exp2_await_required() -> None:
    """实验2（反证）：链路里混入同步阻塞 → 并发形同虚设。"""
    print("=" * 72)
    print("exp2_await_required：阻塞调用如何杀死并发")

    async def _blocking_chain(x: Any) -> str:
        time.sleep(LATENCY_S)      # ⚠️ 同步 sleep：占着事件循环不撒手
        return f"blocking<{str(x)[:8]}>"

    chain = RunnableLambda(_blocking_chain)
    sections: list[str] = ["a", "b", "c", "d"]

    t0: float = time.perf_counter()
    asyncio.run(analyze_batch_async(chain, sections))
    blocked_s: float = time.perf_counter() - t0

    async def _proper_chain(x: Any) -> str:
        await asyncio.sleep(LATENCY_S)   # ✅ 可 await：等待期间让出事件循环
        return f"proper<{str(x)[:8]}>"

    t1: float = time.perf_counter()
    asyncio.run(analyze_batch_async(RunnableLambda(_proper_chain), sections))
    proper_s: float = time.perf_counter() - t1

    print(f"  链路含 time.sleep（阻塞）: {blocked_s:.2f}s  ← 退化回串行（≈4×{LATENCY_S}s）")
    print(f"  链路用 asyncio.sleep（让出）: {proper_s:.2f}s  ← 真并发（≈1×{LATENCY_S}s）")
    assert blocked_s > proper_s * 1.8, "阻塞竟然没拖慢，实验前提不成立"
    print("  ✅ 反证成立：**并发的前提是链路里每个等待点都可 await**")
    print("     落地检查表：有没有 `time.sleep` / 同步 `requests` / 同步 DB 驱动？")
    print("     有 → 换成 asyncio 版，或用 `await asyncio.to_thread(...)` 包起来。")


def main() -> None:
    exp1_async_batch_shape()
    exp2_await_required()
    print("=" * 72)
    print("✅ day40_concurrency_lab 两实验全过")


if __name__ == "__main__":
    main()