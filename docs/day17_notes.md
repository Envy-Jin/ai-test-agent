# Day 17 学习笔记：Memory 对话记忆

## 日期
2026-08-02

## 今日成果
- [ ] 理解 Chat History 的本质：消息列表 + add/clear 操作
- [ ] 掌握 RunnableWithMessageHistory 的自动历史管理
- [ ] 使用 MessagesPlaceholder 在 Prompt 中预留历史位置
- [ ] 实现 session_id 多会话隔离
- [ ] 构建 TestAssistant 带记忆的测试助手对话系统

## 核心概念

### 1. Memory 三层抽象

| 层级 | 组件 | 职责 |
|------|------|------|
| 存储层 | `InMemoryChatMessageHistory` | 存消息列表，增删查 |
| 管理层 | `get_session_history` | 按 session_id 取历史 |
| 包装层 | `RunnableWithMessageHistory` | 自动读写历史 |

### 2. Day 15 vs Day 17 多轮对话对比

| 维度 | Day 15（手动管理） | Day 17（Memory 自动） |
|------|-------------------|----------------------|
| 历史管理 | 手动维护 list[Message] | RunnableWithMessageHistory 自动 |
| 多用户隔离 | 手动为每个用户维护 list | store[session_id] 自动隔离 |
| 代码量 | 每次 invoke 都要拼完整消息列表 | 只传 input + config |
| 出错风险 | 容易忘记清空、混入脏数据 | 自动管理，风险低 |

### 3. 关键 API

```python
# Memory 包装
chain_with_memory = RunnableWithMessageHistory(
    base_chain,              # 底层 Chain（prompt | llm | parser）
    get_session_history,      # 回调：按 session_id 取历史
    input_messages_key="input",          # 输入 key
    history_messages_key="chat_history", # 历史占位 key
)

# 调用
config: RunnableConfig = {"configurable": {"session_id": "user_001"}}
result = chain_with_memory.invoke(
    {"input": "用户消息"},
    config=config,
)
