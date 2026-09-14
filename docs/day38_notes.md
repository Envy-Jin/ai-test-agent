# Day 38 学习笔记：CLI 命令行界面 + 依赖闭包 + 入口层冷启动瘦身

## 日期
2026-09-11（第 6 周 Day 3）

## 今日成果
- 新建 cli.py：Click 三命令（scan / run / report），对齐 UI 三页签；参数 --scenario/--no-bug-probe/--with-llm/--force/--fail-fast/--stage
- day35_scenario.select_stages：--stage 依赖闭包（wanted → 反向上溯 producer → 按原蓝图顺序返回）
- 入口层冷启动瘦身四处：day35_scenario 执行器 import 进函数 / day33_regression_analyzer langchain+构造懒化 / ui/app.py 类型注解延迟 + run_flow 延迟导入 / utils.py google.genai 注解延迟
- tests/test_day38_cli.py：CliRunner 无头冒烟 7 条全绿
- click 8.4.2（实测已在 venv：streamlit/ddgs 传递依赖）→ 仍显式写进 requirements.txt

## 核心概念
### 1. 入口层最薄 + 重依赖延迟导入
- CLI 每次调用 = 新进程 → 启动开销直接等于体验；--help 必须不 import 任何 dayXX
- UI（长驻）模块级 import 无妨 → 入口形态决定导入策略
### 2. 子集执行 = 闭包不是过滤
- 裸过滤只保证"我要的段在"，闭包保证"它们的输入有生产者"
- 返回必须借原蓝图顺序（原序 = 拓扑序）；set 重排可能把消费者排到生产者前面
### 3. Click 的 pyright 真坑：被装饰的名字不是函数
- type(scan).__name__ == "Command"；直接 scan() 会去解析 sys.argv
- 测试必须走 CliRunner（对照 Day37 的 AppTest：入口层一律"无头驱动"测试）
### 4. exit code 契约
- Click 用法错误 = 2；脚本化调用靠它区分"命令写错"与"程序挂了"
### 5. 运行期校验 vs click.Choice
- Choice 要求导入期候选集 → 会拖慢 --help 且复制场景名单；改用 BadParameter 运行期校验，注册表保持单一来源
### 6. pydantic v2 场景派生（沿用 Day37）
- sc.model_copy(update={"bug_probe": ...})；CLI 与 UI 用同一套派生手法
### 7. 本日踩坑记录
- （按实际填：如 click.__version__ 弃用、GBK、pyright 对 cli.py 的 import 解析等）

## 还存在的问题 / 待办
- [ ] Day 39：单元测试覆盖 + README（含裸 pytest 4 个 collection error 的整理：testpaths/norecursedirs + 失效测试归档）
- [ ] register 场景真跑全链（补 schemas/register.json + bugs/register_bugs.md）—— 周末综合
- [ ] 第二批分层迁移（src/tools、src/rag、src/config.py）按 day36_notes 5.4 纪律穿插
- [ ] 执行层第 6 态 skipped_missing_input（须与 P0 系列同批，会动 ExecStatus Literal / 报告 / 断言）
- [ ] 残留冷启动：pydantic + python-dotenv（≈0.5s）—— 已是必要依赖，不再优化
- [ ] UI 阶段多选（st.multiselect + select_stages）—— 可选延伸
