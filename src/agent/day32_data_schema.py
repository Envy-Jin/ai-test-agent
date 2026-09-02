"""
Day 32 练习 1/2：测试数据生成器 —— 字段规则 Schema + 加载分派 + 解析 Chain

实验↔步骤↔运行命令 映射：
  exp1_schema_smoke()    步骤2  python -c "from day32_data_schema import exp1_schema_smoke; exp1_schema_smoke()"    零API
  exp2_load_dispatch()   步骤2  python -c "from day32_data_schema import exp2_load_dispatch; exp2_load_dispatch()"   零API
  exp3_parse_schema()    步骤3  python -c "from day32_data_schema import exp3_parse_schema; exp3_parse_schema()"    真实API
  main()                 步骤3  python day32_data_schema.py（完成态，真实 API 取消注释）

设计（步骤 1 的 5 个决策落地）：
  A. 主线形态 = Chain（字段规则解析）+ 确定性生成引擎（day32_data_generator）——造数 = 确定性最高的专项
  B. Schema = FieldRule（字段级规则）+ DataSchema（表级），FieldType Literal 枚举锁死（10 类）
  C. 双输入分派：.json 机器可读走确定性解析（json.loads 直读，不走 load_document——Day 30 教训）；
     .md/.txt 自然语言走模型解析（练习 2 的 parse_schema_text）
  D. 五类产物（正常/边界/异常/SQL/Mock）全部由 day32_data_generator 确定性合成
  E. 分界线实证：day32_run_pipeline.exp7_model_vs_code（代码合成 vs 模型直出跑两次 diff）

模型（用户指定）：主 gemini-3.5-flash-lite（thinking_level="medium"）/ 备 gemini-3.1-flash-lite（temperature=0.2）
容错顺序：先 with_structured_output 再 with_fallbacks（Day 29 坑 5，fallbacks.py:592）

用法：
  python -c "from day32_data_schema import exp1_schema_smoke; exp1_schema_smoke()"   # 零 API
  python -c "from day32_data_schema import exp2_load_dispatch; exp2_load_dispatch()"  # 零 API
  python -c "from day32_data_schema import exp3_parse_schema; exp3_parse_schema()"   # 真实 API
  python day32_data_schema.py   # 完成态（步骤 3 末尾给出）
"""

import json
import os
import sys
from typing import Any, Literal

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()  # ⚠️ 必须在 langchain import 之前（Day 25 口诀）

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field
from dataclasses import dataclass, field

from day29_doc_loader import load_document


# ═══════════════════════════════════════════════════════
# 字段规则 Schema（设计决策 B：FieldRule 字段级 + DataSchema 表级，FieldType Literal 锁死）
# ═══════════════════════════════════════════════════════

FieldType = Literal[
    "int", "float", "str", "bool", "date", "datetime", "enum", "phone", "email", "username"
]


class FieldRule(BaseModel):
    """字段级规则（生成引擎的唯一依据，模型/代码双路径都产出它）。"""

    name: str = Field(description="字段名，如 phone")
    field_type: FieldType = Field(description="字段类型：int/float/str/bool/date/datetime/enum/phone/email/username")
    required: bool = Field(description="是否必填（true=必填，false=可空）")
    description: str = Field(description="字段语义描述，如 '手机号'")
    min_value: float | None = Field(default=None, description="数值下界（int/float 用）")
    max_value: float | None = Field(default=None, description="数值上界（int/float 用）")
    max_length: int | None = Field(default=None, description="最大长度（str 系用，如 varchar(50) 的 50）")
    pattern: str | None = Field(default=None, description="格式正则（如手机号 ^1[3-9]\\d{9}$）")
    enum_values: list[str] = Field(default_factory=list, description="枚举取值（enum 用）")
    default: str | None = Field(default=None, description="默认值（可选字段用）")
    primary_key: bool = Field(default=False, description="是否主键（SQL 渲染跳过自增列）")


class DataSchema(BaseModel):
    """表级数据模型（生成引擎的输入）。"""

    table_name: str = Field(description="表名/模型名，如 users")
    description: str = Field(description="表语义描述")
    fields: list[FieldRule] = Field(description="字段规则列表")

# ═══════════════════════════════════════════════════════
# 加载分派（设计决策 C：.json 走代码 / .md 走模型；Day 30 第二次落地）
# ═══════════════════════════════════════════════════════

def load_schema(path: str) -> DataSchema | None:
    """加载数据模型：.json 走确定性解析，.md/.txt 走模型解析（练习 2 补全 parse_schema_text）。

    ⚠️ 教学点（Day 30 教训延续）：load_document 只支持 .txt/.md/.docx，
       .json 是机器可读数据 → 直接 open + json.loads（分派逻辑 ≠ 路径打通）。
    """
    ext: str = os.path.splitext(path)[1].lower()
    if ext == ".json":
        data: object = json.loads(_read_text(path))
        if not isinstance(data, dict):
            raise ValueError(f"JSON 数据模型必须是对象，实际 {type(data).__name__}")
        return DataSchema.model_validate(data)
    # .md / .txt：复用 Day 29 加载器读文本 → 模型解析（练习 2 实现 parse_schema_text）
    doc = load_document(path)
    if doc is None:
        return None
    return parse_schema_text(doc.text)


def _read_text(path: str) -> str:
    """读文件（utf-8，errors=replace）。"""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _schema_path(name: str) -> str:
    """样本路径（路径基准钉 __file__，2026-08-28 用户规范）。"""
    here: str = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "..", "docs", "schemas", name)


# ═══════════════════════════════════════════════════════
# 解析 Chain（设计决策 A：固定单任务；容错 = with_fallbacks，Day 29 坑 5 顺序）
# ═══════════════════════════════════════════════════════

SCHEMA_PARSE_PROMPT = """你是一名资深测试工程师，负责把数据模型（表结构）的字段规则解析成结构化 Schema。

【解析要求】
1. 逐字段提取：name（字段名）、field_type（int/float/str/bool/date/datetime/enum/phone/email/username）
2. required：必填=true；可选（含"可选""默认"）=false
3. description：字段语义一句话（如 "手机号"）
4. 数值字段：min_value/max_value 从"范围/最小/最大"提取（没有就填 null）
5. 字符串字段：max_length 从 varchar(N)/"长度不超过 N"提取；pattern 从"格式/只允许"提取——
   手机号格式 1[3-9] 开头共 11 位 → ^1[3-9]\\d{{9}}$；只允许字母数字下划线 → ^[A-Za-z0-9_]+$
   （⚠️ 模板花括号已转义：双花括号 {{9}} 渲染后为单花括号，Day 30 坑 1 变体——prompt 模板里写正则必须转义花括号，2026-09-01 实测：不转义则构建期报 Invalid variable name '9'）
6. enum 字段：enum_values 从 enum(...) 或"取值"提取
7. primary_key：标注"主键"的字段 = true
8. 不要臆造字段：文本里没有的字段不要加，字段规则没给的不猜

【规范】
- description 用中文；field_type 严格用给定枚举；不确定的类型选 str"""


def build_schema_chain():
    """字段规则解析 Chain：prompt | llm（主+备 with_fallbacks）| 结构化输出。

    ⚠️ 返回注解【留空】（Day 26 口诀 25）；顺序【先 with_structured_output 再 with_fallbacks】
       （Day 29 坑 5：反了走 RunnableWithFallbacks.__getattr__ → pyright 推断 Any）。
    """
    llm_primary = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", thinking_level="medium")  # 主
    llm_backup = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0.2)  # 备（确定性优先）
    main = llm_primary.with_structured_output(DataSchema)
    backup = llm_backup.with_structured_output(DataSchema)
    llm = main.with_fallbacks([backup])
    prompt = ChatPromptTemplate.from_messages([
        ("system", SCHEMA_PARSE_PROMPT),
        ("human", "请解析以下数据模型的字段规则：\n\n{schema_text}"),
    ])
    return prompt | llm


def parse_schema_text(text: str) -> DataSchema:
    """自然语言字段规则 → DataSchema（模型解析）。

    ⚠️ 返回注解【明确写 DataSchema】：链 invoke 静态推断是 dict|BaseModel 联合 →
       isinstance 收窄 + dict 兜底 model_validate（Day 29 实操验证的写法）。
    """
    chain = build_schema_chain()
    result = chain.invoke({"schema_text": text})
    if isinstance(result, DataSchema):
        return result
    if not isinstance(result, dict):
        raise ValueError(f"解析失败：链返回 {type(result).__name__}，期望 dict 或 DataSchema")
    return DataSchema.model_validate(result)


# ═══════════════════════════════════════════════════════
# 质检（设计决策 A 延续：纯函数，零 API 可冒烟——质量红线归代码）
# ═══════════════════════════════════════════════════════

@dataclass
class SchemaIssue:
    """一条质检问题。level: ERROR(硬伤) / WARNING(建议)。"""

    level: str
    message: str


@dataclass
class SchemaValidationReport:
    """字段规则质检报告。"""

    issues: list[SchemaIssue] = field(default_factory=list)

    @property
    def has_error(self) -> bool:
        return any(issue.level == "ERROR" for issue in self.issues)


def validate_schema(schema: DataSchema) -> SchemaValidationReport:
    """字段规则质检（纯函数，零 API）：硬检查=无字段/字段名重复/enum 无取值；软检查=无边界依据。"""
    report = SchemaValidationReport()
    if not schema.fields:
        report.issues.append(SchemaIssue("ERROR", "字段列表为空"))
        return report
    names: list[str] = [f.name for f in schema.fields]
    if len(names) != len(set(names)):
        dup: list[str] = sorted({n for n in names if names.count(n) > 1})
        report.issues.append(SchemaIssue("ERROR", f"字段名重复: {dup}"))
    for f in schema.fields:
        if f.primary_key:
            continue
        if f.field_type == "enum" and not f.enum_values:
            report.issues.append(SchemaIssue("ERROR", f"{f.name} 是 enum 但 enum_values 为空"))
        if f.field_type in ("int", "float") and not f.primary_key and f.min_value is None and f.max_value is None:
            report.issues.append(SchemaIssue("WARNING", f"{f.name} 无 min/max（边界测试没依据）"))
        if f.field_type in ("str", "phone", "email", "username") and f.max_length is None:
            report.issues.append(SchemaIssue("WARNING", f"{f.name} 无 max_length（超长测试没依据）"))
        if f.field_type in ("phone", "email") and f.pattern is None:
            report.issues.append(SchemaIssue("WARNING", f"{f.name} 无 pattern（格式校验没依据）"))
    return report


def render_schema_overview(schema: DataSchema, report: SchemaValidationReport) -> str:
    """渲染字段规则概览 Markdown（确定性代码；练习 4/5 落盘可评审）。"""
    lines: list[str] = [
        f"# 数据模型：{schema.table_name}",
        "",
        f"- **表语义**：{schema.description}",
        f"- **字段数**：{len(schema.fields)}",
        "",
        "| 字段 | 类型 | 必填 | 边界/格式 | 语义 |",
        "|------|------|------|-----------|------|",
    ]
    for f in schema.fields:
        bounds: list[str] = []
        if f.min_value is not None or f.max_value is not None:
            bounds.append(f"{f.min_value}~{f.max_value}")
        if f.max_length is not None:
            bounds.append(f"≤{f.max_length}")
        if f.pattern is not None:
            bounds.append(f"格式:{f.pattern}")
        if f.enum_values:
            bounds.append(f"枚举:{'/'.join(f.enum_values)}")
        bounds_text: str = "; ".join(bounds) if bounds else "-"
        lines.append(f"| {f.name} | {f.field_type} | {'是' if f.required else '否'} | {bounds_text} | {f.description} |")
    lines.append("")
    lines.append("## 质检报告")
    if report.issues:
        for issue in report.issues:
            lines.append(f"- **[{issue.level}]** {issue.message}")
    else:
        lines.append("- ✅ 无问题")
    return "\n".join(lines)



# ═══════════════════════════════════════════════════════
# 实验
# ═══════════════════════════════════════════════════════

def exp1_schema_smoke() -> None:
    """实验：Schema 构造 + 默认值 + 类型收窄（零 API）——断言 Literal 枚举合法、默认值生效。"""
    print("=" * 60)
    print("实验：exp1_schema_smoke —— FieldSchema 构造（零 API）")
    # 手工构造 users 表样例（模拟模型解析结果）
    schema = DataSchema(
        table_name="users",
        description="用户信息表",
        fields=[
            FieldRule(name="id", field_type="int", required=True, description="主键自增", primary_key=True),
            FieldRule(name="phone", field_type="phone", required=True, description="手机号",
                      pattern=r"^1[3-9]\d{9}$", max_length=11),
            FieldRule(name="age", field_type="int", required=True, description="年龄",
                      min_value=1, max_value=150),
            FieldRule(name="gender", field_type="enum", required=False, description="性别",
                      enum_values=["男", "女", "未知"], default="未知"),
        ],
    )
    assert schema.table_name == "users"
    assert len(schema.fields) == 4
    # 默认值生效：没给的字段是 None / False / 空列表
    assert schema.fields[0].min_value is None
    assert schema.fields[1].max_length == 11
    assert schema.fields[2].min_value == 1 and schema.fields[2].max_value == 150
    assert schema.fields[3].default == "未知"
    # 类型收窄：Literal 枚举非法值构建期就报错（pydantic 校验）
    try:
        FieldRule(name="bad", field_type="object", required=True, description="x")  # type: ignore[arg-type]
        raise AssertionError("field_type='object' 应触发 Literal 校验失败")
    except Exception as e:
        print(f"  ✅ 非法枚举被 Pydantic 拦截: {type(e).__name__}")
    # 字段清单（教学点：类型是语义（模型选），合成是规则（代码写））
    names: list[str] = [f.name for f in schema.fields]
    assert names == ["id", "phone", "age", "gender"]
    print(f"  ✅ Schema 构造 ok: {schema.table_name}.{names}")
    print("✅ Schema 冒烟通过")


def exp2_load_dispatch() -> None:
    """实验：双输入分派（零 API）——orders.json 走确定性解析（不走模型、不走 load_document）。"""
    print("=" * 60)
    print("实验：exp2_load_dispatch —— 双输入分派（零 API）")
    # orders.json：机器可读 → 确定性路径（json.loads 直读）
    orders_path: str = _schema_path("orders.json")
    schema: DataSchema | None = load_schema(orders_path)
    assert schema is not None, "orders.json 解析失败"
    assert schema.table_name == "orders"
    assert len(schema.fields) == 6
    amount: FieldRule = next(f for f in schema.fields if f.name == "amount")
    assert amount.field_type == "float"
    assert amount.min_value == 0.01 and amount.max_value == 999999.99
    status: FieldRule = next(f for f in schema.fields if f.name == "status")
    assert status.enum_values == ["待支付", "已支付", "已发货", "已完成", "已取消"]
    print(f"  ✅ orders.json 确定性解析 ok: {schema.table_name} 共 {len(schema.fields)} 字段")
    for f in schema.fields:
        print(f"     - {f.name} [{f.field_type}] 必填={f.required}"
              f"{f' 范围={f.min_value}~{f.max_value}' if f.min_value is not None or f.max_value is not None else ''}")
    # users.md：自然语言 → 模型路径（练习 2 的 exp3 验证；这里确认分派走对分支）
    users_path: str = _schema_path("users.md")
    print(f"  🔍 users.md 走 .md 分支 → 模型解析（练习 2 的 exp3_parse_schema 验证，这里不触发）")
    assert os.path.exists(users_path), "users.md 样本缺失"
    print("✅ 加载分派冒烟通过")


def exp3_parse_schema(path: str | None = None) -> DataSchema | None:
    """端到端：users.md（自然语言）→ 模型解析 → 质检 → 渲染概览（真实 API）。"""
    print("=" * 60)
    print(f"实验：exp3_parse_schema —— 字段规则模型解析（{path or 'users.md'}）")
    target: str = path or _schema_path("users.md")
    schema: DataSchema | None = load_schema(target)  # .md 分支 → parse_schema_text（模型）
    if schema is None:
        print("❌ 加载失败")
        return None
    print(f"  ✅ 解析完成: {schema.table_name} 共 {len(schema.fields)} 字段")
    report: SchemaValidationReport = validate_schema(schema)
    for f in schema.fields:
        print(f"     - {f.name} [{f.field_type}] 必填={f.required}"
              f"{f' 范围={f.min_value}~{f.max_value}' if f.min_value is not None or f.max_value is not None else ''}"
              f"{f' 格式={f.pattern}' if f.pattern is not None else ''}"
              f"{f' 枚举={f.enum_values}' if f.enum_values else ''}"
              f"{f' 长度≤{f.max_length}' if f.max_length is not None else ''}")
    if report.has_error:
        print(f"  ⚠️ 质检存在 ERROR: {[i.message for i in report.issues if i.level == 'ERROR']}")
    else:
        print(f"  ✅ 质检通过（{len(report.issues)} 条建议）")
    overview: str = render_schema_overview(schema, report)
    print("  ── 概览预览 ──")
    print(overview[:600])
    return schema


if __name__ == "__main__":
    """完成态：零 API 冒烟 + 真实 API 端到端（取消注释切换）。"""
    # exp1_schema_smoke()
    # exp2_load_dispatch()
    exp3_parse_schema()  # 真实 API，取消注释
    print("\n💡 要点回顾：")
    print("   分层第四次落地：模型只解析字段规则（FieldSchema），造数归 day32_data_generator（确定性代码）")
    print("   双输入分派：.md 走模型（语义理解），.json 走代码（结构化直读）——同一个 DataSchema 契约")
    print("   质检归代码：validate_schema 零 API，ERROR 硬检查（无字段/重名/enum 空）")

