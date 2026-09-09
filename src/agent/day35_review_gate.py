"""Day 35 练习 4：两段式评审门 —— 模型产物先审后入库（入库对象 = 评审对象）。

故事（为什么做）：
  Day 31 的 upsert_bug_analyses(reviewed=False) 只是【软提示】——打印一行警告照样入库；
  Day 34 蓝图 S2 是【占位】——manual 段永远等人。今天把两者收口成"硬门禁 + 可执行人审工具"，
  让 S2 从占位变成真的能走的闸门（蓝图 S2 的输入 = 本工具消费的评审对象）。

原则三连：
  1. 入库对象 = 评审对象：模型落盘 JSON 原样包进 ReviewEnvelope，payload 只读不改（不可变）
  2. 评审门硬阻断：reviewed=False 的 envelope 调 upsert_from_envelope → ReviewGateError（raise，不是打印）
  3. 审计可追溯：reviewed_by / reviewed_at / created_at 全程留痕（谁、何时、审了哪个版本）

两段式（Day 35 名字由来）：
  段一 exp1_generate_seed —— 模型产物"种子化"落盘（reviewed=False，等人工审阅）
  人工环节（不入代码）：打开 envelope JSON，审阅 payload 是否符合预期（可改字段 = 要重新生成？见坑 2）
  段二 exp2_approve_seed —— 人审通过后盖章（reviewed=True + reviewed_by + reviewed_at）
  入库 exp3/exp4 —— 硬门禁放行后 upsert（dry_run=True 预演 / False 真入库，真入库走 Day 31 链路）

实验↔步骤↔运行命令 映射：
  exp1_generate_seed()      步骤5  python -c "from day35_review_gate import exp1_generate_seed; exp1_generate_seed()"
  exp2_approve_seed()       步骤5  python -c "from day35_review_gate import exp2_approve_seed; exp2_approve_seed()"
  exp3_gate_block()         步骤5  python -c "from day35_review_gate import exp3_gate_block; exp3_gate_block()"
  exp4_approve_and_preview()步骤5  python -c "from day35_review_gate import exp4_approve_and_preview; exp4_approve_and_preview()"
  main()                    步骤5  python day35_review_gate.py（完成态：生成→演示门禁→盖章→dry-run 预演）
  真入库（真 API）                 python -c "from day35_review_gate import upsert_from_envelope; print(upsert_from_envelope('outputs/gate/bug_login_analysis_pending.json', dry_run=False))"
"""
from __future__ import annotations

import json
import os
import sys

from datetime import datetime
from typing import Literal

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from pydantic import BaseModel, Field, ValidationError

from day31_bug_analyzer import BugAnalysis, upsert_bug_analyses  # noqa: E402
from day35_common import ROOT, read_text, write_text, output_dir  # noqa: E402  # 复用抽好的公共底座



class ReviewGateError(RuntimeError):
    """评审门硬阻断异常：reviewed=False 的一切入库企图都被它拦下。"""

class ReviewEnvelope(BaseModel):
    """评审信封：模型产物（payload）+ 评审元数据（谁/何时/审没审）。

    ⚠️ reviewed_at 用 ISO 文本（str）而非 datetime 字段——见 day35_pyright_pitfalls 坑 1：
       datetime 字段 model_dump() 后 json.dumps 直接 TypeError。
    """

    kind: Literal["bug"] = "bug"                  # 评审对象类型（文档给出 requirement 扩展点）
    source: str                                   # 溯源：产生这份产物的原始输入（如 docs/bugs/login_bugs.md）
    payload: dict[str, object]                    # 模型产物 JSON 原样（评审对象本体，不可变）
    reviewed: bool = False
    reviewed_by: str | None = None
    reviewed_at: str | None = None
    created_at: str = Field(
        default_factory=lambda: datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )


# ═══════════════════════════════════════════════════════
# 评审门核心（工具函数：生成 / 盖章 / 硬门禁入库）
# ═══════════════════════════════════════════════════════
def _abs(rel: str) -> str:
    """相对项目根 → 绝对路径（钉 __file__，锚来自 day35_common.ROOT）。"""
    return os.path.join(ROOT, rel)


def load_envelope(rel: str) -> ReviewEnvelope:
    """读回评审信封并做 Schema 校验（json.loads 是 Any → isinstance 收窄 + model_validate）。"""
    data: object = json.loads(read_text(_abs(rel)))
    if not isinstance(data, dict):
        raise ReviewGateError(f"envelope 必须是 JSON 对象，实际 {type(data).__name__}: {rel}")
    return ReviewEnvelope.model_validate(data)


def generate_seed(payload_rel: str, source: str) -> str:
    """段一：把模型产物包成待评审种子落盘（reviewed=False）。返回 envelope 相对路径。

    只落盘不入库（两段式第一段）；payload 原样进信封——评审对象 = 模型当时产出的那份。
    """
    payload: object = json.loads(read_text(_abs(payload_rel)))
    if not isinstance(payload, dict):
        raise ReviewGateError(f"评审对象必须是 JSON 对象（单条分析），实际 {type(payload).__name__}")
    output_dir("gate")  # write_text 不建父目录 → 先确保 outputs/gate 在位
    stem: str = os.path.splitext(os.path.basename(payload_rel))[0]
    rel: str = os.path.join("outputs", "gate", f"{stem}_pending.json")
    env = ReviewEnvelope(kind="bug", source=source, payload=payload)
    write_text(_abs(rel), json.dumps(env.model_dump(), ensure_ascii=False, indent=2))
    return rel


def approve_seed(rel: str, reviewer: str) -> ReviewEnvelope:
    """段二：人工审阅通过后盖章（reviewed=True + reviewed_by/reviewed_at），写回信封。

    幂等：已盖章再调只提示不覆盖 reviewer。
    """
    env: ReviewEnvelope = load_envelope(rel)
    if env.reviewed:
        print(f"  ⚠️ 已是 reviewed=True（{env.reviewed_by} @ {env.reviewed_at}），跳过重复盖章")
        return env
    env.reviewed = True
    env.reviewed_by = reviewer
    env.reviewed_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    write_text(_abs(rel), json.dumps(env.model_dump(), ensure_ascii=False, indent=2))
    return env


def upsert_from_envelope(rel: str, *, dry_run: bool = True) -> int:
    """硬门禁入库：reviewed=False 一律 raise；盖章后按 kind 分派入库。

    dry_run=True（默认，CI 预演）：只模拟不真写库，返回将入库条数；
    dry_run=False（真入库）：走 Day 31 upsert_bug_analyses（真 Embedding API，需 .env key）。
    教学点：门禁检查在【构造入库链路之前】——raise 路径零 API，可随时冒烟。
    """
    env: ReviewEnvelope = load_envelope(rel)
    if not env.reviewed:
        raise ReviewGateError(
            f"评审门硬阻断：{rel} 的 reviewed=False——模型产物未经人工评审不得入库"
            f"（先跑 exp2_approve_seed 盖章；审计: created_at={env.created_at}）"
        )
    if env.kind == "bug":
        try:
            analysis: BugAnalysis = BugAnalysis.model_validate(env.payload)
        except ValidationError as exc:
            raise ReviewGateError(
                f"payload 不符合 BugAnalysis Schema：{str(exc.errors()[:2])}"
            ) from exc
        if dry_run:
            print(f"  ▶ dry-run 预演：将入库 1 条（source={env.source}，reviewed_by={env.reviewed_by}）")
            return 1
        count: int = upsert_bug_analyses([analysis], source=env.source, reviewed=True)
        return count
    raise ReviewGateError(f"暂不支持的评审对象类型: {env.kind}")

# ═══════════════════════════════════════════════════════
# 实验（练习 4：按"人审前/后"的顺序演示）
# ═══════════════════════════════════════════════════════
def exp1_generate_seed(
    payload_rel: str = "outputs/bug_login_analysis.json",
    source: str = "docs/bugs/login_bugs.md",
) -> str:
    """生成待评审种子（两段式段一）。默认对象：S9 现成产物 bug_login_analysis.json。"""
    print("=" * 66)
    print(f"exp1_generate_seed：{payload_rel} → 评审信封（reviewed=False，落盘止，不入库）")
    rel: str = generate_seed(payload_rel, source)
    env: ReviewEnvelope = load_envelope(rel)
    print(f"  ✅ 种子落盘: {_abs(rel)}")
    print(f"     kind={env.kind} source={env.source} reviewed={env.reviewed} created_at={env.created_at}")
    print(f"     payload 键: {sorted(env.payload.keys())}（bug_id={env.payload.get('bug_id')!r}）")
    print("  → 人工环节：打开上面的 JSON，审阅 payload 各字段是否符合预期")
    return rel


def exp2_approve_seed(rel: str, reviewer: str = "zhangsan") -> ReviewEnvelope:
    """人工审阅通过 → 盖章写回（两段式段二）。"""
    env: ReviewEnvelope = approve_seed(rel, reviewer)
    print(f"exp2_approve_seed：盖章完成 reviewed={env.reviewed} "
          f"reviewed_by={env.reviewed_by} reviewed_at={env.reviewed_at}")
    return env


def exp3_gate_block(rel: str) -> str:
    """门禁演示：不盖章直接 upsert → 必须被 ReviewGateError 拦下（硬阻断不是打印）。"""
    print("exp3_gate_block：未评审信封直接入库 → 应被硬门禁拦下")
    try:
        upsert_from_envelope(rel, dry_run=True)
    except ReviewGateError as exc:
        print(f"  ✅ 门禁生效: ReviewGateError: {str(exc)[:80]}...")
        return "gate_raised"
    raise AssertionError("❌ 门禁未生效：reviewed=False 居然放行了")


def exp4_approve_and_preview(rel: str, reviewer: str = "zhangsan") -> int:
    """盖章后 dry-run 预演入库（不真写库）；真入库命令见模块 docstring。"""
    print("exp4_approve_and_preview：盖章后 dry-run 预演入库")
    approve_seed(rel, reviewer)
    count: int = upsert_from_envelope(rel, dry_run=True)
    print(f"  ✅ dry-run 将入库 {count} 条（source 同源幂等，重复跑不产生重复文档）")
    print("  → 真入库（真 API）：python -c \"from day35_review_gate import upsert_from_envelope; "
          "print(upsert_from_envelope('outputs/gate/bug_login_analysis_pending.json', dry_run=False))\"")
    return count


if __name__ == "__main__":
    """完成态：生成种子 → 演示硬门禁 → 盖章 → dry-run 预演（全程零 API）。"""
    env_rel: str = exp1_generate_seed()
    exp3_gate_block(env_rel)          # 先证明"没盖章进不去"
    exp4_approve_and_preview(env_rel)  # 再盖章放行（dry-run）
    print("=" * 66)
    print("💡 要点回顾：")
    print("   入库对象 = 评审对象：payload 原样进信封，不可变；改内容 = 重新生成种子")
    print("   评审门硬阻断：raise 而非打印 —— 门禁检查在构造入库链路之前（零 API 可测）")
    print("   审计可追溯：created_at/reviewed_by/reviewed_at 三枚时间戳+责任人全程留痕")
    print("   蓝图 S2 收口：S1 产物先过评审门再进知识库（doc_type=bug；requirement 扩展见文档）")