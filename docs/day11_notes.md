# Day 11 学习笔记：多轮对话 + 历史管理

## 日期
2026-07-22

## 今日成果
- [ ] 创建 utils.py（safe_text 工具函数，根治 None 崩溃）
- [ ] 理解单次调用 vs 多轮对话的本质区别
- [ ] 掌握 client.chats.create() 多轮对话 API
- [ ] 深入理解对话历史的结构（types.Content）
- [ ] 掌握多会话管理（SessionManager）
- [ ] 封装健壮的 SafeChat 类（重试 + 兜底）
- [ ] 完成交互式需求分析对话脚本

## 核心概念

### 多轮对话 vs 单次调用
- 单次调用: `client.models.generate_content()`，每次都是新对话
- 多轮对话: `client.chats.create()`，后续对话能看到之前的所有内容

### 对话历史结构
- `chat.get_history()` 返回 `list[types.Content]`
- 每条 Content 有 `role`（"user"/"model"）和 `parts`（类型为 `list[Part] | None`）
- 遍历时用 `safe_parts(msg)` 代替 `msg.parts`，避免 None 崩溃
- Part 可以是 text、inline_data（图片）等

### 历史管理
- 保存: `get_history()` 获取完整列表
- 恢复: 重放关键消息或摘要注入
- 截断: 只保留最近 N 条
- 压缩: 让模型自己总结长历史

### 错误处理
- 所有 `response.text` 统一走 `safe_text()`
- 所有 `content.parts` 统一走 `safe_parts()`
- 流式 chunk 也用 `safe_text()`（和 response 是同一类型）
- 重试用指数退避: 2s → 4s → 8s
- 空结果有兜底消息

### 健壮的返回值
- send() 返回 `str`，永不返回 `None`
- send_stream() 拼接全文后返回 `str`
- 类型安全: 可以放心做字符串操作

## 踩坑记录
（记录今天遇到的问题和解决方法）

### response.text 类型问题已解决
- 所有文件统一 `from utils import safe_text`
- 全文不再出现 `response.text` 直接访问
- 流式输出直接用 `safe_text()`

### content.parts 类型问题已解决
- `msg.parts` 的类型也是 `list[Part] | None`，和 `response.text` 同出一个坑
- 遍历历史消息时用 `safe_parts(msg)` 代替 `msg.parts`
- `safe_parts()` 在 None 时返回空列表，安全遍历

### SessionManager 当前是练习级别，生产化留待后续
- 返回值：当前用 `str`，Day 12 健壮封装时会升级为结构化 `dict`（含状态码 + 数据）
- 持久化：当前只在内存，第3周 LangChain Memory 会覆盖
- 线程安全：当前不考虑，Web 场景是后话
- 回到 Day 12 时可以顺手把 `session_configs` 的 `dict` 改成 `TypedDict`

## 新旧 SDK 关键区别
- 旧版: `model.start_chat(history=[])`
- 新版: `client.chats.create(model="...", config=...)`
- 旧版: `chat.history` (属性)
- 新版: `chat.get_history()` (方法)
- 旧版: 流式用 `chat.send_message(stream=True)`
- 新版: `chat.send_message_stream()`

## 对比 Day 10 的进步
- Day 10: 多模态 + 流式，但每次都是单次调用
- Day 11: 多轮对话，AI 能记住上下文，像真人一样交流
- safe_text 彻底解决了 response.text 的 None 崩溃问题
