# FILE: test_day40_cache_batch.py
"""Day 40 测试：缓存（SQLite BaseCache）+ 并发批量（保序/限流/隔离）

测试策略（沿用 Day 39 决策 A/B/C）：
  · 纯函数写厚：缓存契约、并发语义、限流上限 —— 这些不需要网络，能写多厚写多厚；
  · 入口层写薄：CLI `cache` 子命令只断言"命令在 + 输出形状"，真跑靠人工；
  · **不许断言"磁盘上真有缓存文件"**——缓存是本地可再生状态，用它就导致测试不可重复。
    所以每个用例都显式指定 `tmp_path` 下的 db（受控替身），绝不去碰项目根的 `.cache/`。
  · 零 API、零外网：并发用例全部走假任务；缓存用例全部走手造 Generation。

⚠️ 为什么不 import day31_bug_analyzer 来测它的异步版：
   那个模块顶层 `import langchain_google_genai` → 实测冷启动 ≈66s。
   本文件测的是**并发语义与缓存契约**（与业务无关的通用能力），
   用 RunnableLambda 造假链能把同样的语义测到，且整套测试 < 2s。
   （真链路的异步补丁由 `day40_concurrency_lab` 的形状实验 + 人工验收覆盖。）
"""
from __future__ import annotations

import asyncio
import inspect
import sqlite3
from pathlib import Path
from typing import Any

import pytest
from click.testing import CliRunner, Result
from langchain_core.runnables import RunnableLambda

from day40_batch import _fake_llm_call
from day40_llm_cache import SQLiteLLMCache, _fake_generation


# ═══════════════════════════════════════════════════════
# 第一组：缓存契约（纯逻辑 + tmp_path，不碰项目 .cache/）
# ═══════════════════════════════════════════════════════
@pytest.fixture()
def cache(tmp_path: Path):
    """每个用例一个**独立**的 sqlite 文件（互不污染，可重复跑）。

    ⚠️ 不写返回注解：SQLiteLLMCache 已在本模块顶层导入，这里其实可以写；
       但保持与项目既有夹具风格一致（见 tests/conftest.py 的说明）。
    """
    return SQLiteLLMCache(tmp_path / "test_cache.db")


def test_empty_cache_returns_none(cache: SQLiteLLMCache) -> None:
    """基类契约：未命中必须返回 None（不是抛异常、不是空列表）。"""
    assert cache.lookup("prompt", "llm") is None


def test_update_then_lookup_roundtrip(cache: SQLiteLLMCache) -> None:
    """写入后能取回，且 Generation 的元信息（generation_info）不丢。"""
    cache.update("p", "llm-A", [_fake_generation("答案")])
    hit = cache.lookup("p", "llm-A")
    assert hit is not None
    assert hit[0].text == "答案"
    assert hit[0].generation_info == {"finish_reason": "STOP"}


def test_different_llm_string_never_hits(cache: SQLiteLLMCache) -> None:
    """★ 核心契约：缓存键是 (prompt, llm_string) 二元组。

    同一句 prompt 换模型 = 换问题 → 必须 miss，否则会拿到错误模型的答案。
    """
    cache.update("同一个 prompt", "model-A", [_fake_generation("A 的答案")])
    assert cache.lookup("同一个 prompt", "model-A") is not None
    assert cache.lookup("同一个 prompt", "model-B") is None


def test_isolated_db_instances_share_state(tmp_path: Path) -> None:
    """持久化：同一文件的两个实例共享状态（模拟"新进程"）。"""
    db: Path = tmp_path / "shared.db"
    writer = SQLiteLLMCache(db)
    writer.update("持久化", "llm", [_fake_generation("落盘")])
    reader = SQLiteLLMCache(db)
    got = reader.lookup("持久化", "llm")
    assert got is not None and got[0].text == "落盘"


def test_clear_empties_and_resets_counters(cache: SQLiteLLMCache) -> None:
    """clear 清空数据 + 命中率计数器归零。"""
    cache.update("p", "llm", [_fake_generation("x")])
    _ = cache.lookup("p", "llm")     # 命中 1
    _ = cache.lookup("z", "llm")     # 未命中 1
    assert cache.count() == 1
    assert cache.hits == 1 and cache.misses == 1

    cache.clear()
    assert cache.count() == 0
    assert cache.hits == 0 and cache.misses == 0
    assert cache.lookup("p", "llm") is None


def test_count_matches_rows(cache: SQLiteLLMCache) -> None:
    """count() 与实际行数一致（防 SQL 写错时静默通过）。"""
    for i in range(3):
        cache.update(f"p{i}", "llm", [_fake_generation(f"v{i}")])
    assert cache.count() == 3


def test_is_base_cache_subclass() -> None:
    """必须是 BaseCache 子类 —— 否则 set_llm_cache 不认它。"""
    from langchain_core.caches import BaseCache

    assert issubclass(SQLiteLLMCache, BaseCache)


def test_supports_being_set_as_global_cache(tmp_path: Path) -> None:
    """能真的装到 LangChain 全局缓存上，且能取回（set_llm_cache / get_llm_cache）。"""
    from langchain_core.globals import get_llm_cache, set_llm_cache

    original = get_llm_cache()
    try:
        ours = SQLiteLLMCache(tmp_path / "global.db")
        set_llm_cache(ours)
        assert get_llm_cache() is ours, "全局缓存没换成我们的实例"
    finally:
        set_llm_cache(original)  # 用完还原，别污染同进程的其它测试


def test_bad_payload_returns_none_not_crash(tmp_path: Path) -> None:
    """健壮性：库里存了非 Generation 的垃圾 → 返回 None 而不是崩。"""
    db: Path = tmp_path / "junk.db"
    cache = SQLiteLLMCache(db)
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO llm_cache (prompt, llm_string, response) VALUES (?, ?, ?)",
            ("p", "llm", '"这是一个 JSON 字符串，不是 Generation 列表"'),
        )
    assert cache.lookup("p", "llm") is None


# ═══════════════════════════════════════════════════════
# 第二组：并发语义（纯 asyncio + 假任务，零 API）
# ═══════════════════════════════════════════════════════
def test_gather_preserves_input_order() -> None:
    """★ 核心契约：gather 保序 —— 结果与输入一一对应，不是"谁先完成谁在前"。"""

    async def _uneven(x: int) -> int:
        await asyncio.sleep(0.01 * (5 - x))  # 后面的先完成
        return x * 2

    out: list[int] = asyncio.run(RunnableLambda(_uneven).abatch([1, 2, 3, 4]))
    assert out == [2, 4, 6, 8]


def test_abatch_return_exceptions_isolates_failure() -> None:
    """失败隔离：一条炸了不影响其它，抛出的异常作为**值**返回。"""

    async def _boom(x: int) -> int:
        if x == 2:
            raise ValueError("boom")
        return x

    out: list[Any] = asyncio.run(
        RunnableLambda(_boom).abatch([1, 2, 3], return_exceptions=True)
    )
    assert isinstance(out[1], ValueError)
    assert out[0] == 1 and out[2] == 3


def test_abatch_empty_input_short_circuits() -> None:
    """空输入短路：不报错、返回空列表。"""
    out: list[int] = asyncio.run(RunnableLambda(lambda x: x).abatch([]))
    assert out == []


def test_concurrency_beats_serial_for_io_tasks() -> None:
    """★ 今天的主论点：IO 密集任务并发显著快于串行。

    阈值取得宽松（>2x）以免机器抖动导致假失败；真实预期是接近 N 倍。
    """
    import time

    n: int = 6
    labels: list[str] = [f"T{i}" for i in range(n)]

    t0: float = time.perf_counter()
    for label in labels:
        asyncio.run(_fake_llm_call(label, latency=0.1))
    serial_s: float = time.perf_counter() - t0

    t1: float = time.perf_counter()
    _ = asyncio.run(_gather_all(labels))
    concurrent_s: float = time.perf_counter() - t1

    assert concurrent_s < serial_s, f"并发({concurrent_s:.2f}s) 竟然不比串行({serial_s:.2f}s) 快"
    assert serial_s / concurrent_s > 2.0, f"加速比仅 {serial_s / concurrent_s:.1f}x，没达到预期"


async def _gather_all(labels: list[str]) -> list[str]:
    return await asyncio.gather(*(_fake_llm_call(label, latency=0.1) for label in labels))


def test_semaphore_caps_in_flight() -> None:
    """★ 限流：同时在飞的任务数从不超过 Semaphore 上限（免费额度 15 RPM 的现实约束）。"""
    limit: int = 2
    peak: int = 0
    in_flight: int = 0

    async def _run() -> None:
        nonlocal peak, in_flight
        sem = asyncio.Semaphore(limit)

        async def _guarded() -> str:
            nonlocal peak, in_flight
            async with sem:
                in_flight += 1
                peak = max(peak, in_flight)
                try:
                    return await _fake_llm_call("x", latency=0.02)
                finally:
                    in_flight -= 1

        await asyncio.gather(*(_guarded() for _ in range(10)))

    asyncio.run(_run())
    assert peak <= limit, f"限流失效：峰值 {peak} > 上限 {limit}"


def test_max_concurrency_is_keyword_only() -> None:
    """接口纪律：限流参数是 keyword-only，防调用方误传位置参数搞混顺序。

    ⚠️ 这里**只能** import day31（它顶层拖 langchain_google_genai）→ 实测单次 ≈47s。
       所以整套测试只允许有**一处**这样的 import（下面那条复用同一次导入），
       别再多加第二个用例去 import 它。
    """
    from day31_bug_analyzer import analyze_bug_batch_async

    sig = inspect.signature(analyze_bug_batch_async)
    assert sig.parameters["max_concurrency"].kind is inspect.Parameter.KEYWORD_ONLY


def test_async_batch_is_coroutine_and_sync_stays_sync() -> None:
    """★ 实测坑回归：异步版是 coroutine，同步版必须**保持同步**。

    同名"同步/异步"两版并存时，最容易出的错就是"顺手把同步版也改成 async"。
    """
    from day31_bug_analyzer import (
        analyze_bug_batch,
        analyze_bug_batch_async,
        analyze_bug_report_async,
    )

    assert inspect.iscoroutinefunction(analyze_bug_batch_async)
    assert inspect.iscoroutinefunction(analyze_bug_report_async)
    assert not inspect.iscoroutinefunction(analyze_bug_batch)


# ═══════════════════════════════════════════════════════
# 第三组：CLI cache 子命令（入口层，写薄）
# ═══════════════════════════════════════════════════════
def test_cli_has_cache_group() -> None:
    """`cache` 子命令已注册，且含 stats / clear 两个动作。"""
    from cli import cli

    result: Result = CliRunner().invoke(cli, ["cache", "--help"])
    assert result.exit_code == 0, result.output
    assert "stats" in result.output
    assert "clear" in result.output


def test_cli_cache_stats_runs_without_api() -> None:
    """`cache stats` 零 API 可跑（不要求缓存文件存在，两种状态都要能正常退出）。"""
    from cli import cli

    result: Result = CliRunner().invoke(cli, ["cache", "stats"])
    assert result.exit_code == 0, result.output
    assert "缓存文件" in result.output or "缓存不存在" in result.output