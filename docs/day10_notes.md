# Day 10 学习笔记：多模态能力 + 流式输出

## 日期
2026-07-20

## 今日成果
- [ ] 理解多模态输入（文本 + 图片）
- [ ] 掌握 PIL.Image 传入图片的两种方式
- [ ] 掌握 File API 上传大图
- [ ] 实现截图分析器（UI 截图 → 测试用例）
- [ ] 掌握流式输出（`generate_content_stream`）
- [ ] 掌握流式 + 结构化输出的拼接技巧
- [ ] 完成多模态测试助手综合实战

## 核心概念

### 多模态输入
- contents 可以传列表：`[文本, 图片]`
- 图片用 `PIL.Image.open()` 加载
- 两种方式：PIL.Image 内联（小图）/ File API 上传（大图）
- 图片也消耗 Token，建议宽度不超过 1536px

### 流式输出
- `generate_content_stream` 开启流式
- `for chunk in response` 迭代获取
- 每个 chunk.text 是文本片段，实时打印
- 首字延迟小，体验更好

### 流式 + 结构化输出
- 流式时 JSON 是分片返回的
- 必须拼接所有 chunk 的 text，最后再解析
- `full_text += chunk.text` → `model_validate_json(full_text)`

### File API
- `client.files.upload(file=path)` 上传
- 上传后可多次引用，不用重复传
- 适合大图（> 20MB）或重复使用的图片
- 文件有有效期（约 48 小时）

## 踩坑记录
- 在pytest中导入不同包的时候会报错，这个在后续需要继续观察以找到原因及根除方法。
- 在return response.test的时候，有时候会报错，目前有这几个原因:
    1. 函数返回值为str类型，但是response.text为str | None型。
    解决方法：1）修改函数返回值类型，匹配str | None。2）返回文本时添加空文本 return response.text or '' 
    2. 对response.text做切片的时候报错。涉及下标操作（[:]、[0]、.get() 等），str | None 就必须先处理 None。 纯打印、传参、赋值等不涉及下标的情况，None 本身是合法值，Pyright 不报错。
    解决方法：暂时去除切片操作。
    后续仍需继续学习如何处理切片操作。

## 对比 Day 9 的进步
- Day 9：纯文本输入 → 结构化用例
- Day 10：文本 + 图片多模态输入 + 流式输出
- 现在能让 AI「看」截图生成测试用例了！