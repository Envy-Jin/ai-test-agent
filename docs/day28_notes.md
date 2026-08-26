# Day 28 学习笔记：多工具测试 Agent 收官 —— 多轮追问 / 失败重测 / 持久化会话 / 周目标验收

## 日期
2026-08-25

## 今日成果
- [ ] `day28_mock_api.py`：双模式 mock 靶场（闭包工厂 make_login_handler(bug_mode)，正常 5 分支 / 埋 Bug 版错误凭据→500）
- [ ] `day28_agent_followup.py`：seed_kb 播种（doc_type=requirement 踩 kb_search 白名单）+ 全 PASS 端到端 + 多轮追问补测 + merge_reports 确定性合并
- [ ] `day28_persist_session.py`：SqliteSaver 跨进程会话（write 写档 / verify 新进程读档）
- [ ] `day28_week4_review.py`：第 4 周能力矩阵验收（8/8 达成）+ 3 个 Pyright 避坑演示
- [ ] `outputs/`：login_test_report.md（3PASS）/ login_test_report_followup.md / login_test_report_merged.md（5 条）/ login_test_report_fail.md（2PASS+1FAIL）/ week4_review.md
- [ ] 联网确认：SqliteSaver 仍官方推荐（from_conn_string 进阶写法）；thread_id 生产要确定性+作用域

## 核心概念

### 1. RAG 即插拔记忆（修端到端失败先想数据问题）
```python
# Day 27 遗留：模型瞎编密码 → 401 FAIL
# 今天：seed_kb() 往知识库塞一条凭据文档（幂等 upsert），不改 Agent 代码 → 3PASS
# 关键：doc_type 必须踩 kb_search 白名单（requirement/bug）——塞数据前先读检索器过滤逻辑
