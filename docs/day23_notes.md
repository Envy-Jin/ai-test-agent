# Day 23 学习笔记：自定义 Tool 定义

## 日期
2026-08-17

## 今日成果
- [ ] StructuredTool.from_function：已有函数 → 工具壳（自定义 name/description/args_schema）
- [ ] Annotated[类型, "说明"]：参数级说明书（模型填参更准）
- [ ] 三层降级阶梯：Pydantic 校验 → 工具内错误文本 → ToolErrorMiddleware（2026 新 API）
- [ ] parse_docstring 的坑：Args: 前必须空行，否则装饰时抛 ValueError
- [ ] 测试用例生成工具箱：generate_test_cases / run_api_test / analyze_bug_report / kb_search
- [ ] 组装 4 工具 Agent 雏形（备 Day 24）

## 核心概念

### 1. 三种工具定义方式
```python
# ① @tool 装饰器（Day 22）：新写小函数，最常用
@tool
def foo(x: str) -> str: ...

# ② StructuredTool.from_function：已有函数套壳 + 改造
tool = StructuredTool.from_function(
    func=existing_fn,
    name="...",              # 覆盖工具名
    description="...",       # 覆盖说明书
    args_schema=SomePydanticModel,  # 参数结构 + 免费校验
)

# ③ Annotated 参数说明：参数级说明书
@tool
def run_api_test(
    url: Annotated[str, "接口地址"],
    timeout: Annotated[int, "超时秒数"] = 10,
) -> str: ...
