# Day 18 学习笔记：文档加载 + 向量数据库（RAG 基础）

## 日期
2026-08-04

## 今日成果
- [ ] 掌握 Document 对象创建 + 纯 Python 文件加载
- [ ] 理解 RecursiveCharacterTextSplitter 切分策略（chunk_size + chunk_overlap）
- [ ] 掌握 GoogleGenerativeAIEmbeddings / HuggingFaceEmbeddings 文本向量化
- [ ] 学会 ChromaDB 向量存储与检索（内存 + 持久化）
- [ ] 构建 RAGRetriever 完整封装类

## 核心概念

### 1. RAG 两步走

| 阶段 | 步骤 | 工具 |
|------|------|------|
| 离线 Indexing | 加载 → 切分 → 向量化 → 存储 | open() + Document + Splitter + Embeddings + ChromaDB |
| 在线 Querying | 查询向量化 → 语义检索 → 返回结果 | vectorstore.similarity_search() |

### 2. 文档切分参数选择

| 参数 | 推荐值 | 说明 |
|------|--------|------|
| chunk_size | 300-500 | 太小子义断裂，太大检索不准 |
| chunk_overlap | 50-100 | 约为 chunk_size 的 10-20% |

### 3. RAG vs Memory

| 维度 | Memory（Day 17） | RAG（Day 18-19） |
|------|-----------------|-----------------|
| 数据来源 | 当前对话历史 | 外部文档库 |
| 生命周期 | 会话期间 | 持久化 |
| 数据量 | 对话轮次（KB 级） | 文档库（MB-GB 级） |
| 检索方式 | 顺序遍历 | 语义向量检索 |
| 比喻 | 短期记忆 | 长期知识（查书） |

### 4. 关键 API

```python
# 建索引
vectorstore = Chroma.from_documents(
    documents=chunks,
    embedding=embeddings,
    persist_directory="./chroma_db",  # 可选：持久化
)

# 检索
results = vectorstore.similarity_search("查询文本", k=3)

# 带分数检索
results = vectorstore.similarity_search_with_score("查询", k=3)

# 转为检索器
retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
```

### 5. 今日产出
```python
rag = RAGRetriever(docs_dir="docs/requirements")
rag.index()  # 一键建索引
results = rag.search("登录功能的安全要求")  # 语义检索
```

## 踩坑记录

### HuggingFaceEmbeddings 本地运行仍需联网的问题

**现象**：模型已下载到本地缓存、脚本也跑通过一次，但第二次运行（断开 VPN）时仍报：
`WinError 10060 连接尝试失败`，请求 `https://huggingface.co/.../resolve/main/xxx.json`

**原因**：`sentence-transformers` 每次加载模型时，默认会**联网校验**模型文件是否有更新
（发 HEAD 请求检查远程文件的 etag）。网络不通时这个校验失败，直接抛错——
即使模型文件已在本地缓存中。

**解决方法（二选一）**：

- **方案 A：环境变量强制离线**
  ```python
  import os
  os.environ["HF_HUB_OFFLINE"] = "1"
  os.environ["TRANSFORMERS_OFFLINE"] = "1"
  # 再 import / 创建 HuggingFaceEmbeddings
  ```

- **方案 B：构造时指定只用本地文件（推荐，已验证有效）**
  ```python
  embeddings = HuggingFaceEmbeddings(
      model_name="sentence-transformers/all-MiniLM-L6-v2",
      model_kwargs={"local_files_only": True},  # 关键：强制只用本地缓存，不再联网
  )
  ```

**注意**：方案 B 的 `local_files_only=True` 是必须的——否则即使模型已缓存，
sentence-transformers 每次加载仍会尝试联网校验，网络不通就会报错。

## Pyright 避坑总结
1. **metadata.get() 返回 Any** → 显式 `str()` 转换
2. **Chroma.from_documents()** → 用 `Chroma` 类型注解
3. **similarity_search_with_score()** → 返回 `list[tuple[Document, float]]`
4. **chunk_overlap < chunk_size** → 运行时校验
5. **pathlib.glob** → 只写模式不写路径
6. **langchain_core.documents.Document** → 直接构造 + open()，无需额外依赖
7. **GoogleGenerativeAIEmbeddings 不显式传 google_api_key** → Pydantic + Pyright 签名冲突，走 env

## 还存在的问题
- 当前只支持 .txt 文件 → 后续可扩展 PDF/Word/网页
- Embedding API 调用有频率限制 → 大批量需要分批处理
- 检索结果还不能直接喂给 LLM → Day 19 的 RAG Chain 解决

## 第 3 周路线图
- Day 15 ✅ LangChain 入门 + Message 体系
- Day 16 ✅ Prompt Template + LCEL 链式组合
- Day 17 ✅ Memory 对话记忆
- Day 18 ✅ 文档加载 + 向量数据库（RAG 基础）
- Day 19 → RAG Chain 构建（检索 + 生成）
- Day 20-21 → 智能测试知识库项目
