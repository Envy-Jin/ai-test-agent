# FILE: day41_cache_wiring.py
"""Day 41 练习 2：把 Day 40 造好的缓存零件**接进生产链**。

Day 40 的产出是一颗零件：`SQLiteLLMCache`（一个能落盘的 `BaseCache` 子类）。
零件造好了，但**全项目没有一处 `set_llm_cache`** → 实测收益为零。
今天补的就是那根线。

接线要回答三个问题（读源码 + 实测得到答案，不是猜的）：
  ① 装在哪一层？—— **进程级全局**（`langchain_core.globals._llm_cache`）。
     `ChatGoogleGenerativeAI._generate_with_cache` 每次调用都现读
     `get_llm_cache()`，**不是构造时快照** → 先建模型、后 `set_llm_cache`
     一样生效；业务代码一行不改就白拿缓存。
  ② 为什么"在执行器里 set 一次"不够？—— 执行器（day34）是**子进程**跑模型段
     （`subprocess.run([sys.executable, "-c", cmd])`）。全局变量不跨进程，
     父进程装了子进程看不见 → 必须把"装缓存"这段代码**注入子进程**。
     本模块的 `cache_prefix()` 就是那一段（执行器把它拼在 cmd 前面）。
  ③ 关了怎么办？—— 入口层给开关（`cli.py run --no-cache`）；单模型关用
     `cache=False` 构造参数。⚠️ 反过来的坑：`cache=True` 而全局没装 →
     直接 `ValueError: Asked to cache, but no cache found at 'langchain.cache'`。

实验↔步骤↔运行命令（全部零 API）：
  exp1_install_contract()   步骤3  python -c "from day41_cache_wiring import exp1_install_contract; exp1_install_contract()"
  exp2_cache_hits()         步骤3  python -c "from day41_cache_wiring import exp2_cache_hits; exp2_cache_hits()"
  exp3_subprocess_prefix()  步骤3  python -c "from day41_cache_wiring import exp3_subprocess_prefix; exp3_subprocess_prefix()"
  main()                    步骤3  python day41_cache_wiring.py
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from langchain_core.caches import BaseCache
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.globals import get_llm_cache, set_llm_cache
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from day40_llm_cache import CACHE_PATH, SQLiteLLMCache

if sys.platform == "win32":
    _stdout: Any = sys.stdout  # TextIO 静态类型缺 reconfigure → 经 Any 中转（禁 type: ignore）
    _stdout.reconfigure(encoding="utf-8", errors="replace")

# 路径基准钉 __file__（2026-08-28 规范）：src/agent → 上两级 = 项目根
_AGENT_DIR: str = str(Path(__file__).resolve().parent)
_ROOT: Path = Path(_AGENT_DIR).parents[1]


# ═══════════════════════════════════════════════════════
# 装 / 卸 / 看（练习 2：接线的三个动作）
# ═══════════════════════════════════════════════════════
def install_llm_cache(db_path: str | None = None) -> SQLiteLLMCache:
    """装上全局 LLM 缓存，返回装上去的实例（幂等：重复装只是换一个实例）。

    db_path=None → 用项目默认库 `.cache/llm_cache.db`（与 `cli.py cache` 同一份）。
    """
    cache: SQLiteLLMCache = SQLiteLLMCache(CACHE_PATH if db_path is None else db_path)
    set_llm_cache(cache)
    print(f"[cache] 已启用 → {cache.db_path}")
    return cache


def uninstall_llm_cache() -> None:
    """卸掉全局缓存（置 None）。

    为什么要它：全局缓存是**进程级可变状态**，装了不卸会跨用例泄漏
    （测试里"上一个用例的缓存"让下一个用例假通过）。用完即卸是纪律。
    """
    set_llm_cache(None)


def _display_path(path: str) -> str:
    """尽量显示相对项目根的路径；跨盘符时退回绝对路径。

    ⚠️ 实测坑：Windows 上 `os.path.relpath` **跨盘符直接抛 ValueError**
       （临时库在 C:、项目在 D:）—— 路径工具不是「总能用」，要留退路。
    """
    try:
        return os.path.relpath(path, str(_ROOT))
    except ValueError:
        return path


def cache_summary() -> str:
    """一行摘要：装了没有 + 入库条目数（CLI/子进程自检用，零 API）。"""
    current: BaseCache | None = get_llm_cache()
    if current is None:
        return "未启用（get_llm_cache() → None）"
    if isinstance(current, SQLiteLLMCache):
        return f"已启用（{_display_path(current.db_path)}，{current.count()} 条）"
    return f"已启用（{type(current).__name__} 非本项目实现）"


def cache_prefix(db_path: str | None = None) -> str:
    """执行器注入子进程用的代码前缀（**这正是"接线"的那一行**）。

    day34_orchestrator._run_cmd 对 llm 段执行：
        python -c "<cache_prefix()><原 cmd>"
    于是子进程在跑真模型之前先把缓存装上 → 同一 prompt 第二次不再出网。
    """
    arg: str = "" if db_path is None else repr(db_path)
    return f"import day41_cache_wiring as _cw; _cw.install_llm_cache({arg}); "


# ═══════════════════════════════════════════════════════
# 会计数的假模型（练习 2：证明"命中后真的不再进模型"）
# ═══════════════════════════════════════════════════════
class CountingChatModel(BaseChatModel):
    """零网络的假模型：只数 `_generate` 被调了几次。

    为什么不用 `MagicMock` 打桩：要验证的是**框架真的绕过了模型调用**，
    所以计数必须落在真正会被执行的那一层 —— `_generate`（模型自己），
    而不是"我们调过的某个中间函数"。

    ⚠️ 字段叫 `label` 不叫 `name`：`RunnableSerializable` 已有 `name: str | None`，
       覆盖成 `name: str` 是**不兼容重写**（pyright 直接报 incompatible override）。
    """

    label: str = "counting-model"
    reply: str = "固定回答"
    calls: int = 0

    @property
    def _llm_type(self) -> str:
        return "counting-fake"

    @property
    def _identifying_params(self) -> Mapping[str, Any]:
        """模型指纹：它会被拼进 llm_string → 改 label 必须视为"换问题"。

        不覆盖它的话，`_get_llm_string` 拿到的识别参数为空 → 两个"不同模型"
        算出同一个 llm_string → 缓存串味（Day 40 的二元组键就白设计了）。
        """
        return {"label": self.label}

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: CallbackManagerForLLMRun | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        self.calls += 1
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=self.reply))])


# ═══════════════════════════════════════════════════════
# 实验
# ═══════════════════════════════════════════════════════
def _temp_db(prefix: str) -> tuple[str, str]:
    """建一个临时目录 + 库路径，返回 (目录, 库路径)。测完必须删。"""
    tmp_dir: str = tempfile.mkdtemp(prefix=prefix)
    return tmp_dir, os.path.join(tmp_dir, "probe.db")


def exp1_install_contract() -> None:
    """实验1：装/卸契约（零 API）——装完是我们的实例；卸完是 None。"""
    print("=" * 72)
    print("exp1_install_contract：全局开关的装 / 卸")
    tmp_dir, db = _temp_db("day41_wire_")
    original: BaseCache | None = get_llm_cache()  # 先记原值，结束还原（别污染同进程）
    try:
        print(f"  装之前: {cache_summary()}（期望 None）")
        assert get_llm_cache() is None, "起点不该已经有缓存"

        cache: SQLiteLLMCache = install_llm_cache(db)
        assert get_llm_cache() is cache, "set_llm_cache 之后 get_llm_cache 必须就是它"
        assert isinstance(get_llm_cache(), BaseCache), "必须能被框架识别为 BaseCache"
        print(f"  装之后: {cache_summary()}")
        print("  ✅ 契约通过：全局开关指向我们的实例（框架层拦截点就位）")
    finally:
        set_llm_cache(original)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def exp2_cache_hits() -> None:
    """实验2：缓存真的拦住了模型调用（零 API）。

    三个断言对应三条合同：
      ① 同一 prompt 问两次 → `_generate` 只被调 1 次（第二次根本没进模型）
      ② 换模型指纹（label）问同一 prompt → 新模型自己进了一次（**绝不许命中**）
      ③ 库里正好 2 条（两个 llm_string 各一条）
    """
    print("=" * 72)
    print("exp2_cache_hits：命中 / 不串味 / 条目数")
    tmp_dir, db = _temp_db("day41_hit_")
    original: BaseCache | None = get_llm_cache()
    question: str = "给登录功能写 3 条测试用例"
    try:
        install_llm_cache(db)
        model_a = CountingChatModel(label="model-A")
        first: AIMessage = model_a.invoke(question)
        second: AIMessage = model_a.invoke(question)
        print(f"  [A] 第 1 次 invoke → _generate 调用数 {model_a.calls}（期望 1，未命中要出网）")
        print(f"  [A] 第 2 次 invoke → _generate 调用数 {model_a.calls}（期望仍是 1，命中缓存）")
        assert model_a.calls == 1, "同一 prompt 第二次不该再进模型"
        assert first.content == second.content, "命中时返回值必须与首次一致"
        assert isinstance(second.content, str), "content 类型要保持 str"

        model_b = CountingChatModel(label="model-B")
        _ = model_b.invoke(question)
        print(f"  [B] 换模型问同一句 → 新模型调用数 {model_b.calls}（期望 1：换了指纹就是换问题）")
        assert model_b.calls == 1, "不同模型指纹绝不该命中（二元组键的防串味作用）"

        cached = get_llm_cache()
        assert isinstance(cached, SQLiteLLMCache)
        print(f"  [C] {cache_summary()}（期望 2 条：model-A / model-B 各一条键）")
        assert cached.count() == 2, f"应恰好 2 条，实际 {cached.count()}"
        print("  ✅ 缓存接上了：命中省调用、换模型不串味、落盘条目对得上")
    finally:
        set_llm_cache(original)
        shutil.rmtree(tmp_dir, ignore_errors=True)


def exp3_subprocess_prefix() -> None:
    """实验3：子进程也能装上（零 API）——执行器接线的**前提验证**。

    执行器是 `subprocess.run([sys.executable, "-c", cmd])`：父进程 set 过的全局
    变量，子进程从零开始，看不见。所以本实验把 `cache_prefix()` 拼在一个
    真子进程的 `python -c` 前面，读出子进程自己看到的缓存状态。
    """
    print("=" * 72)
    print("exp3_subprocess_prefix：子进程注入（执行器接线的前提）")
    tmp_dir, db = _temp_db("day41_sub_")
    try:
        code: str = cache_prefix(db) + "print('[子进程]', _cw.cache_summary())"
        print(f"  注入的代码前缀: {cache_prefix(db)!r}")
        proc: subprocess.CompletedProcess[str] = subprocess.run(
            [sys.executable, "-c", code],
            cwd=_AGENT_DIR,          # 子进程在 src/agent 跑（与执行器同姿势）
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=180,
        )
        out: str = (proc.stdout or "").strip()
        print(f"  子进程输出: {out.replace(chr(10), ' | ')}")
        assert proc.returncode == 0, f"子进程失败 exit={proc.returncode}: {proc.stderr}"
        assert "已启用" in out, "子进程里没装上缓存 —— 执行器接线会白做"
        print("  ✅ 子进程内可装：执行器只要把这行前缀拼进 python -c 就接线完成")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def main() -> None:
    exp1_install_contract()
    exp2_cache_hits()
    exp3_subprocess_prefix()
    print("=" * 72)
    print("✅ day41_cache_wiring 三实验全过（全程零 API）")


if __name__ == "__main__":
    main()