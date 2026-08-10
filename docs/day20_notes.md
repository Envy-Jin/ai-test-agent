# Day 20 学习笔记：智能测试知识库 —— 核心引擎

## 日期
2026-08-09

## 今日成果
- [ ] KnowledgeLoader：三类文档（需求/用例/Bug）批量导入 + doc_type 元数据
- [ ] RAGRetriever 并发安全改造（Day 19 方案 3）：index() 加锁 + 离线/在线分离
- [ ] KnowledgeIndexer：类型感知检索（Chroma filter）+ 相似用例推荐（带分数）
- [ ] 问答 Chain（StrOutputParser + 来源标注）
- [ ] Bug 分析 Chain（JsonOutputParser + Pydantic）

## 核心概念

### 1. 元数据体系三件套
| 字段 | 示例 | 用途 |
|------|------|------|
| source | 文件绝对路径 | 溯源 |
| doc_type | requirement / test_case / bug | 类型过滤 |
| category | login / checkout | 细粒度分类（可选） |

### 2. 并发安全改造（Day 19 方案 3）
```python
class RAGRetrieverV2:
    def __init__(...):
        self._lock = threading.Lock()
        self._vectorstore: Optional[Chroma] = None

    def index(self, force: bool = False) -> int:
        with self._lock:          # ① 加锁
            if self._vectorstore is not None and not force:
                return ...        # 幂等跳过
            ...                   # 真正建索引（临界区内唯一执行）

    def get_retriever(self, ...):  # ② 在线路径
        vs = self._vectorstore
        if vs is None:
            raise RuntimeError("请先调用 index()")   # 绝不隐式建索引
        return vs.as_retriever(...)