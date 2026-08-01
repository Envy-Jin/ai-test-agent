# Day 16 学习笔记：Prompt Template + LCEL 链式组合

## 日期
2026-07-31

## 今日成果
- [ ] 掌握 ChatPromptTemplate 的 from_messages() 和 from_template()
- [ ] 理解 LCEL | 操作符的数据流转机制
- [ ] 用 JsonOutputParser / PydanticOutputParser 解析结构化输出
- [ ] 构建了完整的 TestCaseGenerator（Pydantic 类型安全）
- [ ] 了解 RunnableParallel 并行执行和 RunnablePassthrough 透传

## 核心概念

### 1. ChatPromptTemplate
| 方法 | 用途 | 示例 |
|------|------|------|
| from_messages() | 多角色模板（有 System/Human 区分） | 测试用例生成标准方式 |
| from_template() | 单条消息模板（简单场景） | 翻译、总结等简单任务 |
| partial() | 预填充部分变量（锁定角色） | 所有链条共享同一个 System Prompt |

### 2. LCEL 管道
- `|` 操作符自动衔接组件的输入输出
- `prompt | llm | parser` 是最经典的组合
- 每一步的返回类型取决于最后加的组件：
  - `prompt` → `PromptValue`
  - `prompt | llm` → `AIMessage`
  - `prompt | llm | StrOutputParser` → `str`
  - `prompt | llm | PydanticOutputParser` → `BaseModel 子类实例`

### 3. Parser 对比
| Parser | 返回类型 | Pyright 友好度 | 数据验证 |
|--------|---------|---------------|---------|
| StrOutputParser | str | ★★★★★ | 无 |
| JsonOutputParser | dict（推断为 Any） | ★★ | 无 |
| PydanticOutputParser | 指定 Pydantic 模型 | ★★★★★ | 严格验证 |

### 4. 今日产出链
```python
generator = TestCaseGenerator(model="gemini-3.1-flash-lite")
suite = generator.generate(requirement="...", test_type="综合测试")
# suite 类型为 Optional[TestSuite]，Pyright 能完整推断
