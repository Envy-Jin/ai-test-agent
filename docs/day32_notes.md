# Day 32 学习笔记：第 5 周第四天 —— 测试数据生成器（字段规则 → 正常/边界/异常 + SQL + Mock JSON）

## 日期
2026-09-01

## 今日成果
- [ ] `docs/schemas/users.md`：自然语言字段规则样本（走模型解析）+ `docs/schemas/orders.json`：机器可读样本（走确定性解析）
- [ ] `day32_data_schema.py`：FieldRule/DataSchema 分级 Schema（FieldType Literal 10 类）+ 双输入加载分派（.json 直读 / .md 走模型）+ 解析 Chain（with_fallbacks）+ 质检 validate_schema + 概览渲染
- [ ] `day32_data_generator.py`：确定性生成引擎——正常值合成器（按类型/格式/范围，同 seq 同值）+ 边界推导（界内最值+界外最值）+ 异常 payload 库（空值/超长/特殊字符/SQL注入/XSS）+ SQL INSERT 渲染（转义+跳主键）+ Mock JSON 包装 + 质量校验
- [ ] `day32_run_pipeline.py`：双输入端到端闭环（users.md 模型 + orders.json 代码 → 同一生成引擎）+ 模型 vs 代码对照实验（分界线实证）
- [ ] `day32_pyright_pitfalls.py`：6 个新坑演示 + 模块零 API 自检
- [ ] `outputs/data_gen/`：users/orders 的 normal/boundary/abnormal.json + insert.sql + mock.json + generation_report.md
- [ ] 联网确认：faker 最新 40.x（2026-07，Python≥3.10，MIT，Faker.seed() 可复现）——今天零新增依赖不装，真实项目增强路径

## 核心概念

### 1. 分层第四次落地：模型出语义（FieldSchema），代码管工程（确定性合成）——造数是确定性最高的专项
```python
schema = parse_schema_text(users_md_text)   # 模型：自然语言字段规则 → DataSchema（唯一非确定环节）
normal = gen_normal_data(schema, 5)          # 代码：合成合理值（同 seq 同值，可 diff）
boundary = gen_boundary_data(schema)         # 代码：min/max/min-1/max+1（界内+界外）
abnormal = gen_abnormal_data(schema)         # 代码：payload 库 × 字段循环
sql = render_sql_inserts(schema, normal)     # 代码：INSERT 模板（转义 + 跳主键）
mock = render_mock_json(schema, normal)      # 代码：接口返回包装
# 五类产物全部零 API 可冒烟——造数不需要模型
