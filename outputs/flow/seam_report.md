# Day 41 接缝报告（端到端跑通 register 的前置作业）

> 由 `day41_seam_probe.py` 自动生成（零 API）：三项探测全部是**静态可断言**的，
> 不必先跑一次端到端就能知道哪里会坏。

## 一、产物路径冲突（8 处）

两场景声明同一个输出文件 → 后跑的静默覆盖先跑的。

- ❌ outputs/data_gen/orders_normal.json  ← login:S5_test_data 与 register:S5_test_data
- ❌ outputs/data_gen/users_normal.json  ← login:S5_test_data 与 register:S5_test_data
- ❌ outputs/flow/exec_report_bug.md  ← login:S8_exec_report 与 register:S8_exec_report
- ❌ outputs/flow/exec_report_normal.md  ← login:S8_exec_report 与 register:S8_exec_report
- ❌ outputs/flow/junit_bug.xml  ← login:S7_execute_bug 与 register:S7_execute_bug
- ❌ outputs/flow/junit_normal.xml  ← login:S6_execute_normal 与 register:S6_execute_normal
- ❌ outputs/generated_tests/conftest.py  ← login:S4_test_codegen 与 register:S4_test_codegen
- ❌ outputs/generated_tests/test_api_suite.py  ← login:S4_test_codegen 与 register:S4_test_codegen

## 二、mock 端口与接口文档不同源（1 处）

生成的套件打文档里的地址，mock 却监听蓝图里的端口 → 一片 404 却仍判 run_ok。

- ❌ register：接口文档端口 8766 ≠ 蓝图 mock_port 8767

## 三、段性质与输入路径脱节（2 处）

kind 是「这一段的输入走模型还是走代码」的声明，随场景资产而变，不是段固有属性。

- ❌ [register] S3_api_plan：kind=llm 但输入全是机器可读文件（.json）→ 实际走代码，白等 --with-llm
- ❌ [register] S5_test_data：kind=llm 但输入全是机器可读文件（.json）→ 实际走代码，白等 --with-llm

## 修复去向

| 探测 | 修在哪 |
|------|--------|
| 一 · 产物冲突 | 步骤 4.1 蓝图工厂加场景命名空间 |
| 二 · 端口不同源 | 步骤 4.6 改接口文档 + 步骤 4.1 加同源契约校验 |
| 三 · kind 脱节 | 步骤 4.1 按资产扩展名派生 kind |

> 修完重跑本脚本：三项应全部归零 —— 那就是「可以开跑了」的判据。