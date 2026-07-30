# Day 4:Python 核心语法精讲(下)
# 内容:dataclass / JSON处理 / 环境变量 / HTTP请求
# 目标:实现 TestCase 数据类，能序列化/反序列化为 JSON

from dataclasses import dataclass, field, asdict, astuple
from dotenv import load_dotenv
import json
import re
import os
import requests

# # === 旧方式:用字典表示测试用例(有什么问题？)===

# # 问题1:没有类型检查——priority 写错了不会报错
# case_dict = {
#     "id": "TC-001",
#     "title": "用户登录正常流程",
#     "steps": ["打开登录页", "输入手机号", "输入密码", "点击登录"],
#     "expected": "跳转到首页，显示用户名",
#     "priority": "P1"
# }

# # 问题2:访问字段需要记住 key 的字符串，容易拼错
# print(case_dict["titel"])    # 拼错了！KeyError 才知道
# # 问题3:IDE 不给补全提示
# # 问题4:嵌套结构变复杂后可读性很差

# # === 新方式:用 dataclass 定义测试用例 ===

# @dataclass
# class TestCase:
#     id: str                          # 用例编号，如 "TC-001"
#     title: str                       # 用例标题
#     steps: list[str]                 # 测试步骤列表
#     expected: str                    # 预期结果
#     priority: str = "P2"             # 优先级，默认 P2(有默认值的放后面)

# # 创建实例——就像调用函数一样
# case1 = TestCase(
#     id="TC-001",
#     title="用户登录正常流程",
#     steps=["打开登录页", "输入手机号和密码", "点击登录"],
#     expected="成功跳转首页，顶部显示用户名",
#     priority="P0"
# )

# print("=== 基础 dataclass ===")
# print(case1)                         # 自动生成友好的 __repr__
# print(f"用例ID: {case1.id}")          # 用 . 访问属性，IDE 有补全！
# print(f"优先级: {case1.priority}")

# # === 完整版 TestCase(贴近实际项目)===

# @dataclass
# class TestCaseFull:
#     id: str
#     title: str
#     steps: list[str]
#     expected: str
#     priority: str = "P2"
#     test_type: str = "功能"                         # 功能/边界/异常/性能
#     preconditions: list[str] = field(default_factory=list)   # 前置条件
#     test_data: dict = field(default_factory=dict)             # 测试数据
#     tags: list[str] = field(default_factory=list)             # 标签
#     actual_result: str | None = None                       # 实际结果(执行后填写)
#     passed: bool | None = None                             # 是否通过

# # 注意:可变对象(list/dict)必须用 field(default_factory=...)，不能直接写 = []
# # 否则所有实例会共享同一个列表(这是 Python 的经典坑！)

# case2 = TestCaseFull(
#     id="TC-002",
#     title="手机号格式错误时登录失败",
#     steps=["输入非法手机号(如 abc)", "输入任意密码", "点击登录"],
#     expected="提示'手机号格式不正确'，不跳转",
#     priority="P1",
#     test_type="异常",
#     preconditions=["用户未登录"],
#     test_data={"phone": "abcdefg", "password": "Test123456"}
# )

# print("\n=== 完整版 TestCase ===")
# print(case2)
# print(f"前置条件:{case2.preconditions}")
# print(f"测试数据:{case2.test_data}")
# print(f"测试标签: {case2.tags}")
# print(f"测试结果: {case2.actual_result}")

# # === dataclass 工具函数 ===
# # asdict:转换为字典(序列化的关键！)
# case_dict = asdict(case2)
# print("\nasdict() 转换结果:")
# print(type(case_dict))           # <class 'dict'>
# print(case_dict)

# # astuple:转换为元组(了解即可)
# case_tuple = astuple(case1)
# print(f"{case_tuple}")
# print(f"\nastuple() 结果长度:{len(case_tuple)}")

# 字段比较(dataclass 自动生成 __eq__)
# case3 = TestCase(id="TC-001", title="用户登录正常流程",
#                   steps=["打开登录页", "输入手机号和密码", "点击登录"],
#                   expected="成功跳转首页，顶部显示用户名", priority="P0")
# print(f"\n两个相同内容的实例是否相等:{case1 == case3}")   # True

# # === BugReport:缺陷报告数据类 ===

# @dataclass
# class BugReport:
#     """缺陷报告数据类，用于结构化描述和跟踪 Bug 信息。"""

#     id: str                              # 缺陷编号，如 "BUG-001"
#     title: str                           # 缺陷标题，简要概括问题
#     description: str                     # 缺陷详细描述
#     reproduce_steps: list[str]           # 复现步骤列表，按顺序记录操作
#     reporter: str                        # 报告人，提交该缺陷的测试人员
#     severity: str = "一般"               # 严重程度，如:致命/严重/一般/轻微
#     created_at: str = ""                 # 创建时间，建议格式 "YYYY-MM-DD HH:MM:SS"
#     fixed: bool = False                  # 是否已修复，默认未修复


# test_bug = BugReport(
#     id = "BUG-001",
#     title = "用户登录正常流程",
#     description = "用户登录正常流程",
#     reproduce_steps = ["打开登录页", "输入手机号和密码", "点击登录"],
#     reporter = "张三",
#     severity = "一般",
#     created_at = "2026-06-28 10:00:00"
# )

# print(asdict(test_bug))

# print("\n=== JSON 序列化与反序列化 ===")

# # dumps:Python 对象 → JSON 字符串
# data = {
#     "test_cases": [
#         {"id": "TC-001", "title": "登录测试", "priority": "P0"},
#         {"id": "TC-002", "title": "注销测试", "priority": "P1"},
#     ],
#     "total": 2,
#     "generated_at": "2026-06-28"
# }

# # 基础序列化
# json_str = json.dumps(data)
# print(f"原始数据:\n{data}\n")
# # print(f"基础序列化(无格式化):\n{json_str}\n")

# # 带格式化和中文支持(开发调试时用这个)
# json_pretty = json.dumps(data, ensure_ascii=False, indent=2)
# print(f"格式化序列化:\n{json_pretty}\n")


# # TestCase → JSON 字符串
# print("\n=== dataclass ↔ JSON 互转 ===")
# case_for_json = TestCase(
#     id="TC-003",
#     title="密码输入超长字符串",
#     steps=["在密码框输入300个字符", "点击登录"],
#     expected="提示密码长度不超过50位, 不提交表单",
#     priority="P1"
# )

# # 步骤1:dataclass → dict
# case_dict = asdict(case_for_json)
# # 步骤2:dict → JSON 字符串
# case_json = json.dumps(case_dict, ensure_ascii=False, indent=2)
# # print(f"TestCase 序列化为 JSON: \n{case_json}\n")

# # 反向:JSON 字符串 → TestCase
# # 步骤1:JSON 字符串 → dict
# loaded_dict = json.loads(case_json)
# # 步骤2:dict → dataclass(用 **字典解包)
# restored_case = TestCase(**loaded_dict)
# print(f"从 JSON 还原 TestCase:\n")
# print(f"  ID: {restored_case.id}")
# print(f"  标题: {restored_case.title}")
# print(f"  优先级: {restored_case.priority}")
# print(f"  步骤数: {len(restored_case.steps)}")

# # 批量创建测试用例
# print("\n=== JSON 文件读写 ===")

# test_cases_list = [
#     TestCase(id=f"TC-{i:03d}", title=f"测试场景{i}",
#              steps=[f"步骤{j}" for j in range(1, 3)],
#              expected=f"预期结果{i}",
#              priority="P0" if i == 1 else "P1")
#     for i in range(1, 6)
# ]

# # 写入 JSON 文件
# output_path = "docs/day4_test_cases.json"
# with open(output_path, "w", encoding="utf-8") as f:
#     json.dump(
#         [asdict(c) for c in test_cases_list],    # 列表推导式转换所有用例
#         f,
#         ensure_ascii=False,
#         indent=2
#     )
# print(f"✅ 已写入 {len(test_cases_list)} 条用例到 {output_path}")

# with open("docs/day4_test_cases.json", "r", encoding="utf-8") as f:
#     loaded_cases_raw = json.load(f)

# loaded_cases = [TestCase(**c) for c in loaded_cases_raw]
# print(f"读取并还原:{len(loaded_cases)} 个 TestCase 对象")
# for c in loaded_cases[:3]:
#     print(f"  [{c.priority}] {c.id}: {c.title}")

# #处理 LLM 返回的不规范 JSON(实战技巧)
# def safe_parse_llm_json(llm_output: str) -> dict | list | None:
#     """
#     安全解析 LLM 返回的 JSON——LLM 经常在 JSON 外面包裹 markdown 代码块
    
#     Args:
#         llm_output: LLM 的原始输出文本
    
#     Returns:
#         解析成功返回 dict 或 list, 失败返回 None
#     """
#     text = llm_output.strip()
#     if not text:
#         return None

#     # 策略1:直接解析
#     try:
#         return json.loads(text)
#     except json.JSONDecodeError:
#         pass

#     # 策略2:提取 ```json ... ``` 代码块
#     pattern = r'```(?:json)?\s*([\s\S]*?)\s*```'
#     match = re.search(pattern, llm_output)
#     if match:
#         try:
#             return json.loads(match.group(1))
#         except json.JSONDecodeError:
#             pass

#     # 策略3:从每个 { 或 [ 起点尝试 raw_decode(比 find/rfind 截取更安全)
#     decoder = json.JSONDecoder()
#     for index, char in enumerate(text):
#         if char not in "{[":
#             continue
#         try:
#             obj, _ = decoder.raw_decode(text, index)
#             return obj
#         except json.JSONDecodeError:
#             continue

#     return None   # 三种策略都失败，返回 None

# # 测试1:正常 JSON
# r1 = safe_parse_llm_json('{"test_cases": [{"id": "TC-001"}]}')
# print(f"正常 JSON: {r1}")

# # 测试2:LLM 包了 markdown 代码块
# r2 = safe_parse_llm_json('这是测试用例:\n```json\n{"test_cases": []}\n```\n希望对你有帮助!')
# print(f"含代码块的输出:{r2}")

# # 测试3:JSON 前后有废话
# r3 = safe_parse_llm_json('好的，以下是结果:{"id": "TC-001", "title": "登录"} 请参考以上内容。')
# print(f"JSON前后有废话: {r3}")

# # # 测试4:完全不含 JSON
# # r4 = safe_parse_llm_json("对不起，我无法完成这个请求。")
# # print(f"无 JSON 内容:{r4}")

# #使用 python-dotenv 读取环境变量
# print("\n=== 环境变量读取 ===")

# # 加载 .env 文件(调用一次，之后 os.getenv 就能读到)
# load_dotenv()

# # 读取各种类型的环境变量
# api_key = os.getenv("GEMINI_API_KEY")
# app_env = os.getenv("APP_ENV", "production")      # 第二个参数是默认值
# max_retries = int(os.getenv("MAX_RETRIES", "3"))   # 注意:环境变量永远是字符串！
# debug_mode = os.getenv("DEBUG_MODE", "false").lower() == "true"   # 转为 bool

# print(f"环境:{app_env}")
# print(f"最大重试次数:{max_retries}(类型:{type(max_retries).__name__})")
# print(f"调试模式:{debug_mode}(类型:{type(debug_mode).__name__})")

# # 敏感信息不直接打印——只确认是否存在
# if api_key and api_key != "your_gemini_api_key_here":
#     print(f"✅ GEMINI_API_KEY 已配置(长度:{len(api_key)})")
# else:
#     print("⚠️  GEMINI_API_KEY 未配置或仍是占位值(后续填入真实 Key)")

# @dataclass
# class AppConfig:
#     """应用配置——从环境变量加载"""
#     gemini_api_key: str
#     app_env: str = "development"
#     max_retries: int = 3
#     debug_mode: bool = False

#     @classmethod
#     def from_env(cls) -> "AppConfig":
#         """从环境变量创建配置实例"""
#         load_dotenv()
#         key = os.getenv("GEMINI_API_KEY", "")
#         if not key:
#             raise ValueError("GEMINI_API_KEY 未配置！请在 .env 文件中填入真实的 API Key")
#         return cls(
#             gemini_api_key=key,
#             app_env=os.getenv("APP_ENV", "development"),
#             max_retries=int(os.getenv("MAX_RETRIES", "3")),
#             debug_mode=os.getenv("DEBUG_MODE", "false").lower() == "true"
#         )

# # 测试配置加载（忽略 Key 未配置的错误）
# print("\n=== 配置类测试 ===")
# try:
#     config = AppConfig.from_env()
#     print(f"配置加载成功:环境={config.app_env}, 重试={config.max_retries}, 调试={config.debug_mode}")
# except ValueError as e:
#     print(f"配置加载失败（预期结果）:{e}")
#     # 创建一个带占位 Key 的配置用于后续测试
#     config = AppConfig(gemini_api_key="placeholder", app_env="development")
#     print(f"使用占位配置继续测试")

# print("\n=== HTTP 请求:GET ===")
# # 最简单的 GET 请求
# try:
#     response = requests.get("https://httpbin.org/json", timeout=10)
#     print(f"状态码:{response.status_code}")          # 200
#     print(f"响应头 Content-Type:{response.headers.get('Content-Type')}")
#     print(f"响应体(JSON):{response.json()}") 
#     # 常用属性
#     print(f"\n响应体(文本): {response.text[:100]}...")
#     print(f"编码：{response.encoding}")
#     print(f"响应时间：{response.elapsed.total_seconds():.3f} 秒")

# except requests.exceptions.Timeout:
#     print("❌ 请求超时（网络不稳定时会触发）")
# except requests.exceptions.ConnectionError:
#     print("❌ 连接失败(没有网络时会触发)")

# print("\n=== GET 请求带查询参数 ===")

# try:
#     # 方式1：直接拼接 URL（不推荐）
#     # resp = requests.get("https://httpbin.org/get?name=TestAgent&version=1.0")

#     # 方式2：用 params 参数（推荐！自动处理编码）
#     params = {
#         "name": "TestAgent",
#         "version": "1.0",
#         "feature": "测试用例生成"    # 中文会自动 URL 编码
#     }
#     resp = requests.get("https://httpbun.com/get", params=params, timeout=10)
#     data = resp.json()

#     print(f"状态码：{resp.status_code}")
#     print(f"请求 URL（含参数）：{resp.url}")    # 查看实际请求的完整 URL
#     print(f"服务端接收到的参数：{data.get('args', {})}")

# except Exception as e:
#     print(f"请求异常：{e}")

# print("\n=== POST 请求（模拟登录接口调用）===")

# try:
#     # 模拟登录接口测试
#     login_payload = {
#         "phone": "13800138000",
#         "password": "Test123456",
#         "remember_me": True
#     }

#     resp = requests.post(
#         "https://httpbun.com/post",     # httpbin 会把我们的请求体原样返回
#         json=login_payload,             # 自动设置 Content-Type: application/json
#         timeout=10
#     )

#     data = resp.json()
#     print(f"状态码：{resp.status_code}")
#     print(f"服务端接收到的 JSON body：{data.get('json', {})}")
#     print(f"请求 Headers：{dict(list(resp.request.headers.items())[:3])}")  # 前3个

# except Exception as e:
#     print(f"请求异常：{e}")

# #5.4 封装一个简单的 API 测试执行器
# @dataclass
# class ApiTestResult:
#     """单次 API 测试的结果"""
#     url: str
#     method: str
#     status_code: int
#     response_body: dict
#     response_time_ms: float
#     passed: bool
#     error_message: str | None = None

# def execute_api_test(
#     url: str,
#     method: str = "GET",
#     payload: dict | None = None,
#     headers: dict | None = None,
#     timeout: int = 10
# ) -> ApiTestResult:
#     """
#     执行一次 API 测试请求
    
#     Args:
#         url: 接口地址
#         method: HTTP 方法，GET/POST/PUT/DELETE
#         payload: 请求体（POST/PUT 时使用）
#         headers: 自定义请求头
#         timeout: 超时秒数
    
#     Returns:
#         ApiTestResult 对象，包含状态码、响应体、耗时等信息
#     """
#     default_headers = {"Content-Type": "application/json"}
#     if headers:
#         default_headers.update(headers)

#     try:
#         resp = requests.request(
#             method=method.upper(),
#             url=url,
#             json=payload,
#             headers=default_headers,
#             timeout=timeout
#         )
#         return ApiTestResult(
#             url=url,
#             method=method.upper(),
#             status_code=resp.status_code,
#             response_body=resp.json() if resp.headers.get("Content-Type", "").startswith("application/json") else {"raw": resp.text[:200]},
#             response_time_ms=resp.elapsed.total_seconds() * 1000,
#             passed=(200 <= resp.status_code < 300)
#         )
#     except requests.exceptions.Timeout:
#         return ApiTestResult(url=url, method=method, status_code=-1,
#                              response_body={}, response_time_ms=-1,
#                              passed=False, error_message="请求超时")
#     except Exception as e:
#         return ApiTestResult(url=url, method=method, status_code=-1,
#                              response_body={}, response_time_ms=-1,
#                          passed=False, error_message=str(e))

# print("\n=== API 测试执行器 ===")

# # 测试1：正常 GET
# result1 = execute_api_test("https://httpbin.org/get")
# print(f"GET 测试：状态码={result1.status_code}, 耗时={result1.response_time_ms:.0f}ms, 通过={result1.passed}")

# # 测试2：POST 模拟登录
# result2 = execute_api_test(
#     "https://httpbin.org/post",
#     method="POST",
#     payload={"username": "test_user", "password": "Test123"}
# )
# print(f"POST 测试：状态码={result2.status_code}, 耗时={result2.response_time_ms:.0f}ms, 通过={result2.passed}")

# # 测试3：模拟失败（404）
# result3 = execute_api_test("https://httpbin.org/status/404")
# print(f"404 测试：状态码={result3.status_code}, 通过={result3.passed}")


# === 今日里程碑：集成 TestCaseManager ===
from test_case_model import TestCase as TC, TestCaseManager

print("\n=== 今日里程碑：TestCase 完整系统 ===")
manager = TestCaseManager()

# 添加几条测试用例
manager.add_case(TC(
    id="TC-001", title="正常登录",
    priority="P0", test_type="功能",
    preconditions=["用户已注册"],
    steps=["打开登录页", "输入正确手机号和密码", "点击登录"],
    expected_result="成功跳转首页"
))
manager.add_case(TC(
    id="TC-002", title="手机号格式错误",
    priority="P1", test_type="异常",
    preconditions=["用户未登录"],
    steps=["输入非法手机号", "输入密码", "点击登录"],
    expected_result="提示手机号格式错误"
))
manager.add_case(TC(
    id="TC-003", title="密码连续错误5次锁定",
    priority="P0", test_type="边界",
    preconditions=["用户已注册"],
    steps=["连续5次输入错误密码"],
    expected_result="账号锁定30分钟，提示锁定时间"
))
# 保存到 JSON
manager.save_to_json("docs/final_test_cases.json")
# 按优先级查询
p0_cases = manager.find_by_priority("P0")
print(f"P0 级用例数量：{len(p0_cases)}")
# 重新加载
manager2 = TestCaseManager()
manager2.load_from_json("docs/final_test_cases.json")
print(f"从文件加载：{len(manager2.cases)} 条用例")
print("✅ TestCase 序列化/反序列化验证通过！")