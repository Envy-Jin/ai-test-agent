# Day 3：Python 核心语法精讲（上）
# 内容：推导式 / 类型注解 / 异常处理 / 文件读写

# from typing import Literal, TypedDict
import json
from math import e
from sys import exception
import datetime
from collections import Counter

# # === 1. 列表推导式 ===
# # 普通写法
# test_ids_old = []
# for i in range(1, 6):
#     test_ids_old.append(f'tc-{i:03d}')
# print('普通写法', test_ids_old)

# # 推导式写法
# test_ids_new = [f'tc-{i:03d}' for i in range(1, 6)]
# print('推导式写法', test_ids_new)

# # 带条件的推导式
# even_cases = [f'tc-{i:03d}' for i in range(1, 11) if i % 2 == 0]
# print('偶数用例', even_cases)

# # 字典推导式：生成测试用例字典列表
# test_cases = [{'id' : f'tc-{i:03d}', 'name' : f'测试场景{i}', 'piority' : 'P1'} for i in range(1, 6)]
# print('测试用例字典列表')
# for case in test_cases:
#     print(f"{case['id']}: {case['name']} [{case['piority']}]")

# # 推导式练习题：
# # 练习 1
# test_results = [
#     {"case_id": "TC001", "name": "登录-正确密码", "status": "passed", "retry": 0},
#     {"case_id": "TC002", "name": "登录-错误密码", "status": "failed", "retry": 3},
#     {"case_id": "TC003", "name": "注册-邮箱格式", "status": "passed", "retry": 1},
#     {"case_id": "TC004", "name": "支付-超时回调", "status": "failed", "retry": 2},
#     {"case_id": "TC005", "name": "搜索-空关键词", "status": "failed", "retry": 0},
#     {"case_id": "TC006", "name": "下单-库存不足", "status": "failed", "retry": 5},
# ]

# results = [f'{test_result['case_id']} : {test_result['name']}' for test_result in test_results if test_result['status'] == 'failed' and test_result['retry'] >= 2]
# results_improve = [f'{r['case_id']} : {r['name']}' for r in test_results if r['status'] == 'failed' and r['case_id'].startswith('TC0') and r['retry'] > 2]
# print(results)
# print(results_improve)

# # 练习 2
# api_logs = [
#     {"path": "/api/login", "method": "POST", "status": 200, "duration_ms": 320},
#     {"path": "/api/login", "method": "POST", "status": 500, "duration_ms": 890},
#     {"path": "/api/users", "method": "GET", "status": 404, "duration_ms": 1500},
#     {"path": "/api/order", "method": "POST", "status": 201, "duration_ms": 2100},
#     {"path": "/api/order", "method": "POST", "status": 422, "duration_ms": 180},
#     {"path": "/api/report", "method": "GET", "status": 503, "duration_ms": 3200},
#     {"path": "/api/users", "method": "GET", "status": 404, "duration_ms": 900},
# ]

# seen = set()
# logs = [
#     log['path']
#     for log in api_logs
#     if log['status'] not in (200, 201, 204)
#     and log['duration_ms'] > 1000
#     and log['path'] not in seen
#     and not seen.add(log['path'])
# ]
# print(logs)

# # === 2. 函数与类型注解 ===
# Priority = Literal["P0", "P1", "P2"]


# class TestCase(TypedDict):
#     """测试用例数据结构。"""

#     id: str
#     title: str
#     priority: Priority


# def greeting(name: str) -> str:
#     '''生成欢迎语句'''
#     return f'hello, {name}! 我是AI助手'

# # print(greeting('测试工程师'))

# # 实际项目会用到的类型
# def generate_test_cases(
#     requirements: str,
#     count: int = 5,
#     priority: str = 'P1'
# ) -> list[dict]:
#     """
#     根据需求生成测试用例（占位，后续会被gemini真实实现）
#     Args:
#         requirements: 需求描述
#         count: 用例数量，默认5条
#         priority: 优先级，默认P1
#     Returns:
#         list[dict]: 测试用例列表，包含id、title、piority
#     """
#     # 占位，第二周被ai调用
#     return [
#         {
#             'id': f'TC-{i:03d}',
#             'title': f'测试:{requirements[:10]}...场景{i}',
#             'piority': priority
#         }
#         for i in range(1, count + 1)
#     ]

# cases = generate_test_cases("用户登录功能，支持手机号和邮箱", 3)
# print("\n生成的测试用例：")
# for case in cases:
#     print(f"  {case}")

# def find_case_by_id(cases: list[dict], case_id: str) -> dict | None:
#     """
#     按 ID 查找测试用例，找不到返回 None
    
#     Returns:
#         找到返回用例字典，找不到返回 None
#     """
#     for case in cases:
#         if case['id'] == case_id:
#             return case
#     return None

# result = find_case_by_id(cases, 'TC-001')
# missing = find_case_by_id(cases, 'TC-007')

# print(f"\n find case by id TC-001: {result}")
# print(f"\n find case by id TC-007: {missing}")

# #以下是cursor生成的代码。-Start
# def group_cases_by_priority(cases: list[TestCase]) -> dict[Priority, list[TestCase]]:
#     """
#     按优先级将测试用例分组。

#     将传入的测试用例列表按 ``priority`` 字段（P0 / P1 / P2）归类，
#     便于后续按优先级批量执行、评审或交给 AI Agent 分析。

#     Args:
#         cases: 测试用例字典列表。每条用例至少应包含 ``id``、``title``、
#             ``priority`` 字段，其中 ``priority`` 取值为 ``"P0"``、``"P1"``
#             或 ``"P2"``。

#     Returns:
#         dict[Priority, list[TestCase]]: 分组结果。key 为优先级（P0/P1/P2），
#         value 为该优先级下的用例列表。即使某优先级没有用例，也会返回空列表。

#     Examples:
#         >>> sample = [
#         ...     {"id": "TC-001", "title": "登录", "priority": "P0"},
#         ...     {"id": "TC-002", "title": "注册", "priority": "P1"},
#         ... ]
#         >>> grouped = group_cases_by_priority(sample)
#         >>> len(grouped["P0"])
#         1
#     """
#     grouped: dict[Priority, list[TestCase]] = {
#         "P0": [],
#         "P1": [],
#         "P2": [],
#     }
#     for case in cases:
#         priority = case["priority"]
#         if priority in grouped:
#             grouped[priority].append(case)
#     return grouped


# sample_cases: list[TestCase] = [
#     {"id": "TC-001", "title": "登录-正确密码", "priority": "P0"},
#     {"id": "TC-002", "title": "登录-错误密码", "priority": "P1"},
#     {"id": "TC-003", "title": "支付-超时回调", "priority": "P0"},
#     {"id": "TC-004", "title": "搜索-空关键词", "priority": "P2"},
#     {"id": "TC-005", "title": "注册-邮箱格式", "priority": "P1"},
# ]

# grouped_cases = group_cases_by_priority(sample_cases)
# print("\n按优先级分组：")
# for level in ("P0", "P1", "P2"):
#     print(f"  {level} ({len(grouped_cases[level])} 条):")
#     for case in grouped_cases[level]:
#         print(f"    {case['id']}: {case['title']}")
# #以下是cursor生成的代码。-End

# # === 3. 异常处理 ===
# # 模拟：直接访问不存在的字典 key（常见 Bug）
# test_case = {"id": "TC-001", "title": "登录测试"}

# # ❌ 错误写法（会崩溃）
# # print(test_case["priority"])  # KeyError!

# # ✅ 安全写法1：try/except
# try:
#     priority = test_case["priority"]
# except KeyError:
#     priority = "P2"  # 给一个默认值
#     print("⚠️  priority 字段缺失，使用默认值 P2")

# # ✅ 安全写法2：dict.get()（更简洁）
# priority2 = test_case.get("priority", "P2")
# print(f"用例优先级（get方式）：{priority2}")

# def parse_ai_response(raw_text: str) -> dict:
#     """
#     解析 AI 返回的 JSON 文本（模拟真实场景）
    
#     AI 有时返回格式不规范的 JSON, 需要健壮处理
#     """
#     try:
#         #尝试直接解析 JSON
#         result = json.loads(raw_text)
#         print(f"✅ 成功解析 JSON: {result}")
#         return result
#     except json.JSONDecodeError as e:
#         #json格式错误
#         print(f"❌ JSON 格式错误: {raw_text}")
#         return{'error':'json解析失败', 'raw': raw_text}
#     except Exception as e:
#         #其他异常
#         print(f"❌ 解析失败，未知错误: {type(e).__name__}: {e}")
#         return {'error': str(e)}
        
# # 测试各种情况
# print("\n--- 测试 AI 响应解析 ---")

# # 情况1：正常 JSON
# good_json = '{"test_cases": [{"id": "TC-001", "title": "登录测试"}]}'
# result1 = parse_ai_response(good_json)
# print(f"正常响应：{result1}\n")

# # 情况2：带 markdown 代码块的 JSON（AI 常见返回格式）
# bad_json = "```json\n{\"test_cases\": []}\n```"
# result2 = parse_ai_response(bad_json)
# print(f"带代码块：{result2}\n")

# # 情况3：完全错误的内容
# garbage = "对不起，我无法生成测试用例"
# result3 = parse_ai_response(garbage)
# print(f"错误内容：{result3}\n")

# # 情况4：非字符串输入（真正的未知错误）
# result4 = parse_ai_response(None)
# print(f"非字符串输入：{result4}\n")

# def safe_file_operation(filename: str) -> str:
#     """演示 finally 确保资源释放"""
#     file_handle = None
#     try:
#         file_handle = open(filename, "r", encoding="utf-8")
#         content = file_handle.read()
#         return content
#     except FileNotFoundError:
#         return f"⚠️  文件 {filename} 不存在"
#     except PermissionError:
#         return f"⚠️  没有权限读取 {filename}"
#     finally:
#         # 无论成功还是失败，finally 都会执行
#         if file_handle:
#             file_handle.close()
#             print(f"📁 文件句柄已关闭")

# print("\n--- 测试文件操作异常处理 ---")
# content = safe_file_operation("不存在的文件.txt")
# print(content)

# # 有 Bug 的代码——让 Cursor 帮你分析
# def calculate_pass_rate(passed: int, total: int) -> float:
#     if total == 0:
#         return 0.0
#     return passed / total * 100

# # 故意触发崩溃
# try:
#     rate = calculate_pass_rate(0, 0)
# except ZeroDivisionError as e:
#     print(f"\n捕获到除零错误：{e}")


# === 4. 文件读写 ===
# # 读取需求文档
# def read_requirement(filename: str) -> str:
#     '''读取需求文档'''
#     with open(filename, 'r', encoding='utf-8') as file:
#         content = file.read()
#     return content

# #测试读取
# print("\n--- 测试文件读取 ---")
# try:
#     req_text = read_requirement('docs/sample_requirement.txt')
#     print(f'文档长度：{len(req_text)} 个字符')
#     print(f'前100字符: \n{req_text[:100]}')
# except FileNotFoundError:
#     print(f"⚠️  请先创建 docs/sample_requirement.txt 文件")

# def read_requirements_by_line(filepath: str) -> list[str]:
#     """逐行读取需求文档，过滤掉空行"""
#     with open(filepath, "r", encoding="utf-8") as f:
#         lines = [line.strip() for line in f.readlines() if line.strip()]
#     return lines

# lines = read_requirements_by_line("docs/sample_requirement.txt")
# print(f"\n文档共 {len(lines)} 行（非空）")
# for i, line in enumerate(lines[:5], 1):
#     print(f"  第{i}行: {line}")

# # 将生成的测试用例写入文件
# def save_test_cases(cases: list[dict], output_path: str) -> None:
#     """将测试用例列表保存为 JSON 文件"""
#     with open(output_path, "w", encoding="utf-8") as f:
#         json.dump(cases, f, ensure_ascii=False, indent=2)
#     print(f"✅ 已保存 {len(cases)} 条用例到 {output_path}")

# # 生成并保存
# sample_cases = generate_test_cases("用户登录功能", count=3)
# save_test_cases(sample_cases, "docs/sample_test_cases.json")

# # 重新读取验证
# with open("docs/sample_test_cases.json", "r", encoding="utf-8") as f:
#     loaded = json.load(f)
# print(f"读回验证：加载了 {len(loaded)} 条用例")
# print(json.dumps(loaded, ensure_ascii=False, indent=2))


# # 记录日志
# def log_activity(message: str, log_file: str = "docs/agent.log") -> None:
#     """追加写入日志（不覆盖历史记录）"""
#     timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#     log_entry = f"[{timestamp}] {message}\n"
#     with open(log_file, "a", encoding="utf-8") as f:
#         f.write(log_entry)

# log_activity("Day 3 学习开始")
# log_activity("完成文件读写练习")
# log_activity("生成了 3 条测试用例")

# # 查看日志
# with open("docs/agent.log", "r", encoding="utf-8") as f:
#     print("\n--- 日志内容 ---")
#     print(f.read())


# from requirement_analyzer import analyze_requirement

# print("\n--- 综合练习：需求文档分析器 ---")
# result = analyze_requirement(
#     "docs/sample_requirement.txt",
#     "docs/requirement_analysis.json"
# )
# print(f"分析结果：")
# print(f"  总字数：{result.get('char_count', 'N/A')}")
# print(f"  总行数：{result.get('line_count', 'N/A')}")
# print(f"  关键约束行数：{len(result.get('keyword_lines', []))}")
# print(f"\n关键约束提取：")
# for line in result.get('keyword_lines', [])[:3]:
#     print(f"  - {line}")


# # ============ 10 道练习题 ============
# # 规则：先自己写，写完后用 Ctrl+L 让 Cursor 检查答案

# # 题1：用推导式生成 1~20 中所有能被 3 整除的数的平方
# # 期望：[9, 36, 81, 144, 225, 324]
# q1 = [i ** 2 for i in range(1, 21) if i % 3 == 0]  # 替换为你的推导式

# # 题2：将以下列表中的字符串转成大写，过滤掉长度小于 4 的
# words = ["get", "post", "delete", "put", "patch", "options"]
# # 期望：['POST', 'DELETE', 'PATCH', 'OPTIONS']
# q2 = [ch.upper() for ch in words if len(ch) >= 4]  # 替换为你的推导式

# # 题3：写一个函数，接收两个整数 a, b，返回它们的商（float），若 b=0 返回 None
# # 加类型注解
# def safe_divide(a: int, b: int) -> float | None:  # 补全返回值类型注解
#     return a / b if b != 0 else None  # 替换为你的实现

# # 题4：写一个函数，统计字符串中每个字符出现次数，返回字典
# # 如 "hello" → {"h":1, "e":1, "l":2, "o":1}
# def count_chars(text: str) -> dict[str, int]:
#     return dict(Counter(text))  # 替换为你的实现（提示：可用推导式或字典方法）

# # 题5：用 try/except 读取一个可能不存在的 JSON 文件，失败返回空字典
# def safe_read_json(filepath: str) -> dict:
#     try:
#         with open(filepath, 'r', encoding='utf-8') as file:
#             # content = file.read()
#             return json.load(file)
#     except FileNotFoundError:
#         return {}
#     # 替换为你的实现

# 题6：将字典列表按某个 key 的值排序（不用 lambda，用函数）
cases = [
    {"id": "TC-003", "priority": "P0"},
    {"id": "TC-001", "priority": "P2"},
    {"id": "TC-002", "priority": "P1"},
]
# 按 id 升序排序
def get_case_id(case: dict) -> str:
    return case["id"]

sorted_cases = sorted(cases, key=get_case_id)
print("\n题6结果(按 id 排序）：", sorted_cases)

# 题7：用推导式把上面 sorted_cases 的 id 提取成一个列表
q7 = [case['id'] for case in sorted_cases]  # 替换为你的推导式
print("题7结果: ", q7)

# 题8：写一个函数，接收文件路径，返回文件行数（文件不存在返回 -1）
def count_file_lines(filepath: str) -> int:
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            content = file.read()
            return len(content.splitlines())
    except FileNotFoundError:
        return -1
    # 替换为你的实现

# 题9：将测试用例列表写入 Markdown 表格格式的字符串（不需要写文件）
# 期望格式：
# | ID     | 标题         | 优先级 |
# |--------|------------|--------|
# | TC-001 | 测试场景1   | P1     |
def cases_to_markdown(cases: list[dict]) -> str:
    # 确定每一列的最大宽度
    id_width = max([len(str(case['id'])) for case in cases] + [len('ID')])
    title_width = max([len(str(case.get('title', case.get('name', '')))) for case in cases] + [len('标题')])
    priority_width = max([len(str(case.get('priority', case.get('piority', '')))) for case in cases] + [len('优先级')])

    # 构造表头和分隔线
    header = f"| {'ID'.ljust(id_width)} | {'标题'.ljust(title_width)} | {'优先级'.ljust(priority_width)} |"
    separator = f"|{'-' * (id_width+2)}|{'-' * (title_width+2)}|{'-' * (priority_width+2)}|"

    # 构造表格每一行
    rows = [
        f"| {str(case['id']).ljust(id_width)} | "
        f"{str(case.get('title', case.get('name', ''))).ljust(title_width)} | "
        f"{str(case.get('priority', case.get('piority', ''))).ljust(priority_width)} |"
        for case in cases
    ]
    return "\n".join([header, separator, *rows])

markdown_cases = [
    {"id": "TC-001", "title": "测试场景1", "priority": "P1"},
    {"id": "TC-002", "title": "测试场景2", "priority": "P0"},
]
print("\n题9结果:\n", cases_to_markdown(markdown_cases))

# 题10：用推导式将以下嵌套列表 "拍平"（二维→一维）
nested = [[1, 2, 3], [4, 5], [6, 7, 8, 9]]
# 期望：[1, 2, 3, 4, 5, 6, 7, 8, 9]
q10 = [nested[i][j] for i in range(len(nested)) for j in range(len(nested[i]))]  # 替换为你的推导式（提示：双层 for）
print("\n题10结果: ", q10)