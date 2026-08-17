# Day 22 学习笔记：Agent 基础概念 + 预置工具

## 日期
2026-08-15

## 今日成果
- [ ] @tool 装饰器：docstring（说明书）+ 类型注解（参数 Schema）+ 返回值（Observation）
- [ ] duckduckgo_search 工具：ddgs 包 + 代理 + Ratelimit 容错（替代失效的 DuckDuckGoSearchRun）
- [ ] create_agent 第一个 Agent：输入 {"messages": [...]}，输出 result["messages"][-1]
- [ ] 多工具 Agent（搜索/统计/知识库）+ stream(stream_mode="updates") 流式观察
- [ ] 把 Day 20-21 知识库包装成 kb_search 工具（RAG → Agentic RAG 第一步）

## 核心概念

### 1. Chain vs Agent
