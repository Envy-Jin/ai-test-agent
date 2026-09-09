"""Day 35 练习 1：公共工具抽取 —— rule of three 收口（重复 → 一处实现 + 等价性回归）。

背景（为什么抽——三次重复触发 rule of three）：
  Day 31/32 的 4 个脚本里躺着同一批"路径/IO 小工具"，各写各的：
    day31_bug_analyzer._read_text      —— 读 utf-8 文本（第 369 行）
    day32_data_schema._read_text       —— 同上，逐字重复
    day32_run_pipeline._read_text      —— 同上，第三份
    day32_data_schema._schema_path     —— 定位 docs/schemas/<name>
    day32_run_pipeline._schema_path    —— 同上，第二份
    day32_data_generator._out_dir      —— 定位 outputs/data_gen 并建目录
  抽取触发规则：一次内联 / 二次考虑 / 三次抽取（2026-09-02 讨论结论）。

本脚本 = 抽取后的"公共实现"教学载体：
  1. 公共函数必须是无框架依赖的【叶子模块】——业务脚本 import 它不背 langchain/chroma；
  2. 路径一律以项目根为锚（钉 __file__，2026-08-28 规范）；
  3. 物理并入 src/agent/utils.py + 改造 day31/day32 旧脚本为薄包装，留到 Day 36
     项目架构重构一起做（今天先证明"抽取后行为不变"，不打断历史脚本）。
  练习实验 exp1 做等价性回归：旧实现（逐字复刻）vs 新公共实现，同一输入断言输出一致。

实验↔步骤↔运行命令 映射：
  exp1_equivalence()   步骤2  python -c "from day35_common import exp1_equivalence; exp1_equivalence()"
  main()               步骤2  python day35_common.py（完成态：等价回归 + 结论提示）
"""
from __future__ import annotations

import os
import sys
import tempfile

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

# ── 路径基准钉 __file__（2026-08-28 规范）──
# 注意：公共函数用【本模块】的 __file__ 推导项目根。运行时 day35_common.py 与业务脚本
# 同目录（src/agent/）→ 根一致；冒烟测试同构（平铺同目录），故推导始终可靠。
_AGENT_DIR: str = os.path.dirname(os.path.abspath(__file__))
ROOT: str = os.path.dirname(os.path.dirname(_AGENT_DIR))  # src/agent → 项目根


# ═══════════════════════════════════════════════════════
# 公共实现（抽取产物 —— 收敛 Day 31/32 的重复小工具）
# ═══════════════════════════════════════════════════════
def read_text(path: str) -> str:
    """读 utf-8 文本（errors=replace 兜底乱码）—— 收敛三份 _read_text。"""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def write_text(path: str, text: str) -> str:
    """utf-8 落盘并返回路径（返回 str 便于链式拼接/打印）。"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def schema_doc_path(name: str) -> str:
    """定位 docs/schemas/<name>（收敛两份 _schema_path）。"""
    return os.path.join(ROOT, "docs", "schemas", name)


def output_dir(sub: str) -> str:
    """定位并创建 outputs/<sub>，返回目录绝对路径（收敛 day32 的 _out_dir）。"""
    out: str = os.path.join(ROOT, "outputs", sub)
    os.makedirs(out, exist_ok=True)
    return out


# ═══════════════════════════════════════════════════════
# 实验（练习 1：等价性回归 —— 旧实现逐字复刻 vs 新公共实现）
# ═══════════════════════════════════════════════════════
def exp1_equivalence() -> list[str]:
    """等价性回归：同一输入，旧实现（3 份 _read_text / 2 份 _schema_path / 1 份 _out_dir）
    与新公共实现的输出必须一致。返回不一致项列表（空 = 全等）。

    旧实现从 day31/day32 逐字复制（教学展示"重复长什么样"）；新实现见文件顶部。
    ⚠️ 只读 + 系统临时目录写测试：不在项目里留任何残留。
    """
    mismatches: list[str] = []

    # ── 旧 _read_text（day31_bug_analyzer 第 369 行 逐字）──
    def legacy_read_day31(path: str) -> str:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    # ── 旧 _read_text（day32_data_schema 第 103 行 逐字，与 day32_run_pipeline 第 76 行相同）──
    def legacy_read_day32(path: str) -> str:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()

    # ── 旧 _schema_path（day32_data_schema 第 109 行 逐字）──
    def legacy_schema_path_day32(name: str) -> str:
        here: str = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(here, "..", "..", "docs", "schemas", name)

    # ── 旧 _out_dir（day32_data_generator 第 301 行 逐字）──
    def legacy_out_dir_day32() -> str:
        here: str = os.path.dirname(os.path.abspath(__file__))
        out: str = os.path.join(here, "..", "..", "outputs", "data_gen")
        os.makedirs(out, exist_ok=True)
        return out

    # ── 1. 读文件等价（真实资产：需求文档 + schema 样本）──
    samples: list[str] = [
        os.path.join(ROOT, "docs", "requirements", "login_requirement.md"),
        schema_doc_path("users.md"),
        schema_doc_path("orders.json"),
    ]
    for path in samples:
        expected: str = legacy_read_day31(path)
        for label, got in [
            ("day31._read_text", legacy_read_day31(path)),
            ("day32._read_text", legacy_read_day32(path)),
            ("day35.read_text", read_text(path)),
        ]:
            if got != expected:
                mismatches.append(f"读文件不一致 {label} @ {os.path.basename(path)}")
    print(f"  ✅ 读文件等价：{len(samples)} 个样本 × 3 份实现（day31/day32/day35）全部一致")

    # ── 2. schema 路径定位等价 ──
    # ⚠️ 旧实现 join 出的路径带 '..' 段（src/agent/../../docs/...），os.path.join 不折叠 '..' →
    #    字面串不同但语义同一点。等价断言用 normpath 归一化后比较（比语义，不比字面）。
    p_new: str = schema_doc_path("users.md")
    p_legacy: str = legacy_schema_path_day32("users.md")
    if os.path.normpath(p_new) != os.path.normpath(p_legacy):
        mismatches.append(f"_schema_path 不一致: {p_new} != {p_legacy}")
    else:
        print(f"  ✅ _schema_path 等价（normpath）: {os.path.normpath(p_new)}")
    if not os.path.isfile(p_new):
        mismatches.append(f"users.md 样本不在位: {p_new}")

    # ── 3. 产物目录定位等价（data_gen 在真实项目已存在；冒烟骨架已预建）──
    d_new: str = output_dir("data_gen")
    d_legacy: str = legacy_out_dir_day32()
    if os.path.normpath(d_new) != os.path.normpath(d_legacy):
        mismatches.append(f"_out_dir 不一致: {d_new} != {d_legacy}")
    else:
        print(f"  ✅ _out_dir 等价（normpath）: {os.path.normpath(d_new)}")

    # ── 4. 写读往返（系统临时目录，零残留）──
    with tempfile.TemporaryDirectory() as tmp:
        rt_path: str = os.path.join(tmp, "roundtrip.txt")
        content: str = "Day 35 等价回归：中文 + ascii"
        write_text(rt_path, content)
        if read_text(rt_path) != content:
            mismatches.append("write_text/read_text 往返不一致")

    if mismatches:
        print("  ❌ 存在不一致项：")
        for m in mismatches:
            print(f"    - {m}")
    else:
        print("  ✅ 等价性回归通过：抽取未改变任何行为（同输入同输出）")
    return mismatches


if __name__ == "__main__":
    """完成态：等价回归 + 结论提示。"""
    mismatches = exp1_equivalence()
    if mismatches:
        raise SystemExit("❌ 等价回归未通过，先修再继续")
    print("=" * 60)
    print("💡 要点回顾：")
    print("   rule of three：一次内联 / 二次考虑 / 三次抽取 —— 今天已是第三份（触发点）")
    print("   公共底座 = 叶子模块（无框架依赖）；路径锚 __file__；等价回归 = 抽取的安全网")
    print("   Day 36 重构时：本文件函数物理并入 src/agent/utils.py，旧脚本改薄包装 import")
