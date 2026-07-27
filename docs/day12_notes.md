# Day 12 学习笔记：结构化输出封装 + 错误处理

## 日期
2026-07-23

## 今日成果
- [ ] 掌握从 LLM 输出中提取 JSON 的三种策略（直接解析 / 代码块提取 / 正则兜底）
- [ ] 实现 extract_json / extract_json_with_fallback / validate_json_schema
- [ ] 掌握 RetryConfig 指数退避重试机制
- [ ] 掌握 Python logging 模块的配置和使用
- [ ] 实现 SafeGeminiClient 健壮封装类（五种能力）
- [ ] 实现 SafeChat 的升级版（加入 logging 和 safe_text）
- [ ] 用 SafeGeminiClient 重构测试用例生成器

## 核心概念

### JSON 提取策略
- 策略 1：直接 json.loads（最理想：纯 JSON）
- 策略 2：代码块提取（最常见：```json ... ```）
- 策略 3：正则兜底（最顽固：JSON 混在文字中）
- fallback：所有策略失败时的兜底返回值

### 重试机制
- RetryConfig：max_retries / base_delay / max_delay / jitter
- 指数退避：delay = min(base_delay * 2^attempt, max_delay) + jitter
- should_retry：429/5xx/网络错误→重试，400/401/403→不重试

### logging 模块
- 5 个级别：DEBUG / INFO / WARNING / ERROR / CRITICAL
- 格式：时间 | 级别 | 模块 | 消息
- 输出：终端 + 文件（双通道）
- exc_info=True：自动附加异常堆栈

### SafeGeminiClient 五种能力
| 方法 | 用途 | 返回类型 |
|------|------|----------|
| generate() | 单次文本调用 | str |
| generate_stream() | 流式文本调用 | str |
| generate_json() | JSON 提取调用 | dict |
| generate_schema() | Schema 结构化调用 | Pydantic 对象 或 dict |
| create_chat() | 创建多轮对话 | SafeChat 对象 |

### 统一特性
- 所有方法都带 RetryConfig 重试
- 所有方法都用 safe_text
- 所有方法都有 logging 日志
- 所有方法返回值都是确定类型（不会 None / 不会崩溃）

## 踩坑记录
（记录今天遇到的问题和解决方法）

### 新旧 SDK 配置参数区别
- 旧版: genai.GenerationConfig(temperature=..., response_mime_type=...)
- 新版: types.GenerateContentConfig(temperature=..., response_mime_type=...)
- 新版的配置全部放在 GenerateContentConfig 内，不在 model 级别

### generate_json() vs generate_schema() 的选择
- generate_json(): 通用提取，不强制 Schema，适合灵活输出
- generate_schema(): 精确控制结构，适合需要严格格式的场景
- 推荐：能用 Schema 就用 Schema，extract_json 作为兜底

## 对比 Day 11 的进步
- Day 11: SafeChat 基础版（print 调试 + 简单重试）
- Day 12: SafeGeminiClient 全面版（logging + RetryConfig + 五种能力 + 降级策略）
- 从「能用」升级到「生产级」

## 第 2 周知识体系回顾
