# Day 9 学习笔记：Prompt 工程核心技巧

## 日期
2026-07-16

## 今日成果
- [ ] 理解为什么 Prompt 工程重要（认知实验）
- [ ] 掌握角色设定（system_instruction）
- [ ] 掌握 Few-Shot 少样本示例
- [ ] 掌握思维链 Chain of Thought
- [ ] 掌握结构化输出（Pydantic + response_schema）
- [ ] 掌握迭代优化
- [ ] 完成测试用例生成器综合实战

## 五大技巧总结

### 1. 角色设定 Role Prompting
- 用 system_instruction 设置角色身份
- 角色要具体（年限+专长+行为指令）
- 持续生效，多轮对话不用重复

### 2. Few-Shot 少样本示例
- 给 2~3 个「输入→输出」范例
- 示例覆盖不同类型（正向/边界/异常）
- 示例质量决定输出质量

### 3. 思维链 Chain of Thought
- 显式 CoT：在 Prompt 写明「第1步、第2步…」
- 让 AI 先分析再输出，覆盖度更高
- 适合测试用例生成等复杂推理任务

### 4. 结构化输出 JSON Schema
- Pydantic 模型 + response_schema
- Literal 枚举锁定字段取值范围
- 输出 100% 稳定，可直接当对象消费
- 比 Day 8 的 response_mime_type 更精确

### 5. 迭代优化
- 先跑再改，问题具体化
- 多轮对话追问补充
- 保留 Prompt 版本

## 踩坑记录
 - httpx.ConnectError: [SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol - 先试直接重跑，大概率就好了。如果频繁出现，加上重试逻辑和请求间隔就能稳定解决。

## 对比 Day 8 的进步
- Day 8：能让 AI 输出 JSON，但格式不稳定
- Day 9：能让 AI 输出严格符合 Schema 的结构化数据，可直接使用