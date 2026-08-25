# Day 27 学习笔记：多工具测试 Agent —— 自然语言 → 规划 → 执行 → Markdown 测试报告

## 日期
2026-08-23

## 今日成果
- [ ] `day27_report.py`：TestReport/ReportItem Schema + render_test_report 纯逻辑渲染（统计由代码推导）
- [ ] `day27_mock_api.py`：http.server 本地 mock 登录 API（正常 200 / 短密码 400 / 错误凭据 401 三分支）
- [ ] `day27_multi_tool_agent.py`：Agent v4（v3 底座 + 输出换 TestReport + 模型升级 3.5-flash-lite）
- [ ] `outputs/login_test_report.md`：端到端实战生成的测试报告
- [ ] `day27_pyright_pitfalls.py`：6 个新坑位
- [ ] 联网确认：gemini-3.5-flash-lite 存在（2026-07-21 GA，1M 上下文，免费额度，Agentic 能力强于 3.1-flash-lite）

## 核心概念

### 1. 端到端测试 Agent 的职责分三层
```python
# ① LLM：理解指令、规划、调工具、判 PASS/FAIL、写结论
# ② 工具：kb_search / generate_test_cases / run_api_test / analyze_bug_report
# ③ 确定性代码：统计数字（total/passed/failed）+ Markdown 渲染 + 文件落盘
# 口诀：能让代码算的绝不让模型算，能让 Schema 约束的绝不让模型自由发挥
