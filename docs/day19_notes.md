# Day 19 学习笔记：RAG Chain 构建

## 日期
2026-08-06

## 今日成果
- [ ] 掌握 RunnablePassthrough / format_docs / StrOutputParser 三件套
- [ ] 构建标准 RAG Chain（LCEL 方式，替代废弃的 RetrievalQA）
- [ ] 实现 RAG 测试用例生成器（JsonOutputParser + Pydantic 校验）
- [ ] 掌握 MMR 检索策略、分数阈值过滤、来源追踪
- [ ] 实现对话式 RAG（RunnableWithMessageHistory 包装）

## 核心概念

### 1. RAG Chain 四环节

| 环节 | 组件 | 作用 |
|------|------|------|
| ① 检索+透传 | `{"context": retriever | format_docs, "question": RunnablePassthrough()}` | 准备上下文和问题 |
| ② 填 Prompt | ChatPromptTemplate | 把 context/question 填进模板 |
| ③ LLM 生成 | gemini-3.1-flash-lite | 基于文档生成回答 |
| ④ 解析 | StrOutputParser / JsonOutputParser | 输出 str / dict |

### 2. 两个输出解析器的选择

| 场景 | 解析器 | 输出 |
|------|--------|------|
| 给人看（问答） | StrOutputParser | str |
| 给程序用（结构化） | JsonOutputParser + Pydantic | dict → TestSuite 对象 |

### 3. 检索优化三招

| 优化 | 方法 | 效果 |
|------|------|------|
| 策略 | as_retriever(search_type="mmr") | 结果多样，避免重复 |
| 过滤 | k=6 再按 distance 阈值过滤 | 只留高质量片段 |
| 溯源 | 把文件名列表塞进 Prompt | 回答可核对出处 |

### 4. 对话式 RAG 组合（Day 17 + Day 19）

```python
conversational_rag = RunnableWithMessageHistory(
    rag_chain,                      # 适配 dict 输入的 RAG 链（assign 从 dict 取 question）
    get_session_history,            # dict[session_id] -> 历史
    input_messages_key="question",
    history_messages_key="chat_history",
)
