"""
Day 31 练习 4：知识库淘汰通道 —— 已修复 Bug 归档

背景（Day 26 答疑遗留）：知识库只有"写入端"（Day 29 reviewed 门禁），没有"淘汰端"——
Agent 检索 Bug 知识时可能把"已修复的历史缺陷"当作"当前缺陷"重复上报。
今天补上：已修复 Bug → 归档副本落盘 + Chroma 按 source+bug_id 删除 → kb_search 不再返回。

设计（步骤 1 决策 D）：
  archive_fixed_bugs(source, analyses, archive_dir)：
    ① 对 status == "已修复" 的 Bug → 渲染归档副本（带"已修复"标注）→ 落盘 outputs/bug_archive/
    ② Chroma 原生 where 多条件过滤（{"$and": [{"source": s}, {"bug_id": id}]}，2026-08-30 联网确认）
       → get 到该 Bug 文档 id → delete（按 Bug 粒度移除，不受 Day 24 source 级 upsert 限制）
    ③ kb_search 验证：归档前能搜到 → 归档后不再返回（淘汰通道生效）

用法：
  python -c "from day31_bug_archive import exp_archive_demo; exp_archive_demo()"  # 真实 API
"""

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()  # ⚠️ 必须在 langchain import 之前

from langchain_chroma import Chroma

from day21_kb_persist import KnowledgeIndexerV2
from day24_case_agent import _get_indexer
from day31_bug_analyzer import (
    BugAnalysis,
    render_bug_markdown,
    validate_bug_analysis,
)


# ═══════════════════════════════════════════════════════
# 底层访问：知识库同一个 Chroma 实例
# ═══════════════════════════════════════════════════════

def _get_vectorstore() -> Chroma:
    """拿知识库底层 Chroma（淘汰操作需要原生 get/delete）。

    ⚠️ _vectorstore 是 KnowledgeIndexerV2 的私有属性，项目先例
       （day21_kb_persist.py:121/203）用 # type: ignore[attr-defined] 访问（练习 5 坑 4）。
    """
    indexer: KnowledgeIndexerV2 = _get_indexer()
    vs = indexer._vectorstore  # type: ignore[attr-defined]
    if vs is None:
        raise RuntimeError("知识库尚未建索引（先跑 exp4_batch_pipeline 入库或 Day 24 exp1）")
    return vs


def find_bug_doc_ids(vs: Chroma, source: str, bug_id: str) -> list[str]:
    """按 source + bug_id 精确定位单个 Bug 文档 id（Chroma where $and 多条件过滤）。

    ⚠️ vs.get(where=...) 返回 dict[str, object] → ids 需 isinstance 收窄为 list[str]（练习 5 坑 3）。
    """
    rows: dict[str, object] = vs.get(
        where={"$and": [{"source": source}, {"bug_id": bug_id}]}  # 2026-08-30 联网确认的语法
    )
    ids_obj: object = rows.get("ids", [])
    ids: list[str] = ids_obj if isinstance(ids_obj, list) else []
    return [i for i in ids if isinstance(i, str)]


# ═══════════════════════════════════════════════════════
# 淘汰通道：已修复 Bug 归档
# ═══════════════════════════════════════════════════════

def archive_fixed_bugs(source: str, analyses: list[BugAnalysis], archive_dir: str | None = None) -> int:
    """已修复 Bug 归档（淘汰通道）：归档副本落盘 + 从活跃库移除。

    返回归档的 Bug 数量。
    """
    fixed: list[BugAnalysis] = [a for a in analyses if a.status == "已修复"]
    if not fixed:
        print("  ℹ️ 本批次没有已修复的 Bug，无需归档")
        return 0
    out_dir: str = archive_dir or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "..", "..", "outputs", "bug_archive"
    )
    os.makedirs(out_dir, exist_ok=True)
    vs: Chroma = _get_vectorstore()
    archived: int = 0
    for a in fixed:
        # ① 归档副本落盘（归档 = 可追溯：教训留给历史）
        archive_path: str = os.path.join(out_dir, f"{os.path.splitext(source)[0]}_{a.bug_id}.md")
        report = validate_bug_analysis(a)
        with open(archive_path, "w", encoding="utf-8") as f:
            f.write(f"> 已归档（{a.status}）——不再作为活跃缺陷检索\n\n" + render_bug_markdown(a, report))
        # ② 从活跃库移除（淘汰 = 还给检索：历史缺陷不是现状）
        ids: list[str] = find_bug_doc_ids(vs, source, a.bug_id)
        if ids:
            vs.delete(ids=ids)
            print(f"  ✅ {a.bug_id} 已归档并移除（删 {len(ids)} 条）：{archive_path}")
        else:
            print(f"  ⚠️ {a.bug_id} 归档副本已落盘，但知识库中未找到该文档（先入库再归档）")
        archived += 1
    return archived


# ═══════════════════════════════════════════════════════
# 实验
# ═══════════════════════════════════════════════════════

def exp_archive_demo(source: str = "login_bugs.md", question: str = "登录 token 未写入") -> None:
    """演示淘汰通道：归档前 kb_search 能搜到 → 归档后不再返回（真实 API）。

    前置：先跑 exp4_batch_pipeline('../../docs/bugs/login_bugs.md', name='login', reviewed=True)
    入库（含 BUG-L02 已修复），再跑本实验。
    """
    print("=" * 60)
    print(f"实验：exp_archive_demo —— 已修复 Bug 淘汰通道（source={source}）")
    indexer: KnowledgeIndexerV2 = _get_indexer()
    # ① 归档前检索（应能搜到 BUG-L02）
    before: list = indexer.search_by_type(question, "bug", k=3)
    hit_before: bool = any(str(d.metadata.get("bug_id", "")) == "BUG-L02" for d in before)
    print(f"  🔍 归档前检索 '{question}': {len(before)} 条，含 BUG-L02={hit_before}")
    if not hit_before:
        print("  ⚠️ 未搜到 BUG-L02——确认先跑过 exp4_batch_pipeline 入库")
    # ② 构造分析列表（练习 3 的真实分析产物，这里演示用手工构造的"已修复"样本）
    fixed_analyses: list[BugAnalysis] = [
        BugAnalysis(
            bug_id="BUG-L02",
            title="登录成功后 token 未写入本地存储",
            bug_summary="登录成功但 localStorage 未写 token，刷新掉登录态",
            bug_type="功能缺陷",
            severity="严重",
            root_cause_analysis="token 写入逻辑挂在页面刷新回调而非登录成功回调",
            reproduce_steps=["正常登录", "检查 localStorage"],
            test_cases_to_add=[],
            regression_scope=["登录流程", "会话保持"],
            prevention="登录成功路径统一由 auth 模块回调写入 token",
            status="已修复",
        ),
    ]
    archived: int = archive_fixed_bugs(source, fixed_analyses)
    # ③ 归档后检索（应不再返回 BUG-L02）
    after: list = indexer.search_by_type(question, "bug", k=3)
    hit_after: bool = any(str(d.metadata.get("bug_id", "")) == "BUG-L02" for d in after)
    print(f"  🔍 归档后检索 '{question}': {len(after)} 条，含 BUG-L02={hit_after}")
    print(f"  ✅ 归档 {archived} 个已修复 Bug；淘汰通道生效={hit_before and not hit_after}")



if __name__ == "__main__":
    """一键演示：已修复 Bug 淘汰通道（真实 API）。"""
    exp_archive_demo()