# Day 30 学习笔记：第 5 周第二天 —— 接口测试辅助：API 文档 → pytest 自动化测试代码

## 日期
2026-08-29

## 今日成果
- [ ] `day30_api_schema.py`：ApiDoc 分级 Schema（ApiParam/ApiEndpoint/ApiDoc，method/Literal 枚举 + 三个期望码 + response_fields）+ 加载分派（.md/.txt 走模型、.json 走确定性 model_validate）+ 解析 Chain（with_fallbacks 容错）+ 三件套计划生成（确定性：正常/参数缺失/越权或错误凭据）+ plan 落盘 json+md
- [ ] `day30_pytest_generator.py`：pytest 代码渲染器（conftest.py fixture + test_api_suite.py 三件套；行列表拼接避开 f-string 花括号地狱；ast.parse 语法校验；parametrize 用 list 字面量）
- [ ] `day30_mock_api.py`：双接口 mock 靶场（POST /api/login 公开 + GET /api/orders 需鉴权；bug_mode 埋 2 缺陷：错误凭据 500 + 无 token 200 越权漏洞）
- [ ] `day30_run_pipeline.py`：端到端执行闭环（plan json → 生成代码 → mock → subprocess pytest → 报告；正常版 7/7 全绿 + 埋 Bug 版 5/7 抓到 2 缺陷）+ @tool 工具化演示（v5 接入点）
- [ ] `day30_pyright_pitfalls.py`：6 个新坑演示 + 模块零 API 自检
- [ ] 联网确认：pytest 9.1.1（2026-06-19 发布）；parametrize argvalues 迭代器弃用（9.1.0）→ 必须 list

## 核心概念

### 1. 分层：模型出语义，代码管工程（今日最关键的决策）
```python
# 模型只解析文档 → ApiDoc（端点/参数/example/期望码/响应字段）
api_doc = analyze_api_doc(text)          # prompt | llm.with_fallbacks | with_structured_output(ApiDoc)
# pytest 代码由确定性模板渲染（绝不让模型写代码）：
conftest = render_conftest(api_doc)      # BASE_URL + base_url/auth_headers fixture
tests = render_test_module(api_doc, plans)  # 每端点一个 Test 类，三件套必出
validate_python_syntax(tests, ...)       # ast.parse 可编译保证
# 为什么：模型写代码 = 语法不稳定/风格飘忽/不可 diff；模板渲染 = 语法稳/可 diff/三件套不漏
# 分界线：代码形状可预知（测试代码）→ 模板；代码形状不可预知（爬虫脚本）→ 模型写+人工审
