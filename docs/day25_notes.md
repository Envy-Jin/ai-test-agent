# Day 25 学习笔记：LangSmith 调试 + 错误处理

## 日期
2026-08-20

## 今日成果
- [ ] LangSmith 账号注册 + API Key（lsv2_pt_xxx，Settings → API Keys）
- [ ] `day25_langsmith_tracing.py`：零侵入追踪 Day 24 Agent，LangSmith UI 观察调用树
- [ ] `day25_error_handling.py`：ModelRetry + ModelFallback + ToolRetry/ToolError 组合 + recursion_limit
- [ ] `day25_test_agent_v2.py`：完整 Agent v2（可观测 + 容错 + 结构化输出 + 5 工具）
- [ ] `day25_pyright_pitfalls.py`：5 个新坑位
- [ ] 实操发现：ModelFallbackMiddleware 字符串必须带 provider 前缀；create_agent 无 recursion_limit 参数

## 核心概念

### 1. LangSmith 零侵入追踪（2026 新 API）
```python
# .env（必须在 import langchain 之前 load_dotenv！）
LANGCHAIN_TRACING_V2=true          # 字符串 "true"，不是布尔 True
LANGSMITH_API_KEY=lsv2_pt_xxx      # 新标准名；LANGCHAIN_API_KEY 是旧别名
LANGSMITH_PROJECT=test-agent       # LANGCHAIN_PROJECT 是旧别名

# 代码顶部固定顺序：os/sys → load_dotenv() → 然后才 import langchain
from dotenv import load_dotenv
load_dotenv()  # ⚠️ 必须在 langchain import 之前，否则追踪静默失效
