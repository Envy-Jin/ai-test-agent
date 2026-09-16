# FILE: day40_batch.py
"""Day 40 练习2：异步批量调用（串行 for → asyncio.gather 并发）

母计划 Day 40 的第二件事：**异步批量处理**。原文给的形态是：
    tasks = [generate_cases_async(req) for req in requirements]
    results = await asyncio.gather(*tasks, return_exceptions=True)
今天把它落到本项目的真实缺口上——`day31_bug_analyzer.analyze_bug_batch`：

    def analyze_bug_batch(text: str) -> list[BugAnalysis]:
        sections = split_bug_reports(text)
        return [analyze_bug_report(section) for section in sections]   # ← 串行！

N 条 Bug = N 次串行网络往返。**模型调用是 IO 密集（等网络），不是 CPU 密集**——
这正是并发能赢的场景，也是为什么"加速"在这里不需要加机器/换模型，
只需要改**调度方式**：把"发一个等一下"改成"一起发一起等"。

为什么用 asyncio 而不是多线程/多进程（三个方案对比，Day 40 决策 C）：
  · 多进程：模型调用不占 CPU → 开进程纯亏（进程启动 + 内存复制）；
  · 多线程：可行，但 Python 线程模型下"每个请求一个线程"在 N 大时线程开销显著，
    且本项目已有 `abatch`（LangChain 原生异步）可用 → 没必要自己管线程池；
  · asyncio：单线程事件循环，等待期间让出控制权 → 内存开销小、天然适合 IO。
    ⚠️ 前提：**整条链路上不许有阻塞调用**（time.sleep / 同步 requests 会卡死事件循环）。

⚠️ 本项目的一个真实约束（必须知道，否则以为"并发了却没变快"）：
  `Gemini API` 免费额度约 15 RPM（母计划附录原话「Flash 模型每分钟 15 次」）→
  一次并发 10 条请求会**撞限流**。所以今天除了并发，还要讲**限流**：
  `asyncio.Semaphore(n)` 控制同时在飞的数量，把"快"约束在配额内。

教学点：
  1. `asyncio.gather(*tasks, return_exceptions=True)` 把 N 个协程并发跑，
     **返回值顺序与传入顺序严格一致**（不是"谁先完成谁在前"）；
  2. `return_exceptions=True` = 失败不炸整批（拿到的是 Exception 对象，自己筛）——
     与"失败隔离"是同一思想在并发世界的对应物；
  3. 事件循环里绝不能有阻塞调用；`time.sleep` → `asyncio.sleep`，
     同步库 → `asyncio.to_thread(...)`；
  4. 并发上限用 `Semaphore`，不用"手写计数器"——它自带公平排队语义；
  5. **并发 ≠ 一定更快**：单条任务太轻（计算密集/极短）时，协程调度开销反而更贵。
     今天用实验量化这条边界（exp4）。

实验↔步骤↔运行命令：
  exp1_serial_vs_async()  → 同一批假任务：串行 vs 并发，量出加速比（零 API）
  exp2_abatch_contract()  → LangChain 原生 abatch 的语义（顺序/异常/空列表）（零 API）
  exp3_semaphore_limit()  → Semaphore 限流：验证"同时在飞"从不超过 N（零 API）
  exp4_light_vs_heavy()   → 边界：任务极轻时并发反而慢（量化，零 API）
  main()                  → 四实验串跑
  运行（cd src/agent）：
    python -c "from day40_batch import main; main()"
"""
from __future__ import annotations

import asyncio
import sys
import time
from typing import Any

from langchain_core.runnables import RunnableLambda

if sys.platform == "win32":
    _stdout: Any = sys.stdout  # TextIO 静态类型缺 reconfigure → 经 Any 中转（禁 type: ignore）
    _stdout.reconfigure(encoding="utf-8", errors="replace")  # 防 GBK 崩

# 模拟每条请求的网络延迟（真实场景 = 模型响应时间）
FAKE_LATENCY_S: float = 0.25


async def _fake_llm_call(label: str, latency: float = FAKE_LATENCY_S) -> str:
    """假装一次模型调用：只 sleep，不联网（asyncio.sleep 会**让出**事件循环）。"""
    await asyncio.sleep(latency)
    return f"{label} 的分析结果"


def _fake_llm_call_sync(label: str, latency: float = FAKE_LATENCY_S) -> str:
    """对照物：同步版本（time.sleep 是**阻塞**的 → 并发时会把事件循环卡死）。"""
    time.sleep(latency)
    return f"{label} 的分析结果"


# ── 实验1：串行 vs 并发 ──
async def exp1_serial_vs_async() -> float:
    """同一批任务两种跑法：串行总耗时 ≈ N×latency；并发 ≈ 1×latency。"""
    print("=" * 72)
    print("exp1_serial_vs_async：串行 vs 并发（8 个任务，每个 0.25s）")
    labels: list[str] = [f"BUG-{i:03d}" for i in range(1, 9)]

    t0: float = time.perf_counter()
    for label in labels:
        _fake_llm_call_sync(label)
    serial_s: float = time.perf_counter() - t0

    t1: float = time.perf_counter()
    # ★ 并发核心三行：建协程 → gather → 收结果（顺序与 labels 一致）
    tasks = [_fake_llm_call(label) for label in labels]
    results: list[str] = await asyncio.gather(*tasks)
    async_s: float = time.perf_counter() - t1

    speedup: float = serial_s / async_s if async_s else 0.0
    print(f"  串行（同步 for）: {serial_s:.2f}s")
    print(f"  并发（gather）  : {async_s:.2f}s")
    print(f"  加速比: {speedup:.1f}x（理论上限 ≈ 任务数 {len(labels)}）")
    assert len(results) == len(labels), "结果数量不对"
    assert results[0].startswith("BUG-001"), "gather 结果顺序必须与传入一致"
    assert speedup > 3.0, f"并发没生效（加速比 {speedup:.1f}x）"
    print(f"  ✅ 顺序一致 + 加速 {speedup:.1f}x")
    return speedup


# ── 实验2：LangChain 原生 abatch 契约 ──
async def exp2_abatch_contract() -> None:
    """abatch 的语义：保序 / return_exceptions / 空列表短路（零 API）。"""
    print("=" * 72)
    print("exp2_abatch_contract：Runnable.abatch 语义")

    async def _double(x: int) -> int:
        await asyncio.sleep(0.01 * (5 - x))  # 故意让"后面的先完成"，验证保序
        return x * 2

    chain = RunnableLambda(_double)
    out: list[int] = await chain.abatch([1, 2, 3, 4])
    print(f"  abatch([1,2,3,4]) → {out}")
    assert out == [2, 4, 6, 8], "abatch 必须保序（与输入同序）"

    # return_exceptions=True：失败不炸整批
    async def _boom(x: int) -> int:
        if x == 3:
            raise ValueError(f"x={x} 炸了")
        return x

    mixed = await RunnableLambda(_boom).abatch([1, 2, 3, 4], return_exceptions=True)
    kinds: list[str] = [type(v).__name__ for v in mixed]
    print(f"  return_exceptions=True → {kinds}")
    assert isinstance(mixed[2], ValueError), "第 3 项应拿到异常对象而不是抛出去"
    assert mixed[0] == 1 and mixed[3] == 4, "其余项应正常返回"

    empty: list[int] = await chain.abatch([])
    print(f"  abatch([]) → {empty}（空输入短路，不报错）")
    assert empty == []
    print("  ✅ 保序 / 异常不炸批 / 空输入 三条契约都对")


# ── 实验3：Semaphore 限流 ──
async def exp3_semaphore_limit() -> None:
    """限流：用 Semaphore 把「同时在飞」压在 N 以内（免费额度 15 RPM 的现实约束）。"""
    print("=" * 72)
    print("exp3_semaphore_limit：Semaphore 限流（12 个任务，最多 3 个同时在飞）")
    limit: int = 3
    sem = asyncio.Semaphore(limit)
    in_flight: int = 0
    peak: int = 0

    async def _guarded(label: str) -> str:
        nonlocal in_flight, peak
        async with sem:                      # ← 只在拿到许可时进入
            in_flight += 1
            peak = max(peak, in_flight)
            try:
                return await _fake_llm_call(label, latency=0.05)
            finally:
                in_flight -= 1               # 无论成功失败都要归还

    t0: float = time.perf_counter()
    results: list[str] = await asyncio.gather(*(_guarded(f"S{i}") for i in range(12)))
    elapsed: float = time.perf_counter() - t0

    print(f"  完成 {len(results)} 个任务，耗时 {elapsed:.2f}s")
    print(f"  同时在飞峰值 = {peak}（上限 {limit}）")
    assert peak <= limit, f"限流失效：峰值 {peak} > {limit}"
    print("  ✅ 峰值未越界（这就是把『快』关进配额笼子的办法）")


# ── 实验4：并发边界（任务极轻时并发反而慢）──
async def exp4_light_vs_heavy() -> None:
    """量化边界：任务几乎不等待时，协程调度开销 > 省下的等待。"""
    print("=" * 72)
    print("exp4_light_vs_heavy：并发不是万灵药（极轻任务对照）")
    n: int = 200

    t0: float = time.perf_counter()
    for _ in range(n):
        _fake_llm_call_sync("x", latency=0.0)   # 纯计算，无等待
    serial_s: float = time.perf_counter() - t0

    t1: float = time.perf_counter()
    await asyncio.gather(*(_fake_llm_call("x", latency=0.0) for _ in range(n)))
    async_s: float = time.perf_counter() - t1

    ratio: float = async_s / serial_s if serial_s else 0.0
    print(f"  {n} 个零延迟任务：串行 {serial_s * 1000:.1f}ms / 并发 {async_s * 1000:.1f}ms")
    print(f"  比值 = {ratio:.2f}（>1 表示并发更慢）")
    print("  💡 结论：**并发赢的是『等待时间』，不是『计算量』**——任务越轻、等待越少，")
    print("     协程调度开销占比越高。判断标准是『这条任务有多少时间是纯等待』。")
    # 不断言方向（机器抖动会让比值在 1 附近摆动），只把现象摆出来
    print("  ✅ 现象已量化（本机实测见文档附录，不做硬断言）")


async def _amain() -> None:
    await exp1_serial_vs_async()
    await exp2_abatch_contract()
    await exp3_semaphore_limit()
    await exp4_light_vs_heavy()


def main() -> None:
    """三实验串跑（asyncio.run 是同步世界与异步世界的唯一入口）。"""
    asyncio.run(_amain())
    print("=" * 72)
    print("✅ day40_batch 四实验全过")


if __name__ == "__main__":
    main()