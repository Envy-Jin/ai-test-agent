# 第 4 周能力矩阵验收清单

| 周目标 | 交付物 | 验收 | 说明 |
|--------|--------|------|------|
| 理解 ReAct 和 Function Calling 两种 Agent 模式 | day22_agent_multi.py | ✅ | Day 22 预置工具 Agent（day22_agent_multi.py: build_multi_tool_agent） |
| 能自定义 Tool 并注册到 Agent | day23_case_tools.py | ✅ | Day 23 自定义工具（day23_case_tools.py: generate_test_cases） |
| 能用结构化输出拿到 Pydantic 数据 | day24_case_agent.py | ✅ | Day 24 结构化输出（day24_case_agent.py: TestCaseBundle） |
| 能配置 LangSmith 可视化追踪 | day25_langsmith_tracing.py | ✅ | Day 25 LangSmith（day25_langsmith_tracing.py: check_tracing_env） |
| 能给 Agent 加模型级容错（重试+备用模型） | day25_test_agent_v2.py | ✅ | Day 25 容错（day25_test_agent_v2.py: ModelRetryMiddleware） |
| 理解 LangGraph 状态机 + Agent 记忆 | day26_state_graph.py | ✅ | Day 26 状态图（day26_state_graph.py: StateGraph） |
| 自然语言 → 规划 → 调工具 → Markdown 报告 | day27_multi_tool_agent.py | ✅ | Day 27 端到端 v4（day27_multi_tool_agent.py: build_agent_v4） |
| 多轮追问 / 失败重测 / 持久化会话 | day28_persist_session.py | ✅ | Day 28 打磨收官（day28_persist_session.py: SqliteSaver） |

**验收结果：8/8 项达成**
