# Day 34 学习笔记：第 5 周周末综合训练（上）—— 测试全流程 Agent：五专项贯通 + 编排层

## 日期
2026-09-03

## 今日成果
- [ ] 流程蓝图：9 段 StageSpec（输入/输出契约 + llm|code|manual 三态），全零 API 盘点
- [ ] 资产盘点：五专项产物回放（S3/S4/S5/S9 reused）；S1 缺口浮出（login 需求从未出产物）
- [ ] 编排器：三态执行 + 断点续跑（产物在 → reused）+ 失败隔离（--fail-fast 才中断）
- [ ] 执行双回路：mock 正常版 7/7 全绿 vs 埋 Bug 版抓到缺陷（同一套用例只切 bug_mode）
- [ ] 执行报告：JUnit → summarize/find_defects（day33 纯函数）→ Markdown + TC 反查
- [ ] flow_report.json/.md：每段 状态/耗时/产物 sha256 指纹（可审计）
- [ ] 补缺口：S1 真 API 补跑（login_requirement.md → requirement_login_analysis.*）
- [ ] 确定性验证：S4 --force 重跑两次指纹一致（代码段零漂移，模型段才需评审门）

## 核心概念
### 1. 综合 = 编排不是重写（三层分离）
# 蓝图(做什么)/实现(怎么做,在 day29-33)/执行器(怎么调度)——编排器不碰业务逻辑
# 黑盒交接：段与段只认"输入文件 → 输出文件"，实现可换（模型↔规则）而流程不动

### 2. 三态执行 = 分界思想在流程层
# llm 段（语义，真 API）→ 显式 --with-llm 才跑，否则 skipped_needs_api
# code 段（确定性工程）→ 全自动；manual 段（评审门）→ 永远占位等人
# 口诀：代码段自动跑，模型段显式开，人工段永远占位

### 3. 断点续跑 = 流程级幂等
# 产物在且非空 → reused（不重跑）；--force 才重跑
# 空文件=失败产物（getsize>0 双检）——断点续跑不能把坏产物当好产物
# 指纹 sha256：确定性段重跑前后一致 = "同输入同输出"的流程级证据

### 4. 缺口清单 = 周末任务清单
# 盘点先于动工：reused/run_ready/needs_api/manual_pending 一目了然
# 今天补了 S1（需求段），全链闭合只剩 S2 评审门 → Day 35

### 5. 编排器踩坑记录
# subprocess text=True 拿 str；CompletedProcess[str] 显式泛型
# hashlib 只收 bytes（rb 读）；argparse Namespace 是 Any → 手写 flag 解析
# Literal 显式 ==；exists & size>0 双检防"空文件当产物"

## 还存在的问题 / 待办
- S2 两段式评审门（exp_generate → exp_seed_approved → upsert 硬门禁）→ Day 35
- 公共工具抽取到 src/agent/utils.py（方案 B：day32_run_pipeline 从 utils import）→ Day 35
- 执行缺陷 → 自动生成 Bug 报告 → Day 31 分析：把 S6/S7 失败接上 S9（可选深水区）
- 双实现切换实验：把 S3/S9 的模型实现换"规则/人读 JSON"实现，验证流程零改动
- flow 层回放的是"既有产物"——产物过期管理（版本化/时间戳）留真实工程再议
- 批量串行（Day 31）→ Day 40 asyncio 统一解决（沿用）
