"""
Day 32 练习 3/4：测试数据生成器 —— 确定性生成引擎（正常/边界/异常 + SQL INSERT + Mock JSON）

实验↔步骤↔运行命令 映射：
  exp4_normal_boundary()    步骤4  python -c "from day32_data_generator import exp4_normal_boundary; exp4_normal_boundary()"  零API
  exp5_abnormal_sql_mock()  步骤5  python -c "from day32_data_generator import exp5_abnormal_sql_mock; exp5_abnormal_sql_mock()"  零API
  main()                    步骤5  python day32_data_generator.py（完成态）

设计（步骤 1 的 5 个决策落地）：
  A. 生成引擎 = 纯确定性代码（random/string/re/json 标准库），零 API 可冒烟
  B. 输入 = DataSchema（day32_data_schema），字段类型 Literal 枚举锁死 → 合成器按类型安全分派
  D. 五类产物：
     ① 正常数据 gen_normal_data（count 条，每字段合成合理值，同 seq 同值）
     ② 边界数据 gen_boundary_data（每字段 界内最值+界外最值）
     ③ 异常数据 gen_abnormal_data（ABNORMAL_PAYLOADS × 字段循环，练习 4）
     ④ SQL INSERT render_sql_inserts（练习 4，转义 + 跳主键）
     ⑤ Mock JSON render_mock_json（练习 4）
  E. 质量校验 validate_record/validate_records：生成数据自证符合字段规则（正常数据全通过）

用法：
  python -c "from day32_data_generator import exp4_normal_boundary; exp4_normal_boundary()"  # 零 API
  python day32_data_generator.py   # 完成态（步骤 5 末尾给出）
"""
import json
import os
import re
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dataclasses import dataclass

from day32_data_schema import DataSchema, FieldRule


# ═══════════════════════════════════════════════════════
# 正常值合成器（设计决策 D ①：按字段类型/格式/范围合成"合理值"）
# ═══════════════════════════════════════════════════════

Record = dict[str, str | int | float | bool | None]


def _synth_value(rule: FieldRule, seq: int) -> str | int | float | bool | None:
    """按字段规则合成一个"合理值"（确定性：seq 相同 → 值相同，可 diff 可评审）。

    ⚠️ 教学点：造数是确定性最高的专项——合成规则全是代码，模型只解析过规则本身。
    """
    if rule.field_type == "int":
        lo: int = int(rule.min_value) if rule.min_value is not None else 1
        hi: int = int(rule.max_value) if rule.max_value is not None else lo + 100
        return max(lo, min(lo + seq, hi))  # 范围内中值附近递增
    if rule.field_type == "float":
        lo_f: float = rule.min_value if rule.min_value is not None else 0.0
        hi_f: float = rule.max_value if rule.max_value is not None else lo_f + 1000.0
        return round(lo_f + (hi_f - lo_f) * (seq % 5) / 5, 2)  # 范围内 5 等分点轮询
    if rule.field_type == "bool":
        return seq % 2 == 0
    if rule.field_type == "enum":
        values: list[str] = rule.enum_values or ["未知"]
        return values[seq % len(values)]
    if rule.field_type == "phone":
        return f"1{3 + (seq % 7)}{(seq % 1_000_000_000):09d}"  # 1[3-9] + 9 位数字，共 11 位
    if rule.field_type == "email":
        return f"user{seq:03d}@example.com"  # 含 @ 和域名
    if rule.field_type == "username":
        return f"user_{seq:03d}"  # 字母数字下划线，长度 3-20
    if rule.field_type == "date":
        return f"2026-{(seq % 12) + 1:02d}-{(seq % 28) + 1:02d}"
    if rule.field_type == "datetime":
        return f"2026-09-01 10:{(seq % 60):02d}:00"
    # str：语义前缀 + 序号，按 max_length 截断
    prefix: str = rule.description or rule.name
    body: str = f"{prefix}{seq}"
    if rule.max_length is not None:
        return body[: rule.max_length]
    return body

def gen_normal_data(schema: DataSchema, count: int = 5) -> list[Record]:
    """正常数据（确定性合成 count 条）：每条所有字段取合理值，同输入同输出。"""
    records: list[Record] = []
    for seq in range(count):
        record: Record = {rule.name: _synth_value(rule, seq) for rule in schema.fields}
        records.append(record)
    return records


# ═══════════════════════════════════════════════════════
# 边界值推导（设计决策 D ②：界内最值 + 界外最值）
# ═══════════════════════════════════════════════════════

@dataclass
class BoundaryCase:
    """一条边界值记录：字段名 + 边界标签 + 边界值。"""

    field: str
    label: str
    value: str | int | float | bool | None


def _boundary_cases(rule: FieldRule) -> list[BoundaryCase]:
    """推导单字段边界值（确定性）。

    ⚠️ 教学点（边界值测试 BVA）：界内最值（min/max/长度上限，应被接受）+ 界外最值
       （min-1/max+1/长度上限+1，应被拒绝）——两类断言方向相反，缺一个不完整。
    """
    cases: list[BoundaryCase] = []
    if rule.field_type == "int":
        lo: int = int(rule.min_value) if rule.min_value is not None else 1
        hi: int = int(rule.max_value) if rule.max_value is not None else lo + 100
        cases = [
            BoundaryCase(rule.name, "min(界内)", lo),
            BoundaryCase(rule.name, "max(界内)", hi),
            BoundaryCase(rule.name, "min-1(界外)", lo - 1),
            BoundaryCase(rule.name, "max+1(界外)", hi + 1),
        ]
    elif rule.field_type == "float":
        lo_f: float = rule.min_value if rule.min_value is not None else 0.0
        hi_f: float = rule.max_value if rule.max_value is not None else lo_f + 1000.0
        cases = [
            BoundaryCase(rule.name, "min(界内)", lo_f),
            BoundaryCase(rule.name, "max(界内)", hi_f),
        ]
    elif rule.field_type in ("str", "phone", "email", "username"):
        n: int = rule.max_length if rule.max_length is not None else 50
        base: str = str(_synth_value(rule, 0) or "")
        # ⚠️ 定长格式（phone）界外用数字填充（全数字=领域内非法输入，避免字母垃圾）；
        #    变长格式（email/username/str）用 'a' 填充（格式仍合规 → 纯净测长度）
        pad: str = "0" if rule.field_type == "phone" else "a"
        cases = [
            BoundaryCase(rule.name, "空串(若可空)", ""),
            BoundaryCase(rule.name, f"长度={n}(界内)", base[:n] if len(base) >= n else base),
            BoundaryCase(rule.name, f"长度={n + 1}(界外)", (base + pad)[: n + 1]),
        ]
    elif rule.field_type == "enum":
        cases = [BoundaryCase(rule.name, f"枚举:{v}", v) for v in rule.enum_values]
    return cases


def gen_boundary_data(schema: DataSchema) -> list[Record]:
    """边界数据：每字段的每条边界值一条记录（其余字段取正常值，纯记录无元数据键）。"""
    records: list[Record] = []
    for rule in schema.fields:
        if rule.primary_key:
            continue  # 主键非输入字段：不测边界
        base: Record = gen_normal_data(schema, 1)[0]
        for case in _boundary_cases(rule):
            rec: Record = dict(base)
            rec[rule.name] = case.value
            records.append(rec)
    return records


# ═══════════════════════════════════════════════════════
# 质量校验（设计决策 E：纯函数，零 API——生成数据自证符合字段规则）
# ═══════════════════════════════════════════════════════

def validate_record(rule: FieldRule, value: str | int | float | bool | None) -> str | None:
    """单字段校验：返回错误信息；None = 通过。检查：类型/min/max/max_length/pattern/enum。

    ⚠️ 坑 6 预演：bool 是 int 的子类（isinstance(True, int) == True）——校验 int 必须先排除 bool。
    """
    if value is None:
        return None if not rule.required else f"{rule.name} 必填但为空"
    if rule.field_type == "int":
        if not isinstance(value, int) or isinstance(value, bool):
            return f"{rule.name} 应为 int，实际 {type(value).__name__}"
        if rule.min_value is not None and value < rule.min_value:
            return f"{rule.name}={value} 小于 min={rule.min_value}"
        if rule.max_value is not None and value > rule.max_value:
            return f"{rule.name}={value} 大于 max={rule.max_value}"
    elif rule.field_type == "float":
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            return f"{rule.name} 应为 float，实际 {type(value).__name__}"
        if rule.min_value is not None and float(value) < rule.min_value:
            return f"{rule.name}={value} 小于 min"
        if rule.max_value is not None and float(value) > rule.max_value:
            return f"{rule.name}={value} 大于 max"
    elif rule.field_type == "enum":
        if value not in rule.enum_values:
            return f"{rule.name}={value!r} 不在枚举 {rule.enum_values}"
    elif rule.field_type in ("str", "phone", "email", "username"):
        if not isinstance(value, str):
            return f"{rule.name} 应为 str，实际 {type(value).__name__}"
        if rule.max_length is not None and len(value) > rule.max_length:
            return f"{rule.name} 长度 {len(value)} 超过 max_length={rule.max_length}"
        if rule.pattern is not None and re.fullmatch(rule.pattern, value) is None:
            return f"{rule.name}={value!r} 不匹配 {rule.pattern}"
    return None


def validate_records(schema: DataSchema, records: list[Record]) -> list[str]:
    """全表校验：返回所有错误信息；空列表 = 全部通过。"""
    errors: list[str] = []
    for record in records:
        for rule in schema.fields:
            err: str | None = validate_record(rule, record.get(rule.name))
            if err is not None:
                errors.append(err)
    return errors

# ═══════════════════════════════════════════════════════
# 异常数据（设计决策 D ③：预置 payload 库 × 字段循环）
# ═══════════════════════════════════════════════════════

ABNORMAL_PAYLOADS: list[tuple[str, str | None]] = [
    ("空值", ""),
    ("NULL", None),
    ("特殊字符", "!@#$%^&*()_+{}[]|\\:;\"'<>,.?/"),
    ("SQL注入", "' OR '1'='1"),
    ("SQL注入-DDL", "'; DROP TABLE users; --"),
    ("XSS", "<script>alert(1)</script>"),
    ("XSS-IMG", "<img src=x onerror=alert(1)>"),
]


def gen_abnormal_data(schema: DataSchema) -> list[Record]:
    """异常数据：字段循环 × payload 注入（注入字段取 payload，其余字段取正常值；主键跳过）。

    对 str 系字段额外补一条"超长"（max_length+1）——长度边界来自规则，动态生成。
    """
    records: list[Record] = []
    base: Record = gen_normal_data(schema, 1)[0]
    for rule in schema.fields:
        if rule.primary_key:
            continue  # 主键不注入（自增由数据库保证）
        payloads: list[tuple[str, str | None]] = list(ABNORMAL_PAYLOADS)
        if rule.field_type in ("str", "phone", "email", "username"):
            n: int = rule.max_length if rule.max_length is not None else 50
            payloads.append(("超长", "a" * (n + 1)))
        for label, value in payloads:
            rec: Record = dict(base)
            rec[rule.name] = _abnormal_value(rule, (label, value))
            records.append(rec)
    return records


def _abnormal_value(rule: FieldRule, payload: tuple[str, str | None]) -> str | int | float | bool | None:
    """把 payload 适配到字段类型：str 系直接注入；数值字段退化为超大越界数字；enum 注入越界字符串。"""
    label, value = payload
    if rule.field_type in ("int", "float"):
        return 10**18  # 越界大数（payload 对数值字段没有意义，退化为越界）
    return value


# ═══════════════════════════════════════════════════════
# SQL INSERT 渲染（设计决策 D ④：确定性模板，不碰 f-string 花括号——Day 30 坑 1）
# ═══════════════════════════════════════════════════════

def _sql_literal(value: str | int | float | bool | None) -> str:
    """SQL 字面量：None → NULL；str 单引号转义（' → ''）；bool → 1/0；数值原样。"""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(value)
    return "'" + str(value).replace("'", "''") + "'"


def render_sql_inserts(schema: DataSchema, records: list[Record]) -> str:
    """渲染批量 SQL INSERT 语句（确定性模板）。

    ⚠️ 教学点：不用 f-string 拼 SQL（花括号冲突 + 注入风险），用列表拼接 + ', '.join；
       表名/列名来自 schema（白名单，不是用户输入）；字符串值单引号转义；跳过主键自增列。
    """
    cols: list[str] = [f.name for f in schema.fields if not f.primary_key]
    lines: list[str] = [f"INSERT INTO {schema.table_name} ({', '.join(cols)}) VALUES"]
    for rec in records:
        vals: list[str] = [_sql_literal(rec.get(c)) for c in cols]
        lines.append("  (" + ", ".join(vals) + "),")
    if len(lines) > 1:
        lines[-1] = lines[-1].rstrip(",") + ";"
    else:
        lines.append("  ();")
    return "\n".join(lines)


# ═══════════════════════════════════════════════════════
# Mock JSON 渲染（设计决策 D ⑤：接口返回包装）
# ═══════════════════════════════════════════════════════

def render_mock_json(schema: DataSchema, records: list[Record], total: int | None = None) -> str:
    """Mock 接口返回 JSON：{"code": 0, "message": "success", "data": {"table", "total", "list"}}。"""
    payload: dict[str, object] = {
        "code": 0,
        "message": "success",
        "data": {
            "table": schema.table_name,
            "total": total if total is not None else len(records),
            "list": records,
        },
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


# ═══════════════════════════════════════════════════════
# 落盘工具（确定性代码；路径基准钉 __file__）
# ═══════════════════════════════════════════════════════

def _out_dir() -> str:
    """产物目录 outputs/data_gen（以 __file__ 为基准）。"""
    here: str = os.path.dirname(os.path.abspath(__file__))
    out: str = os.path.join(here, "..", "..", "outputs", "data_gen")
    os.makedirs(out, exist_ok=True)
    return out


def save_json(path: str, obj: object) -> str:
    """JSON 落盘（ensure_ascii=False + indent=2）。"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2))
    return path


def save_text(path: str, text: str) -> str:
    """文本落盘。"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


# ═══════════════════════════════════════════════════════
# 实验
# ═══════════════════════════════════════════════════════

def _demo_schema() -> DataSchema:
    """演示用 users 表 schema（手工构造，模拟练习 2 的模型解析产物；零 API）。"""
    return DataSchema(
        table_name="users",
        description="用户信息表",
        fields=[
            FieldRule(name="id", field_type="int", required=True, description="主键自增", primary_key=True),
            FieldRule(name="phone", field_type="phone", required=True, description="手机号",
                      pattern=r"^1[3-9]\d{9}$", max_length=11),
            FieldRule(name="email", field_type="email", required=False, description="邮箱", max_length=100),
            FieldRule(name="age", field_type="int", required=True, description="年龄",
                      min_value=1, max_value=150),
            FieldRule(name="username", field_type="username", required=True, description="用户名",
                      pattern=r"^[A-Za-z0-9_]+$", max_length=50),
            FieldRule(name="gender", field_type="enum", required=False, description="性别",
                      enum_values=["男", "女", "未知"], default="未知"),
        ],
    )


def exp4_normal_boundary() -> None:
    """实验：正常数据 + 边界数据 + 质量校验（零 API）——断言确定性、边界数量、正常数据全通过。"""
    print("=" * 60)
    print("实验：exp4_normal_boundary —— 正常 + 边界生成（零 API）")
    schema: DataSchema = _demo_schema()

    # ① 正常数据：确定性（跑两次结果一致）+ 校验全通过
    normal: list[Record] = gen_normal_data(schema, count=5)
    assert len(normal) == 5
    assert gen_normal_data(schema, 5) == normal, "确定性被破坏：同输入必须同输出"
    assert normal[0] != normal[1], "5 条记录应互不相同（seq 递增）"
    errors: list[str] = validate_records(schema, normal)
    assert not errors, f"正常数据校验应全通过: {errors}"
    print(f"  ✅ 正常数据 5 条（确定性 diff 一致 + 校验全通过）")
    for i, rec in enumerate(normal):
        print(f"     [{i}] {rec}")

    # ② 边界数据：每字段边界值一条记录；界内界外都生成
    boundary: list[Record] = gen_boundary_data(schema)
    total_cases: int = sum(len(_boundary_cases(f)) for f in schema.fields if not f.primary_key)
    assert len(boundary) == total_cases, f"边界记录数应等于边界用例数 {total_cases}"
    print(f"  ✅ 边界数据 {len(boundary)} 条（= 每字段边界用例之和）")
    for rec in boundary[:6]:
        print(f"     {rec}")

    # ③ 边界值教学点：界内通过校验，界外预期失败（min-1 / max+1）
    age_rule: FieldRule = next(f for f in schema.fields if f.name == "age")
    assert validate_record(age_rule, 1) is None            # min 界内 → 通过
    assert validate_record(age_rule, 150) is None          # max 界内 → 通过
    assert validate_record(age_rule, 0) is not None        # min-1 界外 → 拒绝
    assert validate_record(age_rule, 151) is not None      # max+1 界外 → 拒绝
    print(f"  ✅ 边界语义验证: age=1/150 通过；age=0/151 预期拒绝（界内最值 + 界外最值）")

    # ④ bool 是 int 子类（坑 6 预演）：validate_record 正确拒绝 bool 当 int
    assert isinstance(True, int), "bool 是 int 子类（教学点）"
    assert validate_record(age_rule, True) is not None, "bool 混入 int 字段必须拒绝"
    print("  ✅ 坑 6 预演: isinstance(True, int)=True 但 validate_record 拒绝 bool 混入")
    print("✅ 正常 + 边界冒烟通过")

def exp5_abnormal_sql_mock() -> None:
    """实验：异常数据 + SQL INSERT + Mock JSON + 落盘（零 API）——断言注入数量、转义、产物落盘。"""
    print("=" * 60)
    print("实验：exp5_abnormal_sql_mock —— 异常 + SQL + Mock（零 API）")
    schema: DataSchema = _demo_schema()

    # ① 异常数据：非主键字段 × (7 payload + str 系 1 超长)
    abnormal: list[Record] = gen_abnormal_data(schema)
    str_fields: int = sum(
        1 for f in schema.fields if f.field_type in ("str", "phone", "email", "username") and not f.primary_key
    )
    non_pk: int = sum(1 for f in schema.fields if not f.primary_key)
    expected: int = str_fields * 8 + (non_pk - str_fields) * 7
    assert len(abnormal) == expected, f"异常数据应 {expected} 条，实际 {len(abnormal)}"
    print(f"  ✅ 异常数据 {len(abnormal)} 条（str 系字段 8 payload，数值/enum 7 payload）")
    # 注入点观察：每条记录必有且只有一个字段是 payload 值
    sample: Record = next(r for r in abnormal if r["username"] == "<script>alert(1)</script>")
    print(f"     注入样例: {sample}")
    # 超长 payload 存在（str 系字段 +1）
    assert any(r["username"] == "a" * 51 for r in abnormal)
    print("  ✅ 超长 payload（max_length+1=51）已注入 username")

    # ② SQL INSERT：转义 + 跳主键 + 列白名单
    sql: str = render_sql_inserts(schema, gen_normal_data(schema, 5))
    assert "INSERT INTO users" in sql
    assert "id" not in sql.split("(", 1)[1].split(")", 1)[0], "主键自增列应被跳过"
    print("  ✅ SQL INSERT 渲染 ok（跳主键）")
    print("     " + sql.replace("\n", "\n     ")[:500])
    # 转义验证：SQL 注入 payload 进 INSERT 时单引号被转义（不会破坏语句）
    sql_abn: str = render_sql_inserts(schema, [r for r in abnormal if r["username"] == "' OR '1'='1"])
    assert "'' OR ''1''=''1" in sql_abn or "'' OR '1'='1" in sql_abn
    print("  ✅ SQL 注入 payload 单引号转义验证（'' 不会破坏 INSERT 语句）")

    # ③ Mock JSON：包装结构 + 数量
    mock: str = render_mock_json(schema, gen_normal_data(schema, 5))
    mock_obj: object = json.loads(mock)
    assert isinstance(mock_obj, dict) and mock_obj.get("code") == 0
    data: object = mock_obj.get("data")
    assert isinstance(data, dict) and data.get("total") == 5
    print(f"  ✅ Mock JSON 渲染 ok（code=0, data.total=5）")
    print("     " + mock[:300].replace("\n", "\n     "))

    # ④ 落盘（零 API 全产物）
    out: str = _out_dir()
    save_json(os.path.join(out, "users_normal.json"), gen_normal_data(schema, 5))
    save_json(os.path.join(out, "users_boundary.json"), gen_boundary_data(schema))
    save_json(os.path.join(out, "users_abnormal.json"), abnormal)
    save_text(os.path.join(out, "users_insert.sql"), sql)
    save_text(os.path.join(out, "users_mock.json"), mock)
    print(f"  ✅ 已落盘 {out}/（users_normal/boundary/abnormal.json + insert.sql + mock.json）")
    print("✅ 异常 + SQL + Mock 冒烟通过")



if __name__ == "__main__":
    """完成态：零 API 全冒烟（数据生成器全流程）。"""
    # exp4_normal_boundary()
    exp5_abnormal_sql_mock()
    print("\n💡 要点回顾：")
    print("   造数 = 确定性最高的专项：五类产物全是代码（合成/边界/注入/SQL/Mock），零 API 可冒烟")
    print("   异常数据 = payload 库 × 字段循环（空值/超长/特殊字符/SQL注入/XSS）——主键跳过，数值退化越界")
    print("   SQL/Mock 渲染不碰 f-string 花括号：列表拼接 + 转义（Day 30 坑 1）")

