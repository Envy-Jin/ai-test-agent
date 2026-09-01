# Day 31 学习笔记：第 5 周第三天 —— Bug 报告智能分析（结构化分析 + 批量 + 已修复 Bug 归档）

## 日期
2026-08-31

## 今日成果
- [ ] `docs/bugs/login_bugs.md`：输入样本（4 个 Bug：2 待修复 + 2 已修复，与 Day 30 mock 靶场错误码呼应）
- [ ] `day31_bug_analyzer.py`：BugAnalysis 八段式 Schema（学习计划模板 + bug_id/title/status 增强，Literal 枚举 5/4/3 类）+ 批量分割（正则按标题切段，零 API）+ 分析 Chain（with_fallbacks 容错）+ 质检（复现/根因 ERROR 硬检查）+ 批量聚合（sum() 推导）+ 渲染 + 落盘 + 每 Bug 一条入库（doc_type=bug）
- [ ] `day31_bug_archive.py`：淘汰通道——已修复 Bug 归档副本落盘 + Chroma 原生 where $and 多条件过滤删除 + kb_search 验证（归档前搜得到 → 归档后不再返回）
- [ ] `day31_pyright_pitfalls.py`：5 个新坑演示 + 模块零 API 自检
- [ ] `outputs/`：bug_login_batch_report.md、bug_archive/login_bugs_BUG-L02.md 等
- [ ] 联网确认：Chroma where $and 多条件过滤（2026-08-30）；今日零新增依赖

## 核心概念

### 1. 分层第三次落地：模型出语义（BugAnalysis），代码管工程（分割/聚合/归档）
```python
# 模型只产内容：类型/严重度/根因/复现/加固用例/回归范围/预防（八段式，Literal 枚举锁死）
analysis = analyze_bug_report(text)          # prompt | llm.with_fallbacks | with_structured_output(BugAnalysis)
# 代码管工程（全部确定性、零 API 可冒烟）：
sections = split_bug_reports(text)           # ① 分割：正则按 "## BUG-xxx" 标题切段
stats = aggregate_stats(analyses)            # ② 聚合：severity/type/status 分布 sum() 推导
report = validate_bug_analysis(analysis)     # ③ 质检：缺复现/缺根因 → ERROR 硬检查
md = render_bug_markdown(analysis, report)   # ④ 渲染：八段式可评审文档
