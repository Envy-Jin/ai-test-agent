"""
Day 32 练习 5：端到端闭环 + 模型 vs 代码对照实验

实验↔步骤↔运行命令 映射：
  exp6_pipeline()          步骤6  python -c "from day32_run_pipeline import exp6_pipeline; exp6_pipeline()"   真实API
  exp7_model_vs_code()     步骤6  python -c "from day32_run_pipeline import exp7_model_vs_code; exp7_model_vs_code()"  真实API
  main()                   步骤6  python day32_run_pipeline.py（完成态，真实 API 默认跑 exp6）

设计（步骤 1 决策 E）：
  exp6_pipeline：双输入端到端——users.md（模型路径）+ orders.json（确定性路径）→ 同一个生成引擎
    → 正常/边界/异常 → 校验（正常全通过）→ SQL + Mock → 全产物落盘 → 生成报告
  exp7_model_vs_code：分界线实证——同一 schema 文本，代码合成 vs 模型直出，各跑两次看可重复性

用法：
  python -c "from day32_run_pipeline import exp6_pipeline; exp6_pipeline()"   # 真实 API
  python -c "from day32_run_pipeline import exp7_model_vs_code; exp7_model_vs_code()"  # 真实 API
  python day32_run_pipeline.py    # 完成态（exp6 + 提示）
"""
import json
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()  # ⚠️ 必须在 langchain import 之前

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from day32_data_generator import (
    Record,
    gen_abnormal_data,
    gen_boundary_data,
    gen_normal_data,
    render_mock_json,
    render_sql_inserts,
    save_json,
    save_text,
    validate_records,
    _out_dir,
)
from day32_data_schema import (
    DataSchema,
    SchemaValidationReport,
    load_schema,
    render_schema_overview,
    validate_schema,
)


def _schema_path(name: str) -> str:
    """样本路径（路径基准钉 __file__）。"""
    here: str = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "..", "docs", "schemas", name)


def _model_direct_gen(schema_text: str) -> str:
    """让模型直接生成 5 条正常测试数据（非结构化输出，对照实验用）。

    ⚠️ StrOutputParser（Day 19 已学）：AIMessage.content 可能是 str 或 blocks 列表，
       由 parser 统一转文本（2026-09-01 实测：langchain-core 1.5.2 无 content_to_text，改用 parser）。
    """
    llm = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", thinking_level="medium")
    prompt = ChatPromptTemplate.from_messages([
        ("system", "你是测试数据生成器。根据数据模型生成 5 条正常测试数据。"
                   "只输出 JSON 数组（每条是一个对象，键为字段名），不要任何其他文字。"),
        ("human", "数据模型：\n{schema_text}"),
    ])
    return (prompt | llm | StrOutputParser()).invoke({"schema_text": schema_text})


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()



def exp6_pipeline(
    schema_files: list[str] | None = None,
    subdir: str = "",
) -> None:
    """端到端：多输入殊途同归 → 同一生成引擎 → 全产物落盘。

    Day 41 参数化（原来把 users.md + orders.json **写死在循环里**，第二个场景
    根本没法用它 —— 蓝图工厂把 outputs 参数化了、cmd 却还指向登录的资产，
    这正是「半参数化」最隐蔽的后果：产物路径对了、内容却是另一个场景的）：

      schema_files=None → `["users.md", "orders.json"]`（= 原行为，Day 34 的
                          `exp6_pipeline()` 一字不改也照跑 → 向后兼容）
      subdir            → 产物子目录（场景命名空间）；"" = outputs/data_gen 根
    """
    print("=" * 60)
    print("实验：exp6_pipeline —— 端到端闭环")
    out: str = _out_dir()
    if subdir:
        out = os.path.join(out, subdir)
        os.makedirs(out, exist_ok=True)  # ⚠️ save_json 不会建父目录，子目录必须自己建
    print(f"  产物目录: outputs/data_gen/{subdir}" if subdir else "  产物目录: outputs/data_gen")
    report_lines: list[str] = ["# Day 32 测试数据生成报告", ""]

    files: list[str] = ["users.md", "orders.json"] if schema_files is None else list(schema_files)
    for filename in files:
        name: str = os.path.splitext(filename)[0]
        path: str = _schema_path(filename)
        print(f"  ── 输入: {filename} ──")
        schema: DataSchema | None = load_schema(path)
        if schema is None:
            print(f"  ❌ {name} 加载失败，跳过")
            continue
        v_report: SchemaValidationReport = validate_schema(schema)
        print(f"  ✅ 解析出 {schema.table_name} 共 {len(schema.fields)} 字段"
              f"{'  ⚠️ERROR' if v_report.has_error else ''}")
        # 生成五类
        normal: list[Record] = gen_normal_data(schema, count=5)
        boundary: list[Record] = gen_boundary_data(schema)
        abnormal: list[Record] = gen_abnormal_data(schema)
        # 校验：正常数据必须全通过（生成质量自证）；边界/异常不校验（界外/payload 预期"非法"）
        errors: list[str] = validate_records(schema, normal)
        if errors:
            print(f"  ❌ 正常数据校验失败 {len(errors)} 条: {errors[:3]}")
            continue
        print(f"  ✅ 正常数据 {len(normal)} 条校验全通过 | 边界 {len(boundary)} 条 | 异常 {len(abnormal)} 条")
        # 落盘
        save_json(os.path.join(out, f"{name}_normal.json"), normal)
        save_json(os.path.join(out, f"{name}_boundary.json"), boundary)
        save_json(os.path.join(out, f"{name}_abnormal.json"), abnormal)
        save_text(os.path.join(out, f"{name}_insert.sql"), render_sql_inserts(schema, normal))
        save_text(os.path.join(out, f"{name}_mock.json"), render_mock_json(schema, normal))
        print(f"  ✅ 已落盘 outputs/data_gen/{subdir + '/' if subdir else ''}{name}_*.json/.sql")
        # 报告追加
        report_lines.append(f"## {name}（{filename}）")
        report_lines.append(f"- 字段数：{len(schema.fields)} | 正常 {len(normal)} | 边界 {len(boundary)} | 异常 {len(abnormal)}")
        report_lines.append(f"- 质检：{'⚠️ ' + str([i.message for i in v_report.issues]) if v_report.issues else '✅ 无问题'}")
        report_lines.append("")

    save_text(os.path.join(out, "generation_report.md"), "\n".join(report_lines))
    print(f"  ✅ 生成报告落盘: outputs/data_gen/{subdir + '/' if subdir else ''}generation_report.md")
    print(f"  ── 双路径殊途同归：文档（模型解析）与 .json（代码解析）都产出同一结构 DataSchema，生成引擎完全复用")


def exp7_model_vs_code(schema_path: str | None = None) -> None:
    """分界线实证：同一 schema，代码合成 vs 模型直出，各跑两次看可重复性（真实 API）。

    结论预期：路径 A 两次完全一致（确定性）；路径 B 两次大概率不一致（非确定性 + 烧 token）。
    """
    print("=" * 60)
    print("实验：exp7_model_vs_code —— 模型 vs 代码分界线实证")
    path: str = schema_path or _schema_path("users.md")
    schema: DataSchema | None = load_schema(path)
    if schema is None:
        print("❌ 加载失败")
        return
    schema_text: str = _read_text(path)

    # 路径 A：代码合成（确定性）
    a1: list[Record] = gen_normal_data(schema, count=5)
    a2: list[Record] = gen_normal_data(schema, count=5)
    same_a: bool = a1 == a2
    print(f"  [A] 代码合成：跑两次 diff 一致 = {same_a}（确定性，零成本）")

    # 路径 B：模型直出（非结构化输出，让模型直接生成 5 条正常数据 JSON）
    b1: str = _model_direct_gen(schema_text)
    b2: str = _model_direct_gen(schema_text)
    same_b: bool = b1 == b2
    print(f"  [B] 模型直出：跑两次 diff 一致 = {same_b}（非确定性，烧 token）")
    print(f"      第一次输出（节选）: {b1[:200].replace(chr(10), ' ')}")
    print(f"      第二次输出（节选）: {b2[:200].replace(chr(10), ' ')}")

    print("\n  ── 结论（写进笔记）──")
    print(f"  代码合成 确定性={same_a}：可 diff / 可评审 / 可回归 / 零成本 → 造数归代码")
    print(f"  模型直出 确定性={same_b}：每次不同 / 烧 token / 可能漏字段 → 模型只解析规则")
    print(f"  分界线：{'✅ 实证成立（代码确定性、模型非确定性）' if same_a and not same_b else '⚠️ 本次模型恰好一致，多跑几次再下结论'}")





if __name__ == "__main__":
    """完成态：端到端闭环（真实 API）默认跑；对照实验取消注释。"""
    # exp6_pipeline()
    exp7_model_vs_code()  # 真实 API，取消注释（分界线实证）
    print("\n💡 要点回顾：")
    print("   双输入殊途同归：.md 模型解析 / .json 代码解析 → 同一 DataSchema → 生成引擎完全复用")
    print("   正常数据校验全通过 = 生成器自证质量；边界/异常预期'非法'（界外/payload 是设计意图）")
    print("   exp7 对照实验：代码合成可复现，模型直出不可复现——造数归代码的实测证据")