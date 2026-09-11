# Day 37 学习笔记：Streamlit Web 界面 + 执行档位 + 接口收口

## 日期
2026-09-09（第 6 周 Day 2）

## 今日成果
- 落地执行档位 ScenarioConfig.bug_probe: bool = True（默认开 → Day35 契约断言不破；关 → 摘 S7 + S8 报告输入自适应）
- run_flow 加 blueprint: list[StageSpec] | None = None 入参（None 兜底模块级 BLUEPRINT，向后兼容；UI/CLI 多场景显式传蓝图）
- 新建 ui/app.py（薄 UI 层：侧边栏场景+档位 / 三页签盘点·执行·产物；页面加载零 API，run_flow 挂按钮 + session_state）
- tests/test_day37_app.py：AppTest 无头冒烟 3 条全绿（渲染无异常 / bug_probe 默认勾选 / 场景下拉两选项）
- streamlit 1.62.0（联网核实：Python>=3.10，与 venv 3.12.10 兼容）

## 核心概念
### 1. 第 4 层（入口层）：UI 只调不写
- 验收：app.py 里没有业务 for 循环；表格/报告全委托 day34/35 资产
### 2. 执行档位 = 数据不是按钮
- bug_probe 进 ScenarioConfig：S6 永远在；S7 条件注入；S8 报告输入自适应（防悬空断链）
- 默认 True = 与旧蓝图逐字一致 → 契约等价断言安全网不动
### 3. 显式优于全局（run_flow blueprint 入参）
- 全局覆盖三宗罪：忘覆盖=静默跑错场景 / 不可重入 / 多入口互踩
- 默认 None 兜底全局 = 向后兼容，存量调用零改动
### 4. Streamlit rerun 模型
- 任何交互 = 整脚本重跑 → 昂贵动作挂按钮 + 结果进 st.session_state
- AppTest（streamlit.testing.v1）无头测试：不起浏览器、可模拟点击/勾选、断言 session_state
### 5. 双路径一致：sys.path（运行时）与 pyright extraPaths（静态）
- ui/app.py 平铺裸 import 资产 → 运行时 sys.path 注入 src/agent + pyproject extraPaths 加 "src/agent"
### 6. pydantic v2 场景派生：sc.model_copy(update={"bug_probe": ...})
- 不改全局场景常量，派生变体给本次执行（Day35 实测 model_copy 浅拷贝语义）
### 7. 本日踩坑记录
- （按实际填：如 AppTest label 断言、GBK 输出、streamlit 安装代理等）

## 还存在的问题 / 待办
- [ ] Day 38 CLI：--no-bug-probe / --scenario 参数（复用 run_flow 显式蓝图）
- [ ] register 场景真跑全链（资产补齐 schemas/register.json + bugs/register_bugs.md）—— 周末综合
- [ ] 第二批分层迁移（src/tools、src/rag、src/config.py）按 day36_notes 5.4 纪律穿插
