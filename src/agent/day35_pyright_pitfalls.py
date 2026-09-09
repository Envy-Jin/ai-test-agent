"""Day 35 练习 5：Pyright 避坑 6 连 —— 本日脚本（common/scenario/review_gate）设计现场的真实坑。

实验↔步骤↔运行命令 映射：
  exp1_datetime_json()   步骤6  python -c "from day35_pyright_pitfalls import exp1_datetime_json; exp1_datetime_json()"
  exp2_dump_sharing()    步骤6  python -c "from day35_pyright_pitfalls import exp2_dump_sharing; exp2_dump_sharing()"
  exp3_dict_object()     步骤6  python -c "from day35_pyright_pitfalls import exp3_dict_object; exp3_dict_object()"
  exp4_any_leak()        步骤6  python -c "from day35_pyright_pitfalls import exp4_any_leak; exp4_any_leak()"
  exp5_env_optional()    步骤6  python -c "from day35_pyright_pitfalls import exp5_env_optional; exp5_env_optional()"
  exp6_validation()      步骤6  python -c "from day35_pyright_pitfalls import exp6_validation; exp6_validation()"
  main()                 步骤6  python day35_pyright_pitfalls.py（完成态：6 坑依次演示）
"""
from __future__ import annotations

import json
import os
import sys

from datetime import datetime, timezone
from typing import Literal

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from pydantic import BaseModel, Field, ValidationError


# ═══════════════════════════════════════════════════════
# 坑 1：datetime 字段 vs JSON 序列化（day35_review_gate 设计现场）
# ═══════════════════════════════════════════════════════
class EnvelopeNaive(BaseModel):
    """❌ 反面教材：reviewed_at 用 datetime 字段。"""

    reviewed: bool = False
    reviewed_at: datetime | None = None


def exp1_datetime_json() -> None:
    """datetime 字段 model_dump() 后 json.dumps → TypeError（pyright 不报，运行期炸）。"""
    print("── 坑 1：datetime 字段进 JSON 必炸，gate 因此把 reviewed_at 存成 ISO 文本 ──")
    naive = EnvelopeNaive(reviewed=True, reviewed_at=datetime.now(timezone.utc))
    dumped = naive.model_dump()
    try:
        json.dumps(dumped)  # ❌ TypeError: Object of type datetime is not JSON serializable
    except TypeError as exc:
        print(f"  ❌ json.dumps(model_dump()) → TypeError: {exc}")
    # ✅ 解法 A：字段直接存 ISO 文本（day35_review_gate 的做法，model_dump 后可直序列化）
    iso: str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    safe = {"reviewed": True, "reviewed_at": iso}
    print(f"  ✅ 字段存 ISO 文本（gate 做法）→ json.dumps 通过: {json.dumps(safe)}")
    # ✅ 解法 B：若坚持 datetime 字段，落盘用 model_dump(mode='json') 自动转 ISO
    print(f"  ✅ 解法 B：model_dump(mode='json') → {json.dumps(naive.model_dump(mode='json'))}")


# ═══════════════════════════════════════════════════════
# 坑 2：model_copy() 浅拷贝（评审信封 payload 的不可变设计；v2 实测见函数 docstring）
# ═══════════════════════════════════════════════════════
class EnvelopeDemo(BaseModel):
    payload: dict[str, object]


def exp2_dump_sharing() -> None:
    """model_copy() 浅拷贝：嵌套容器与原模型共享——改"副本"的嵌套 = 改原模型本体。

    ⚠️ pydantic v2 实测（2026-09-07）：model_dump() 恰好做深拷贝输出，不共享；
       真正共享的是 model_copy(deep=False)（默认浅拷贝）。评审信封的不可变防线
       靠「只改 reviewed 元数据、不改 payload」约定 + 确需复制时显式 deep=True。
    """
    print("── 坑 2：model_copy() 浅拷贝 —— 副本的嵌套 dict 与原模型共享 ──")
    env = EnvelopeDemo(payload={"bug_id": "BUG-L01"})
    clone = env.model_copy()  # deep=False（默认）→ 嵌套容器共享
    shared: bool = clone.payload is env.payload
    print(f"  ❌ clone.payload is env.payload → {shared}（共享引用，浅拷贝只复制了外壳）")
    if shared:
        clone.payload["bug_id"] = "被污染"  # dict[str, Any]，pyright 不拦——正是坑
    print(f"     env.payload 现在 = {env.payload}（❌ 改副本的嵌套 = 改了原模型）")
    deep = env.model_copy(deep=True)
    print(f"  ✅ model_copy(deep=True) 后 is 同一引用 → {deep.payload is env.payload}（真独立）")


# ═══════════════════════════════════════════════════════
# 坑 3：dict[str, object] 值类型 invariant（payload 收窄）
# ═══════════════════════════════════════════════════════
def exp3_dict_object() -> None:
    """dict[str, object] 取出的值是 object——直接当 str 用，pyright 立刻报红。"""
    print("── 坑 3：dict[str, object] 取值是 object —— 必须收窄或交给 pydantic ──")
    payload: dict[str, object] = {"bug_id": "BUG-L01", "severity": "一般"}
    # ❌ title: str = payload["bug_id"] 之后 title.startswith(...) → object has no attribute
    # ✅ 解法 A：isinstance 收窄
    raw: object = payload.get("bug_id")
    if isinstance(raw, str):
        print(f"  ✅ isinstance 收窄后可用 str 方法: {raw.startswith('BUG')}")
    # ✅ 解法 B：把整个 dict 交给 pydantic model_validate（类型边界在 Schema，不在手拆字段）
    analysis = BugDemo.model_validate(payload)
    print(f"  ✅ model_validate 收窄（gate 做法）: {analysis.bug_id} / {analysis.severity}")


class BugDemo(BaseModel):
    bug_id: str
    severity: str = "一般"


# ═══════════════════════════════════════════════════════
# 坑 4：json.loads 的 Any 传染（load_envelope 的 isinstance 守卫）
# ═══════════════════════════════════════════════════════
def exp4_any_leak() -> None:
    """json.loads 返回 Any：不设类型边界时拼错键不报错（Any 传染到整个下游）。"""
    print("── 坑 4：json.loads 是 Any —— 显式收窄 = 给下游立类型边界 ──")
    text: str = '{"bug_id": "BUG-L01"}'
    # ❌ data = json.loads(text); data["bug_idd"]  → Any 不报错，运行期 KeyError 才暴露
    # ✅ 显式边界：object → isinstance(dict) 收窄成 dict[str, object]
    obj: object = json.loads(text)
    if not isinstance(obj, dict):
        raise TypeError(f"必须是 JSON 对象，实际 {type(obj).__name__}")
    payload: dict[str, object] = obj
    # 收窄后 dict.get 返回 object|None；值类型仍是 object → 交给下游时仍需收窄/Schema
    value: object | None = payload.get("bug_idd")  # 拼错键：pyright 不拦（键是 str），值是 None
    print(f"  ✅ 收窄后 payload = {payload}；拼错键 bug_idd → get 返回 {value!r}（运行期才暴露）")


# ═══════════════════════════════════════════════════════
# 坑 5：os.environ.get 的 str | None（评审人参数默认值）
# ═══════════════════════════════════════════════════════
def exp5_env_optional() -> None:
    """os.environ.get 返回 str | None：直接用会报 None 窄化错；or 默认值收窄。"""
    print("── 坑 5：os.environ.get → str | None —— or 默认值收窄 ──")
    reviewer: str = os.environ.get("GATE_REVIEWER") or "zhangsan"
    # ❌ reviewer_raw = os.environ.get("GATE_REVIEWER")  类型 str | None
    #    reviewer_raw.upper() → pyright: "upper" is not a known attribute of "None"
    raw: str | None = os.environ.get("GATE_REVIEWER")
    if raw is not None:
        print(f"  ✅ 显式 is not None 收窄分支: env 里有值 {raw!r}")
    else:
        print(f"  ✅ 环境变量没设 → or 默认值兜底: {reviewer!r}")


# ═══════════════════════════════════════════════════════
# 坑 6：model_validate 校验失败要异常链（upsert_from_envelope 的 payload 校验）
# ═══════════════════════════════════════════════════════
class ReviewError(RuntimeError):
    pass


def exp6_validation() -> None:
    """坏 payload 交给 model_validate → ValidationError：用 raise ... from exc 异常链保留根因。"""
    print("── 坑 6：ValidationError 要异常链上抛（from exc），别吞掉根因 ──")
    bad_missing: dict[str, object] = {"severity": "一般"}  # 缺 bug_id → 非法
    try:
        BugDemo.model_validate(bad_missing)
    except ValidationError as exc:
        first: str = str(exc.errors()[0]) if exc.errors() else "unknown"
        try:
            # ✅ 异常链：ReviewError.__cause__ 指向 ValidationError，根因不丢
            raise ReviewError(f"payload 不符合 Schema: {first[:110]}") from exc
        except ReviewError as chained:
            cause_ok: bool = isinstance(chained.__cause__, ValidationError)
            print(f"  ❌ 校验失败: {first[:110]}...")
            print(f"  ✅ 异常链成立: chained.__cause__ is ValidationError → {cause_ok}（根因可追溯）")
    ok: BugDemo = BugDemo.model_validate({"bug_id": "BUG-L01", "severity": "一般"})
    print(f"  ✅ 合法 payload 校验通过: {ok.bug_id} / {ok.severity}")


if __name__ == "__main__":
    """完成态：6 坑依次演示（exp6 内部捕获并构造异常链演示，不会中断）。"""
    exp1_datetime_json()
    exp2_dump_sharing()
    exp3_dict_object()
    exp4_any_leak()
    exp5_env_optional()
    exp6_validation()
    print("=" * 66)
    print("✅ 6 坑演示完成（pyright 0 errors 目标：坑 3/4/5 的 ✅ 写法即本日脚本采用写法）")
