# FILE: day40_llm_cache.py
"""Day 40 练习1：给模型调用加持久化缓存（SQLite 自写 BaseCache 子类）

母计划 Day 40「性能优化 + 异步调用」的第一件事：**缓存**。
需求很朴素——同一个 prompt 问第二遍，不该再花一次钱、再等一次网络。

为什么自写而不是装现成的：
  · `langchain_community.cache.SQLiteCache` 能做同样的事，但 langchain-community
    官方已标注 sunset（实测导入即打 DeprecationWarning，指向 issue #674），
    且为本项目**新增一个顶层依赖**只为一张缓存表，不划算；
  · 本项目规范是「不用 langchain-community」（见 project 约定），保持一致。
所以：用**标准库 sqlite3** 实现 `BaseCache` 的三个抽象方法，落盘一个 db 文件。

LangChain 的缓存契约（读源码 `langchain_core/caches.py` 得到，不是猜的）：
  class BaseCache(ABC):
      def lookup(self, prompt: str, llm_string: str) -> RETURN_VAL_TYPE | None: ...
      def update(self, prompt: str, llm_string: str, return_val: RETURN_VAL_TYPE) -> None: ...
      def clear(self, **kwargs) -> None: ...
      async def alookup / aupdate / aclear: 默认实现 = run_in_executor 包同步版
  · **prompt**：本次请求的 prompt 文本（缓存键之一）
  · **llm_string**：模型参数的确定性字符串（缓存键之二）——LangChain 自动生成，
    目的正是防「同一 prompt 不同模型」串味。所以缓存是 (prompt, llm_string) 二键。
  · **return_val**：list[Generation]，不是 str。存 str 会丢元信息（token 数、
    generation_info），下次命中时 `AIMessage` 组装会缺字段。

教学点：
  1. 缓存的键是**二元组** (prompt, llm_string)，不是只按 prompt——改模型/改温度
     必须视为"另一个问题"，否则会拿到错误模型的答案。
  2. `set_llm_cache()` 是**全局**开关（写在 langchain_core.globals 里），设置后
     所有 Runnable 的 invoke 都走缓存；想对某个模型关掉 → 构造时 `cache=False`。
  3. **命中与否不改变返回值类型**：命中时拿到缓存里的同款对象，调用方无感。
     这正是"缓存该放在框架层"的理由——业务代码一行不用改。
  4. 落盘位置必须进 `.gitignore`（缓存是**可再生**的本地状态，不是资产）。
     本项目 `.gitignore` 已含 `*.sqlite`，但 `.db` 不在其中 → 今天要补一行。

实验↔步骤↔运行命令：
  exp1_cache_contract()  → 空缓存 lookup 返回 None；update 后能取回（纯内存，零 API）
  exp2_sqlite_roundtrip()→ 落盘 → 换一个实例读回 → 证明"跨进程持久"（零 API）
  exp3_hit_rate_demo()   → 用假 invoke 统计命中率（零 API）
  main()                 → 三实验串跑
  运行（cd src/agent）：
    python -c "from day40_llm_cache import main; main()"
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
from typing import Any
from contextlib import closing

from langchain_core.caches import BaseCache, RETURN_VAL_TYPE
from langchain_core.load.dump import dumps
from langchain_core.load.load import loads
from langchain_core.messages import AIMessage, AIMessageChunk
from langchain_core.outputs import ChatGeneration, Generation

if sys.platform == "win32":
    _stdout: Any = sys.stdout  # TextIO 静态类型缺 reconfigure → 经 Any 中转（禁 type: ignore）
    _stdout.reconfigure(encoding="utf-8", errors="replace")  # 防 GBK 崩

# 路径基准钉 __file__（2026-08-28 规范）：src/agent → 上两级 = 项目根
_AGENT_DIR: str = str(Path(__file__).resolve().parent)
_ROOT: Path = Path(_AGENT_DIR).parents[1]

# 缓存库位置（相对项目根，可提交的只有 .gitignore 规则，db 本身不入库）
CACHE_REL: str = ".cache/llm_cache.db"
CACHE_PATH: Path = _ROOT / ".cache" / "llm_cache.db"

# 反序列化白名单：**必须从真实载荷推导**，不能从"我以为的类型"推导。
#   LLM 路径载荷：[Generation]
#   Chat 路径载荷：[ChatGeneration(message=AIMessage)]   ← 今天接线才走到的路径
# Day 40 只放了 Generation → chat 模型一命中就抛
#   ValueError: Deserialization of ('langchain','schema','messages','AIMessage') is not allowed
# ⚠️ 注意 ChatGeneration 是 Generation 的**子类**，但白名单按"id 完全匹配"判定，
#    父类放行 ≠ 子类放行 → 必须逐个列出。
CACHE_ALLOWED_OBJECTS: list[type] = [Generation, ChatGeneration, AIMessage, AIMessageChunk]

class SQLiteLLMCache(BaseCache):
    """把 LLM 调用结果落进 SQLite 的 BaseCache 实现（标准库，零新依赖）。

    表结构：llm_cache(prompt TEXT, llm_string TEXT, response TEXT, PRIMARY KEY(prompt, llm_string))
      · 主键就是 LangChain 给的二元组 → 相同键自动覆盖，天然幂等；
      · response 存 `dumps(list[Generation])` 的 JSON 串（LangChain 官方序列化器），
        比 pickle 安全（不执行任意代码）、比手写 json 完整（保留 Generation 全字段）。
    """

    def __init__(self, db_path: str | Path = CACHE_PATH) -> None:
        self.db_path: str = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_table()
        # 命中统计（教学用：能算出命中率；生产上更该用 metrics/日志）
        self.hits: int = 0
        self.misses: int = 0

    def _connect(self) -> sqlite3.Connection:
        """每次操作新建连接。

        为什么不长期持有一个连接：SQLite 连接**不是线程安全**的，而 LangChain 的
        `batch()` 默认用线程池并发调用 → 共享连接会踩 "SQLite objects created in a
        thread can only be used in that same thread"。开连接很便宜（同进程本地文件），
        换来零并发问题，划算。
        """
        return sqlite3.connect(self.db_path)

    def _session(self) -> closing[sqlite3.Connection]:
        """开一个**用完必关**的连接（Day 41 修复）。

        ⚠️ 坑（Day 41 端到端冒烟时暴出来的）：原来写的是
           `with self._connect() as conn:` —— 这在 sqlite3 里**根本不关连接**！
           `Connection.__enter__/__exit__` 实现的是**事务**语义（提交/回滚），
           不是关闭语义。所以：连接对象只在局部变量出作用域后才被引用计数回收，
           而 `Connection` 与它派生的 `Cursor` 之间存在引用环 → **GC 不立刻回收**，
           文件句柄就一直挂着。

        实测症状：缓存操作做完后删临时目录报
           PermissionError [WinError 32] 另一个程序正在使用此文件: 'probe.db'
        —— 冒烟脚本的 `shutil.rmtree(..., ignore_errors=True)` 会**静默吞掉**这个错，
        于是"清理干净了"是假的（残留目录真真切切躺在 %TEMP% 里）。

        真实影响：一次链路要几十上百次模型调用 → 泄漏几十上百个连接/句柄；
        进程活着时缓存库文件被锁（改名/删除/换库全失败）。

        正确姿势二选一：`contextlib.closing(sqlite3.connect(...))`（本处采用，
        零缩进改动），或自己 try/finally 里 `conn.close()`。
        ⚠️ 事务语义不要丢：`closing()` 不提交，所以里面仍要保留 `with conn:` 的
           `with self._session() as conn, conn:` 写法，或改用显式 `conn.commit()`。
        """
        return closing(self._connect())

    def _init_table(self) -> None:
        with self._session() as conn, conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS llm_cache ("
                "  prompt TEXT NOT NULL,"
                "  llm_string TEXT NOT NULL,"
                "  response TEXT NOT NULL,"
                "  PRIMARY KEY (prompt, llm_string)"
                ")"
            )

    # ── BaseCache 契约三方法（同步；async 版由基类默认实现代理过来）──
    def lookup(self, prompt: str, llm_string: str) -> RETURN_VAL_TYPE | None:
        """命中 → 反序列化 Generation 列表；未命中 → None（基类约定）。"""
        with self._session() as conn, conn:
            row: tuple[str] | None = conn.execute(
                "SELECT response FROM llm_cache WHERE prompt = ? AND llm_string = ?",
                (prompt, llm_string),
            ).fetchone()
        if row is None:
            self.misses += 1
            return None
        self.hits += 1
        # loads 返回 Any → 经 list[Generation] 收窄（项目规范：逐层 isinstance）
        # ⚠️ 显式给 allowed_objects：LangChain 已公告默认值将来会变（实测打
        #    LangChainPendingDeprecationWarning），且显式白名单本身就是安全实践
        #    ——只允许反序列化缓存真会装的几类对象，别的一律拒绝。
        # Day 41 修复：白名单原来只有 Generation（= LLM 路径），chat 路径的载荷是
        #    ChatGeneration(AIMessage) → 一接进生产链就 ValueError（真实载荷见上）。
        loaded: Any = loads(row[0], allowed_objects=CACHE_ALLOWED_OBJECTS)
        if isinstance(loaded, list):
            return [g for g in loaded if isinstance(g, Generation)]
        return None

    def update(self, prompt: str, llm_string: str, return_val: RETURN_VAL_TYPE) -> None:
        """写入（幂等）：同键直接覆盖。"""
        payload: str = dumps(list(return_val))
        with self._session() as conn, conn:
            conn.execute(
                "INSERT OR REPLACE INTO llm_cache (prompt, llm_string, response) VALUES (?, ?, ?)",
                (prompt, llm_string, payload),
            )

    def clear(self, **kwargs: Any) -> None:
        """清空（BaseCache.clear 签名带 **kwargs，保持一致好让基类调用）。"""
        with self._session() as conn, conn:
            conn.execute("DELETE FROM llm_cache")
        self.hits = 0
        self.misses = 0

    # ── 教学辅助：命中率 / 条目数 ──
    def count(self) -> int:
        """当前缓存条目数（CLI `cache stats` 用）。"""
        with self._session() as conn, conn:
            row = conn.execute("SELECT COUNT(*) FROM llm_cache").fetchone()
        return int(row[0]) if row is not None else 0

    def stats(self) -> str:
        total: int = self.hits + self.misses
        rate: float = (self.hits / total * 100) if total else 0.0
        return f"命中 {self.hits} / 查询 {total}（命中率 {rate:.0f}%）"


def _fake_generation(text: str) -> Generation:
    """造一个 Generation 供零 API 实验用（真实调用时是模型返回的）。"""
    return Generation(text=text, generation_info={"finish_reason": "STOP"})


def exp1_cache_contract() -> None:
    """实验1：BaseCache 契约——空缓存返回 None；update 后按二元组取回（零 API）。"""
    print("=" * 72)
    print("exp1_cache_contract：缓存契约（lookup/update/clear）")
    cache = SQLiteLLMCache(CACHE_PATH)
    cache.clear()

    prompt: str = "请给登录功能写 3 条测试用例"
    llm_string: str = "ChatGoogleGenerativeAI(model=gemini-3.5-flash-lite)"

    miss = cache.lookup(prompt, llm_string)
    print(f"  空缓存 lookup → {miss!r}（期望 None）")
    assert miss is None, "空缓存必须返回 None"

    cache.update(prompt, llm_string, [_fake_generation("用例1/用例2/用例3")])
    hit = cache.lookup(prompt, llm_string)
    print(f"  update 后 lookup → {len(hit) if hit else 0} 个 Generation")
    assert hit is not None and hit[0].text == "用例1/用例2/用例3"

    # 关键教学点：换 llm_string（= 换模型）= 换问题 → 必须 miss
    other = cache.lookup(prompt, "ChatGoogleGenerativeAI(model=gemini-3.1-flash-lite)")
    print(f"  换模型后 lookup → {other!r}（期望 None：二元组键防串味）")
    assert other is None, "不同模型的同名 prompt 绝不该命中"

    # Generation 的元信息要能活着回来
    assert hit[0].generation_info == {"finish_reason": "STOP"}, "序列化丢了 generation_info"
    print("  ✅ 契约通过：二元组键 / 元信息保真 / None 语义都对")


def exp2_sqlite_roundtrip() -> None:
    """实验2：持久性——新实例（模拟新进程）能读到上次写的缓存（零 API）。"""
    print("=" * 72)
    print("exp2_sqlite_roundtrip：跨实例持久化")
    writer = SQLiteLLMCache(CACHE_PATH)
    writer.clear()
    writer.update("持久化探针", "llm-A", [_fake_generation("落盘的内容")])
    print(f"  写入实例 → {writer.stats()}")

    reader = SQLiteLLMCache(CACHE_PATH)  # 全新实例，只靠文件共享状态
    got = reader.lookup("持久化探针", "llm-A")
    print(f"  新实例读取 → {got[0].text if got else None!r}")
    assert got is not None and got[0].text == "落盘的内容", "跨实例没读到"

    size: int = CACHE_PATH.stat().st_size if CACHE_PATH.is_file() else 0
    print(f"  缓存文件 {CACHE_REL} = {size} B（>0 表示真的落盘了）")
    assert size > 0, "缓存文件不存在或为空"
    print("  ✅ 持久化通过（这就是「第二次调用不用花钱」的物理基础）")


def exp3_hit_rate_demo() -> None:
    """实验3：命中率统计——同一 prompt 问 3 次，只有第 1 次该"出网"（零 API）。"""
    print("=" * 72)
    print("exp3_hit_rate_demo：命中率（模拟 3 次相同请求）")
    cache = SQLiteLLMCache(CACHE_PATH)
    cache.clear()

    prompt: str = "分析这条 Bug：登录接口返回 500"
    llm_string: str = "chain-v1"
    api_calls: int = 0  # 出网计数（真实场景 = 花钱计数）

    for i in range(1, 4):
        cached = cache.lookup(prompt, llm_string)
        if cached is not None:
            print(f"  第 {i} 次：命中缓存 → {cached[0].text!r}（0 次出网）")
            continue
        api_calls += 1
        result: str = f"模型第 {api_calls} 次回答"
        print(f"  第 {i} 次：未命中 → 假装调模型（出网 {api_calls} 次）")
        cache.update(prompt, llm_string, [_fake_generation(result)])

    print(f"  {cache.stats()}")
    print(f"  ✅ 3 次请求只出网 {api_calls} 次（期望 1）")
    assert api_calls == 1, "缓存没起作用"


def main() -> None:
    exp1_cache_contract()
    exp2_sqlite_roundtrip()
    exp3_hit_rate_demo()
    print("=" * 72)
    print("✅ day40_llm_cache 三实验全过")


if __name__ == "__main__":
    main()