# Day 8 学习笔记：Gemini API 注册与基础调用

## 今日成果
- [x] 注册 Google AI Studio，获取 API Key
- [x] 安装 google-genai SDK（新版）
- [x] 完成第一次 Gemini API 调用
- [x] 探索 response 对象结构
- [x] 封装 GeminiClient 工具类
- [x] 理解 temperature、max_output_tokens、response_mime_type

## 核心概念

### 新版 SDK vs 旧版 SDK
- 旧版：`import google.generativeai as genai` + `genai.configure()` + `GenerativeModel()`
- 新版：`from google import genai` + `genai.Client(api_key=...)`
- 新版调用：`client.models.generate_content(model="...", contents="...")`
- 新版配置：`types.GenerateContentConfig(temperature=..., max_output_tokens=...)`

### temperature 参数
- 范围：0.0 ~ 2.0
- 越低输出越确定、一致（适合代码生成、数据提取）
- 越高输出越随机、有创意（适合头脑风暴、写作）
- **测试用例生成推荐值：0.1 ~ 0.2**

### max_output_tokens
- 控制输出最大长度
- 值太小会导致输出被截断

### response_mime_type
- 设为 `"application/json"` 可强制 JSON 输出
- 自动解析为 Python dict，无需手动清洗 markdown 代码块
- 非常适合结构化数据提取场景

## 踩坑记录
- 最开始学习计划中推荐使用gemini-2.0-flash模型，但是此模型在2026.06.01下线，而gemini-2.5-flash则是不对新用户开放，因此截止到2026.07.15，gemini免费版可用的模型为‘gemini-3.5-flash’，‘gemini-3.1-flash-lite	’。	

## 对 Prompt 工程的初步感受
（为 Day 9 做准备）