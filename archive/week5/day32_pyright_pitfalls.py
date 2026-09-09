"""
Day 32 练习 6：Pyright 避坑演示 + 今日模块零 API 自检

坑 1：Literal 枚举分派——_synth_value 按 rule.field_type 的 if 链分派，
      分派后 FieldType 收窄为具体 Literal，字段属性（min_value 等）正常访问
坑 2：int|float|None 联合运算——boundary 计算必须 is not None 检查再运算（pyright 防止 None 参与算术）
坑 3：dict[str, object] 收窄——json.loads 返回 Any→object 收窄 dict；mock 的 data 逐层 isinstance
坑 4：SQL/Mock 模板拼接不碰 f-string 花括号——列表拼接 + ', '.join（Day 30 坑 1 延续）
坑 5：生成记录显式类型注解——Record = dict[str, str|int|float|bool|None]
      （不写注解 → pyright 推断为 dict[str, object] → 校验/SQL 渲染处处收窄）
坑 6：bool 是 int 子类——isinstance(True, int) == True → 校验 int 必须先排除 bool

用法：
  python day32_pyright_pitfalls.py   # 零 API 自检全绿
"""
import json
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from day32_data_generator import (
    ABNORMAL_PAYLOADS,
    gen_abnormal_data,
    gen_boundary_data,
    gen_normal_data,
    render_mock_json,
    render_sql_inserts,
    validate_record,
)
from day32_data_schema import (
    DataSchema,
    FieldRule,
    load_schema,
    validate_schema,
)


def exp1_literal_dispatch() -> None:
    """坑 1：Literal 枚举分派（_synth_value 的 if 链；类型安全分派）。"""
    print("=" * 60)
    print("坑 1：Literal 枚举分派")
    r = FieldRule(name="age", field_type="int", required=True, description="年龄",
                  min_value=1, max_value=150)
    # field_type 收窄为 "int" 后，min_value 的 float|None 仍需 is not None 才能算术（坑 2 联动）
    lo: int = int(r.min_value) if r.min_value is not None else 1
    assert lo == 1
    print(f"  ✅ Literal 分派 ok: {r.field_type} → min={lo}")

    # 全 10 类覆盖检查（生成引擎分派完整性）
    from day32_data_schema import FieldType
    import typing
    all_types: list[str] = list(typing.get_args(FieldType))
    assert len(all_types) == 10
    print(f"  ✅ FieldType 全枚举: {all_types}")


def exp2_union_arithmetic() -> None:
    """坑 2：int|float|None 联合运算（is not None 检查后再算术）。"""
    print("=" * 60)
    print("坑 2：int|float|None 联合运算")
    rule = FieldRule(name="x", field_type="int", required=True, description="x")
    lo: int = int(rule.min_value) if rule.min_value is not None else 1  # None 分支给默认
    hi: int = int(rule.max_value) if rule.max_value is not None else lo + 100
    assert lo == 1 and hi == 101
    # 直接对 None 算术会崩（教学点：pyright 会报错，运行时会 TypeError）
    bad = None
    assert not (bad is not None and bad + 1 == 2), "None 参与算术是 bug"
    print(f"  ✅ 联合运算安全: lo={lo} hi={hi}（None → 默认值）")


def exp3_dict_object_narrow() -> None:
    """坑 3：dict[str, object] 逐层收窄（json.loads / mock 的 data）。"""
    print("=" * 60)
    print("坑 3：dict[str, object] 逐层收窄")
    raw: object = json.loads('{"code": 0, "data": {"total": 5, "list": [1, 2]}}')
    assert isinstance(raw, dict), "先收窄外层"
    data: object = raw.get("data")
    assert isinstance(data, dict), "再收窄 data 层"
    total: object = data.get("total")
    assert isinstance(total, int) and total == 5, "取值后再收窄"
    print(f"  ✅ 三层收窄 ok: code={raw.get('code')} total={total}")


def exp4_template_no_fstring() -> None:
    """坑 4：SQL/Mock 模板不碰 f-string 花括号（列表拼接 + join）。"""
    print("=" * 60)
    print("坑 4：模板拼接不碰 f-string 花括号")
    schema = DataSchema(
        table_name="t", description="d",
        fields=[FieldRule(name="name", field_type="str", required=True, description="名字", max_length=10)],
    )
    sql: str = render_sql_inserts(schema, [{"name": "张三'}恶意"}])
    assert "('张三''}恶意')" in sql or "')恶意" in sql  # 花括号原样、单引号转义
    assert "{" not in sql.split("(", 1)[1].split(")", 1)[0], "列清单不应含花括号"
    print(f"  ✅ SQL 渲染花括号安全: {sql.strip()}")


def exp5_record_annotation() -> None:
    """坑 5：生成记录显式类型注解（Record = dict[str, str|int|float|bool|None]）。"""
    print("=" * 60)
    print("坑 5：生成记录显式类型注解")
    schema = DataSchema(
        table_name="t", description="d",
        fields=[FieldRule(name="age", field_type="int", required=True, description="年龄", min_value=1, max_value=150)],
    )
    normal: list[dict[str, str | int | float | bool | None]] = gen_normal_data(schema, 2)
    assert normal[0]["age"] == 1
    assert validate_record(schema.fields[0], normal[0]["age"]) is None
    print(f"  ✅ Record 注解 ok: {normal}（校验/渲染直接消费，无需再收窄）")


def exp6_bool_is_int() -> None:
    """坑 6：bool 是 int 子类——校验 int 必须先排除 bool。"""
    print("=" * 60)
    print("坑 6：bool 是 int 子类")
    assert isinstance(True, int), "教学点：bool 是 int 的子类"
    rule = FieldRule(name="age", field_type="int", required=True, description="年龄", min_value=1, max_value=150)
    assert validate_record(rule, True) is not None, "True 混入 int 字段必须拒绝"
    assert validate_record(rule, 30) is None, "正常 int 通过"
    print(f"  ✅ isinstance(True, int)={isinstance(True, int)} 但 validate_record 拒绝 bool 混入")


def exp7_zero_api_selfcheck() -> None:
    """今日模块零 API 自检：orders.json 确定性路径 → 生成 → 校验 → SQL/Mock 全绿。"""
    print("=" * 60)
    print("零 API 自检：今日模块全流程")
    here: str = os.path.dirname(os.path.abspath(__file__))
    orders_path: str = os.path.join(here, "..", "..", "docs", "schemas", "orders.json")
    schema = load_schema(orders_path)
    assert schema is not None, "orders.json 解析失败"
    v = validate_schema(schema)
    assert not v.has_error, f"orders schema 不应有 ERROR: {[i.message for i in v.issues if i.level == 'ERROR']}"
    normal: list[dict[str, str | int | float | bool | None]] = gen_normal_data(schema, 5)
    from day32_data_generator import validate_records
    assert not validate_records(schema, normal), "正常数据校验应全通过"
    assert len(gen_boundary_data(schema)) > 0 and len(gen_abnormal_data(schema)) > 0
    assert "INSERT INTO orders" in render_sql_inserts(schema, normal)
    mock: object = json.loads(render_mock_json(schema, normal))
    assert isinstance(mock, dict) and mock.get("code") == 0
    assert len(ABNORMAL_PAYLOADS) == 7
    print(f"  ✅ orders.json → 生成 → 校验 → SQL/Mock 全绿（正常 5 条 / 边界 {len(gen_boundary_data(schema))} 条 / 异常 {len(gen_abnormal_data(schema))} 条）")
    print("✅ 零 API 自检通过")


def main() -> None:
    exp1_literal_dispatch()
    exp2_union_arithmetic()
    exp3_dict_object_narrow()
    exp4_template_no_fstring()
    exp5_record_annotation()
    exp6_bool_is_int()
    exp7_zero_api_selfcheck()
    print("\n✅ Day 32 Pyright 避坑演示 + 零 API 自检全部通过")


if __name__ == "__main__":
    main()
