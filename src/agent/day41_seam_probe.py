# FILE: day41_seam_probe.py
"""Day 41 练习 1：接缝探测 —— 把「跑起来才发现」提前成「静态可断言」。

母计划 Day 41 = 端到端功能测试 + Bug 修复 + 性能调优。
端到端今天要跑的是 **register（第二个场景）**：它的每个零件都被单测过，
但没有任何一个零件被验证过「和别的零件接在一起」。

零件之间那层东西叫**接缝**。接缝坏了不会在单测里报错，只会在端到端时
以三种面目出现，而且**全都是静默的**：
  · 静默覆盖：两个场景写同一个文件，后跑的盖掉先跑的（状态列还是绿的）
  · 静默错配：蓝图说 mock 在 8767、被测代码打 8766（404 也算「用例失败」）
  · 静默绕过：S5 声明「按本场景的 schema 造数」，cmd 却写死 users/orders

本练习**零 API、零外网**：只做契约比较与文本取证，把三类接缝变成可断言的
清单 —— 之后修一处、划掉一处。探测脚本刻意**不依赖今天新加的任何函数**，
这样它在「改之前 / 改之后」都能跑，同一份脚本给出可对比的两组数字。

实验↔步骤↔运行命令：
  exp1_output_collisions()  步骤2  python -c "from day41_seam_probe import exp1_output_collisions; exp1_output_collisions()"
  exp2_port_mismatch()      步骤2  python -c "from day41_seam_probe import exp2_port_mismatch; exp2_port_mismatch()"
  exp3_kind_blind_spot()    步骤2  python -c "from day41_seam_probe import exp3_kind_blind_spot; exp3_kind_blind_spot()"
  exp4_seam_report()        步骤2  python -c "from day41_seam_probe import exp4_seam_report; exp4_seam_report()"
  main()                    步骤2  python day41_seam_probe.py
"""
from __future__ import annotations

import json
import os
import re
import sys
from typing import Any
from urllib.parse import urlparse

from day34_flow_map import StageSpec
from day35_common import ROOT, output_dir, read_text, write_text
from day35_scenario import (
    SCENARIO_REGISTRY,
    ScenarioConfig,
    build_blueprint,
)

if sys.platform == "win32":
    _stdout: Any = sys.stdout
    _stdout.reconfigure(encoding="utf-8", errors="replace")

# 输入扩展名 → 走哪条解析路径（Day 29/30/32 的分界线）
MODEL_EXTS: frozenset[str] = frozenset({".md", ".txt", ".docx"})   # 文档 → 模型解析
CODE_EXTS: frozenset[str] = frozenset({".json"})                   # 机器可读 → 代码直读

# ⚠️ Day 42 修复：这里原来是 `(LOGIN_SCENARIO, REGISTER_SCENARIO)` —— **第二份写死的场景清单**。
# 加第三个场景时它不会报错，只会"看不见"：探测照旧输出 0/0/0，而那三个 0 的含义
# 已经从「三个场景都不冲突」**静默退化**成「我看的那两个不冲突」。
# Day 42 实测（负向 sanity）：把 refund 的 mock_port 故意改错，本文件**仍然报 0** ——
# 假绿实锤。改为从注册表派生后，新增场景自动进入探测范围。
SCENARIOS: tuple[ScenarioConfig, ...] = tuple(SCENARIO_REGISTRY.values())


def _ext(path_rel: str) -> str:
    return os.path.splitext(path_rel)[1].lower()


def _declared_base_url(doc_rel: str) -> str | None:
    """从接口文档里取服务地址（零 API）。

    .json → json.loads 取 base_url；.md/.txt → 正则扫 `http://host:port`
    （登录接口文档写的是「服务地址：http://127.0.0.1:8766」）。
    文档不在 → None（调用方按「没有可核对的东西」处理）。
    """
    path: str = os.path.join(ROOT, doc_rel)
    if not os.path.isfile(path):
        return None
    text: str = read_text(path)
    if _ext(doc_rel) == ".json":
        data: object = json.loads(text)
        if isinstance(data, dict):
            value: object = data.get("base_url")
            return value if isinstance(value, str) else None
        return None
    found = re.search(r"https?://[0-9A-Za-z._-]+:\d+", text)
    return found.group(0) if found is not None else None


def _port_of(url: str) -> int | None:
    return urlparse(url).port


# ═══════════════════════════════════════════════════════
# 探测一：产物互相覆盖（静默覆盖）
# ═══════════════════════════════════════════════════════
def exp1_output_collisions() -> list[str]:
    """任意两个场景的蓝图声明了同一个输出文件 → 后跑的覆盖先跑的（返回冲突清单）。"""
    print("=" * 72)
    print(f"exp1_output_collisions：{len(SCENARIOS)} 个场景的产物路径冲突（静默覆盖）")
    declarers: dict[str, list[str]] = {}
    for sc in SCENARIOS:
        for spec in build_blueprint(sc):
            for out in spec.outputs:
                declarers.setdefault(out, []).append(f"{sc.name}:{spec.stage_id}")
    collisions: list[str] = [
        f"{path}  ← " + " 与 ".join(who)
        for path, who in sorted(declarers.items())
        if len(who) > 1
    ]
    for line in collisions:
        print(f"  ❌ {line}")
    if not collisions:
        print(f"  ✅ 无冲突：{len(SCENARIOS)} 个场景的产物路径两两不相交（可以并存，谁也不覆盖谁）")
    print(f"  冲突数 = {len(collisions)}（期望修复后为 0）")
    return collisions


# ═══════════════════════════════════════════════════════
# 探测二：mock 端口与文档基地址不同源（静默错配）
# ═══════════════════════════════════════════════════════
def exp2_port_mismatch() -> list[str]:
    """蓝图 mock_port 与接口文档 base_url 的端口是否同源（返回错配清单）。

    为什么必须同源：S4 生成的 pytest 套件里 `BASE_URL` 抄的是**接口文档**里的
    地址；S6/S7 起的 mock 却监听蓝图里的 `mock_port`。两者不一致 → 用例打到
    没人的端口/别的服务的端口 → 一片 404，而「用例失败」在执行器看来是合法的
    结果（`pytest exit=1` 判为 run_ok）→ **绿着错**。
    """
    print("=" * 72)
    print("exp2_port_mismatch：mock_port 与接口文档 base_url 是否同源")
    problems: list[str] = []
    for sc in SCENARIOS:
        url: str | None = _declared_base_url(sc.api_doc)
        if url is None:
            print(f"  ⚠️ [{sc.name}] 读不到 {sc.api_doc} 的 base_url（跳过）")
            continue
        doc_port: int | None = _port_of(url)
        same: bool = doc_port == sc.mock_port
        flag: str = "✅" if same else "❌"
        print(f"  {flag} [{sc.name}] 文档 {url}（端口 {doc_port}） vs 蓝图 mock_port {sc.mock_port}")
        if not same:
            problems.append(
                f"{sc.name}：接口文档端口 {doc_port} ≠ 蓝图 mock_port {sc.mock_port}"
            )
    print(f"  错配数 = {len(problems)}（期望修复后为 0）")
    return problems


# ═══════════════════════════════════════════════════════
# 探测三：段的「性质」与该场景下的实际路径脱节（静默绕过）
# ═══════════════════════════════════════════════════════
def exp3_kind_blind_spot() -> list[str]:
    """按【该场景的输入扩展名】核对段的 kind 声明（返回脱节清单）。

    Day 34 定义 kind 三态时只有一个 login 场景，于是看着像「段固有属性」；
    第二个场景一上就暴露：**kind 其实是资产驱动的**——
      · 需求文档 .md/.txt → 走模型 → llm；同一段换成 .json（机器可读）→ 走代码
      · 声明 llm 但输入全是 .json → 盘点成 needs_api，白等一个 --with-llm
      · 声明 code 但输入含文档 → 执行器「自动跑」时**静默调模型**（更危险）
    只看「外部输入」（蓝图内别的段会产出的文件不算），与 day34 盘点的口径一致。
    """
    print("=" * 72)
    print("exp3_kind_blind_spot：段性质 vs 输入实际路径")
    problems: list[str] = []
    for sc in SCENARIOS:
        blueprint: list[StageSpec] = build_blueprint(sc)
        produced: frozenset[str] = frozenset(p for s in blueprint for p in s.outputs)
        print(f"  ── 场景 [{sc.name}] ──")
        for spec in blueprint:
            if spec.kind == "manual":
                continue
            external: list[str] = [p for p in spec.inputs if p not in produced]
            exts: set[str] = {_ext(p) for p in external}
            if not exts:
                continue  # 输入全是流内产物：性质由上游决定，这里不判
            model_only: bool = all(e in MODEL_EXTS for e in exts)
            code_only: bool = all(e in CODE_EXTS for e in exts)
            ext_text: str = ", ".join(sorted(exts))
            if spec.kind == "llm" and code_only:
                msg = (
                    f"[{sc.name}] {spec.stage_id}：kind=llm 但输入全是机器可读文件"
                    f"（{ext_text}）→ 实际走代码，白等 --with-llm"
                )
                print(f"    ❌ {msg}")
                problems.append(msg)
            elif spec.kind == "code" and model_only:
                msg = (
                    f"[{sc.name}] {spec.stage_id}：kind=code 但输入含文档"
                    f"（{ext_text}）→ 会被「自动跑」静默调模型"
                )
                print(f"    ❌ {msg}")
                problems.append(msg)
            else:
                print(f"    ✅ {spec.stage_id}：kind={spec.kind}，外部输入 {sorted(exts)}")
    print(f"  脱节数 = {len(problems)}（期望修复后为 0）")
    return problems


# ═══════════════════════════════════════════════════════
# 落盘：接缝报告（= 今日修复清单）
# ═══════════════════════════════════════════════════════
def exp4_seam_report(out_dir: str | None = None) -> str:
    """三项探测汇总 → `outputs/flow/seam_report.md`（= 修复清单），返回绝对路径。"""
    print("=" * 72)
    print("exp4_seam_report：汇总接缝报告")
    collisions: list[str] = exp1_output_collisions()
    ports: list[str] = exp2_port_mismatch()
    kinds: list[str] = exp3_kind_blind_spot()
    target_dir: str = output_dir("flow") if out_dir is None else out_dir
    os.makedirs(target_dir, exist_ok=True)
    lines: list[str] = [
        "# Day 41 接缝报告（端到端跑通 register 的前置作业）",
        "",
        "> 由 `day41_seam_probe.py` 自动生成（零 API）：三项探测全部是**静态可断言**的，",
        "> 不必先跑一次端到端就能知道哪里会坏。",
        "",
        f"**本次覆盖场景（{len(SCENARIOS)} 个）**：" + "、".join(sc.name for sc in SCENARIOS),
        "",
        "> Day 42 补：这一行是从**注册表**派生的。加它之前的版本不打印场景清单，",
        "> 于是「加第三个场景」只会让探测**少看一个**，报告照旧写着「三项全部归零」",
        "> —— 那正是最难查的一类绿：**绿得没错，只是少看**。",
        "",
        f"## 一、产物路径冲突（{len(collisions)} 处）",
        "",
        f"{len(SCENARIOS)} 个场景里任意两个声明同一个输出文件 → 后跑的静默覆盖先跑的。",
        "",
    ]
    lines += ([f"- ❌ {c}" for c in collisions] or ["- ✅ 无"])
    lines += [
        "",
        f"## 二、mock 端口与接口文档不同源（{len(ports)} 处）",
        "",
        "生成的套件打文档里的地址，mock 却监听蓝图里的端口 → 一片 404 却仍判 run_ok。",
        "",
    ]
    lines += ([f"- ❌ {p}" for p in ports] or ["- ✅ 无"])
    lines += [
        "",
        f"## 三、段性质与输入路径脱节（{len(kinds)} 处）",
        "",
        "kind 是「这一段的输入走模型还是走代码」的声明，随场景资产而变，不是段固有属性。",
        "",
    ]
    lines += ([f"- ❌ {k}" for k in kinds] or ["- ✅ 无"])
    lines += [
        "",
        "## 修复去向",
        "",
        "| 探测 | 修在哪 |",
        "|------|--------|",
        "| 一 · 产物冲突 | 步骤 4.1 蓝图工厂加场景命名空间 |",
        "| 二 · 端口不同源 | 步骤 4.6 改接口文档 + 步骤 4.1 加同源契约校验 |",
        "| 三 · kind 脱节 | 步骤 4.1 按资产扩展名派生 kind |",
        "",
        "> 修完重跑本脚本：三项应全部归零 —— 那就是「可以开跑了」的判据。",
    ]
    report_path: str = os.path.join(target_dir, "seam_report.md")
    write_text(report_path, "\n".join(lines))
    print(f"  ✅ 接缝报告落盘: {report_path}")
    return report_path


def main() -> None:
    exp4_seam_report()
    print("=" * 72)
    print("✅ day41_seam_probe 完成（零 API）：三项探测 = 今日修复清单")


if __name__ == "__main__":
    main()