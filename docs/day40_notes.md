# Day 40 学习笔记：性能优化 + 异步调用

## 1. 今天改了什么
| 文件 | 新/改 | 职责 |
|------|------|------|
| src/agent/day40_llm_cache.py | 新 | SQLite 自写 BaseCache（标准库，零新依赖） |
| src/agent/day40_batch.py | 新 | asyncio 批量语义实验（顺序/限流/异常隔离/边界） |
| src/agent/day40_concurrency_lab.py | 新 | 并发接真实链形状的教学原型 |
| src/agent/day31_bug_analyzer.py | 改 | 新增 async 版，**同步版原样保留** |
| cli.py | 改 | 新增 cache 子命令组（stats / clear） |
| .gitignore | 改 | 加 .cache/（缓存是可再生的本地状态） |

## 2. 缓存契约
- 键 = (prompt, llm_string)，两个参数都由 LangChain 自动算好传入，**不自创键**。
- prompt = 完整请求文本；llm_string = 模型参数确定性串（model 名 + temperature 等）。
- 只按 prompt 缓存 = 换模型后拿到**另一个模型**的答案 → 静默正确性 bug（答案看着总是"合理"的）。
- BaseCache 契约：同步 3 个必须实现（lookup/update/clear），异步 3 个有默认实现（alookup/aupdate/aclear）。

## 3. RETURN_VAL_TYPE
- 类型是 list[Generation]，不是 str。
- 存：dumps(list(return_val))；取：loads(row[0], allowed_objects=[Generation])。
- allowed_objects 是显式白名单（安全加固 + 消掉 Beta/PendingDeprecation 警告）。

## 4. 并发的边界
- 赢「等待」不赢「计算」：200 个零延迟任务，串行 0.2ms vs 并发 1.7ms（并发反而慢 7.88x）。
- 一个阻塞调用就退化：time.sleep 版 0.61s vs await 版 0.16s。
- 异步是函数固有属性：RunnableLambda(协程函数) 只能 ainvoke，invoke 直接抛
  TypeError: Cannot invoke a coroutine function synchronously. Use `ainvoke` instead.
  → 所以同步版必须是**另一个函数**。

## 5. 踩坑与判据
- 中文字符串里写直双引号 → SyntaxError；本项目一律用「」。
- .gitignore 缺 .cache/：用 git add -A --dry-run | grep 实测才发现，不能"看一眼觉得有"。
- pyright 退出码：0 干净 / 1 有错 / 3 配置错 / 4 一个文件都没查到（4 不打印 N errors → grep 会假绿）。