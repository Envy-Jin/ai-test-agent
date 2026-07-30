# Day 15 学习笔记：LangChain 架构与 Gemini 集成

## 日期
2026-07-30

## 今日成果
- [ ] 安装 langchain / langchain-google-genai / langchain-community
- [ ] 用 ChatGoogleGenerativeAI 完成第一个 LangChain 调用
- [ ] 理解三种 Message 类型（System / Human / AI）
- [ ] 掌握 invoke() 和 stream() 的用法
- [ ] 完成 SDK vs LangChain 深度对比
- [ ] 理解 StrOutputParser 的作用

## 三个核心概念

### 1. LLM 抽象
- LangChain 用一个统一的接口 `invoke()` 封装所有 LLM
- 换模型 = 换一个 LLM 包装类，上层代码不变
- 参数在构造函数中设定，保持调用简洁

### 2. Message 体系
| 类型 | 用途 | 示例 |
|------|------|------|
| SystemMessage | 设定 AI 角色和行为 | "你是测试工程师" |
| HumanMessage | 用户输入 | "生成登录测试用例" |
| AIMessage | AI 的回答（用于历史） | "好的，以下是..." |

### 3. invoke() vs stream()
| 方法 | 行为 | 适用场景 |
|------|------|----------|
| invoke() | 等待全部生成，一次返回 | 批量处理、API 调用 |
| stream() | 边生成边返回 | UI 实时展示 |

## SDK vs LangChain 对比

| 维度 | 纯 SDK | LangChain |
|------|--------|-----------|
| 调用 | generate_content() | invoke() |
| 响应 | GenerateContentResponse | AIMessage |
| 角色 | 手动拼接字符串 | SystemMessage |
| 切换模型 | 改大量代码 | 只改包装类 |
| 管道组合 | 不支持 | LCEL `｜` 操作符 |

## 还存在的问题
- 多轮对话需要手动管理 AIMessage 列表 → Day 17 Memory 解决
- 还没有用到真正的 Chain（管道） → Day 16 LCEL 解决
- invoke() 接受字符串的原理 → Day 16 Prompt Template 解决

## 第 3 周路线图
- Day 15 ✅ LangChain 入门 + Message 体系
- Day 16 → Prompt Template + LCEL 链式组合
- Day 17 → Memory 对话记忆
- Day 18 → 文档加载 + 向量数据库
- Day 19 → RAG Chain 构建
- Day 20-21 → 智能测试知识库项目
