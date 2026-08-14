# Day 21 学习笔记：智能测试知识库 —— 命令行交互界面

## 日期
2026-08-11

## 今日成果
- [ ] KnowledgeIndexerV2：索引持久化（persist_directory 落盘 + 重启加载 + force 重建防重复）
- [ ] CLI 骨架：argparse 子命令（import / query / recommend / analyze-bug）+ --type/--k 参数化
- [ ] 对话式问答：手动记忆模式（InMemoryChatMessageHistory，RunnableWithMessageHistory 的 2026 替代）
- [ ] 交互式 chat + 会话历史持久化（sessions.json，重启不丢）
- [ ] Windows UTF-8 输出兜底（sys.stdout.reconfigure）

## 核心概念

### 1. 索引持久化（KnowledgeIndexerV2）
```python
# 建库：参数名是 embedding
Chroma.from_documents(documents=..., embedding=..., persist_directory=...)
# 加载：参数名是 embedding_function（不同！）
Chroma(persist_directory=..., embedding_function=..., collection_name=...)

# force 重建必须先删旧集合，否则 from_documents 是【追加】→ 记录数翻倍
tmp = Chroma(persist_directory=persist, embedding_function=..., collection_name=...)
tmp._client.delete_collection(name=...)  # type: ignore[attr-defined]
# ⚠️ chromadb 1.5.x：Collection.delete() 无参会抛 ValueError，必须给 ids/where
