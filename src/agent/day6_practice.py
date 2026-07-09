# === 1. 正则表达式基础 === 
from ast import pattern
from dataclasses import dataclass, asdict, field
import re
import json

# # re 模块的核心函数: 
# # re.search(pattern, text)   -> 在文本中搜索第一个匹配, 返回 Match 对象或 None 
# # re.findall(pattern, text)  -> 返回所有匹配的字符串列表 
# # re.finditer(pattern, text) -> 返回所有匹配的 Match 对象迭代器 
# # re.match(pattern, text)    -> 从文本开头匹配(不常用) 
# # re.sub(pattern, repl, text)-> 替换匹配内容 

# # --- 示例1: 查找所有手机号 --- 
# text1 = "联系方式: 13800138000, 备用电话13912345678, 客服010-12345678" 
# phone_pattern = r'1[3-9]\d{9}'   # 手机号正则: 1开头, 第二位3-9, 后面9位数字 
# phones = re.findall(phone_pattern, text1) 
# print("找到的手机号: ", phones) 
# # 期望: ['13800138000', '13912345678']

# # --- 示例2：提取括号中的内容 ---
# text2 = "记住登录状态(7天有效),缓存数据(30分钟过期)"
# paren_pattern = r'\(([^)]+)\)'   # 匹配中文括号及其内容
# paren_contents = re.findall(paren_pattern, text2)
# print("括号内容：", paren_contents)
# # 期望：['7天有效', '30分钟过期']

# # --- 正则核心语法演示 ---

# # 1. 字符类 [abc] 匹配括号中的任意一个字符
# print("\n--- 字符类 ---")
# print(re.findall(r'[aeiou]', "hello world"))  # ['e', 'o', 'o']

# # 2. 范围 [a-z] [0-9] [\u4e00-\u9fa5]（中文字符范围）
# print(re.findall(r'[A-Z]', "Hello World"))     # ['H', 'W']
# chinese_text = "用户user登录login"
# print(re.findall(r'[\u4e00-\u9fa5]+', chinese_text))  # ['用户', '登录']

# # 3. 量词：* 零次或多次, + 一次或多次, ? 零次或一次, {n,m} n到m次
# print("\n--- 量词 ---")
# print(re.findall(r'\d+', "a1bb22ccc333"))      # ['1', '22', '333']
# print(re.findall(r'\d{2,3}', "a1bb22ccc333"))   # ['22', '333']

# # 4. 分组 () 提取匹配的部分 group(0) 是整个匹配内容，group(n) 是第n个括号内容, 如果没有对应数量的括号会报no such group错
# print("\n--- 分组 ---")
# match = re.search(r'(\d+)次', "失败超过5次锁定")
# print(match)
# if match:
#     print(f"数字部分：{match.group(1)}")  # group(1) 是第一个括号内容

# # 5. 特殊字符 \d \w \s \b
# # \d = 数字, \w = 字母数字下划线, \s = 空白字符, \b = 单词边界
# print("\n--- 特殊字符 ---")
# print(re.findall(r'\d+', "密码8位，至少1个数字"))   # ['8', '1']
# print(re.findall(r'\w+', "hello_world test"))       # ['hello_world', 'test']

# #练习 1
# text = '''请联系测试负责人 zhangsan@test.com 或 li.si@example.cn 获取账号。
# 备用邮箱：admin+dev@mail.com
# 无效示例：not-an-email@、@missing.com'''

# emails = re.findall(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+', text)
# print("练习1:", emails)

# #练习 2
# rules = [
#     "密码不少于8位",
#     "登录失败超过5次锁定账号30分钟",
#     "验证码有效期60秒",
#     "用户名长度在3到20之间",
#     "本次测试共执行128条用例",
# ]

# pattern = r'\d+'
# rules_dict = {}
# for rule in rules:
#     rules_dict[rule] = [int(num) for num in re.findall(pattern, rule)]
# print(rules_dict)

# #练习 3
# features = [
#     "用户登录功能：支持手机号和邮箱登录",
#     "订单管理功能：支持创建订单、取消订单、查询订单状态",
#     "支付功能：支持微信和支付宝",
#     "搜索功能：支持关键词搜索",
# ]

# pattern = r'(.+?)功能[：:](.+)'
# result = []

# for feature in features:
#     temp = {}
#     match = re.search(pattern, feature)
#     if match:
#         feature_name = match.group(1)      # 用户登录
#         sub_part = match.group(2)          # 支持手机号和邮箱登录
#     sub_part = re.sub(r'^支持', '', sub_part) #在正则表达式中，[]表示字符集，其中的^表示取反，而非[]中的^表示以什么字符开头
#     parts = re.split(r'[、和]', sub_part)
#     sub_features = [re.sub(r'登录$', '', p).strip() for p in parts if p.strip()] #在正则表达式中，$表示以什么字符结尾
#     temp['feature_name'] = feature_name
#     temp['sub_features'] = sub_features
#     result.append(temp)
# print(result)

# # --- 贪婪 vs 非贪婪 ---
# print("\n--- 贪婪 vs 非贪婪 ---")

# text = "功能A：描述1。功能B：描述2。"

# # 贪婪匹配（默认）：.* 会尽可能多匹配
# greedy = re.findall(r'功能(.*)：', text)
# print(f"贪婪匹配：{greedy}")  # ['A：描述1。功能B']，相当于匹配到了内容“功能(A：描述1。功能B)：”

# # 非贪婪匹配：.*? 尽可能少匹配（加个 ? 即可）
# non_greedy = re.findall(r'功能(.*?)：', text)
# print(f"非贪婪匹配：{non_greedy}")  # ['A', 'B']，相当于匹配到了1.“功能(A):”和2.“功能(B):”

@dataclass
class Feature:
    """单个功能模块的解析结果"""
    feature: str    # 功能名称，如"用户注册"
    sub_features: list[str] = field(default_factory=list)    # 子功能列表
    constraints: list[str] = field(default_factory=list)    # 约束条件列表
    raw_text: str = ""    # 原始文本

@dataclass
class ParsedRequirement:
    """完整需求文档的解析结果"""
    features: list[Feature] = field(default_factory=list)   # 所有功能模块
    source_file: str = ''    # 源文件路径
    total_features: int = 0     # 功能总数
    total_sub_features: int = 0    # 子功能总数
    total_constraints: int = 0    # 约束总数


    def summarize(self) -> str:
        """生成解析摘要"""
        return (
            f"共解析出 {self.total_features} 个功能模块，"
            f"提取 {self.total_constraints} 条约束条件"
        )

# # 快速验证 dataclass 定义
# print("\n=== dataclass 验证 ===")
# test_feature = Feature(
#     feature="测试功能",
#     sub_features=["子功能1", "子功能2"],
#     constraints=["约束1"]
# )
# print(test_feature)
# print(f"asdict 转换：{asdict(test_feature)}")


# === 3. 核心解析逻辑 ===
def extract_features(text: str) -> list[str]:
    """
    从需求文本中提取所有功能名称
    
    匹配模式："XX功能：" 或 "XX功能："
    示例："用户注册功能：" → 提取 "用户注册"
    
    Args:
        text: 需求文档文本
    Returns:
        功能名称列表
    """
    # 正则解释：
    # ([\u4e00-\u9fa5]+)  → 匹配一个或多个中文字符（功能名称）
    # 功能                → 匹配字面量"功能"
    # [：:]               → 匹配中文冒号或英文冒号
    pattern = r'([\u4e00-\u9fa5]+)功能[：:]'
    features = re.findall(pattern, text)
    return features

# # 测试提取功能名称
# print("\n=== 提取功能名称 ===")
sample_text = "用户注册功能：支持手机号注册。商品搜索功能：支持关键词搜索。"
# feature_names = extract_features(sample_text)
# print(f"提取到的功能：{feature_names}")
# # 期望：['用户注册', '商品搜索']

def split_by_features(text: str) -> list[tuple[str, str]]:
    """
    将需求文本按功能分段
    
    Args:
        text: 完整需求文本
    Returns:
        元组列表：(功能名称, 该功能对应的描述文本)
    """
    # 策略：用正则找到所有"XX功能："的位置，然后切片
    pattern = r'([\u4e00-\u9fa5]+)功能[：:]'
    matches = list(re.finditer(pattern, text))
    segments = []
    for i, match in enumerate(matches):
        feature_name = match.group(1)
        start = match.end()     # 功能描述开始位置（冒号之后）
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)     # 下一个功能的开始位置，或者文本末尾
        description = text[start:end].strip()
        segments.append((feature_name, description))
    return segments

# # 测试分段
# print("\n=== 按功能分段 ===")
# segments = split_by_features(sample_text)
# print(segments)
# for name, desc in segments:
#     print(f"功能：{name}")
#     print(f"描述：{desc[:50]}...")
#     print()

def extract_sub_features(description: str) -> list[str]:
    """
    从功能描述中提取子功能
    
    匹配模式：以"支持"、"需要"开头，到逗号/句号结束的短语
    
    Args:
        description: 单个功能的描述文本
    Returns:
        子功能列表
    """
    sub_features = []

    # 匹配 "支持XX" 或 "需要XX"，到标点符号结束
    # 正则解释：
    # (支持|需要)       → 匹配"支持"或"需要"
    # ([\u4e00-\u9fa5\w]+?)  → 非贪婪匹配中文和字母数字（子功能内容）
    # (?=[，,。.；;（(])    → 正向预查：到标点符号前停止（不消耗标点）
    pattern = r'(支持|需要)([\u4e00-\u9fa5\w]+?)(?=[，,。.；;（(])'
    matches = re.findall(pattern, description)

    for prefix, context in matches:
        sub_feature = f"{prefix}{context}"
        sub_features.append(sub_feature)

    return sub_features

# # 测试提取子功能
# print("\n=== 提取子功能 ===")
# test_desc = "支持手机号注册，需要短信验证码验证，支持按价格排序，搜索结果分页显示。"
# subs = extract_sub_features(test_desc)
# print(f"子功能：{subs}")


def extract_constraints(description: str) -> list[str]:
    """
    从功能描述中提取约束条件
    
    约束条件特征：包含"不少于"、"不超过"、"必须"、"唯一"、"至少"、"最多"等关键词
    
    Args:
        description: 单个功能的描述文本
    Returns:
        约束条件列表
    """
    constraints = []

    # 约束关键词列表
    constraint_keywords = ['不少于', '不超过', '必须', '唯一', '至少', '最多', '不可', '不能', '禁止', '长度']

    # 按逗号/句号分割成短句
    sentences = re.split(r'[，,。.；;]', description)

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue
        # 检查短句中是否包含约束关键词
        for keyword in constraint_keywords:
            if keyword in sentence:
                constraints.append(sentence)
                break  # 同一句不重复添加

    return constraints

# # 测试提取约束条件
# print("\n=== 提取约束条件 ===")
# test_desc2 = "密码不少于8位且必须包含数字和字母，年龄必须在1-150之间，同一手机号不可重复注册。"
# cons = extract_constraints(test_desc2)
# print(f"约束条件：{cons}")
# for i, c in enumerate(cons, 1):
#     print(f"  {i}. {c}")

def parse_requirement(text: str) -> ParsedRequirement:
    """
    解析完整的需求文档文本，返回结构化结果
    
    Args:
        text: 需求文档完整文本
    Returns:
        ParsedRequirement 对象
    """
    segments = split_by_features(text)
    features = []
    total_constraints = 0
    for feature_name, description in segments:
        # 2. 提取子功能
        sub_features = extract_sub_features(description)
        # 3. 提取约束条件
        constraints = extract_constraints(description)

        feature = Feature(
            feature=feature_name,
            sub_features=sub_features,
            constraints=constraints,
            raw_text=description
        )

        features.append(feature)
        total_constraints += len(constraints)

    return ParsedRequirement(
        features=features,
        source_file=text,
        total_features=len(features),
        total_constraints=total_constraints
    )

# # 测试完整解析
# print("\n=== 完整解析测试 ===")
# result = parse_requirement(sample_text)
# print(result.summarize())
# for f in result.features:
#     print(f"\n功能：{f.feature}")
#     print(f"  子功能：{f.sub_features}")
#     print(f"  约束条件：{f.constraints}")


# === 4. 文件读写 ===
def read_requirement_file(filepath: str) -> str:
    """
    读取需求文件内容
    
    Args:
        filepath: 文件路径
    Returns:
        文件文本内容
    Raises:
        FileNotFoundError: 文件不存在
    """
    try:
        with open(filepath, 'r', encoding='utf-8') as file:
            return file.read()
    except FileNotFoundError:
        print(f"❌ 文件不存在：{filepath}")
        raise
    except Exception as e:
        print(f"❌ 读取文件失败：{type(e).__name__}: {e}")
        raise

def save_parsed_result(result: ParsedRequirement, output_path: str) -> None:
    """
    将解析结果保存为 JSON 文件
    
    Args:
        result: ParsedRequirement 对象
        output_path: 输出文件路径
    """
    # dataclass → dict → JSON
    result_dict = {
        "features": [asdict(f) for f in result.features],
        "source_file": result.source_file,
        "total_features": result.total_features,
        "total_constraints": result.total_constraints,
        "summary": result.summarize()
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(result_dict, f, ensure_ascii=False, indent=2)

    print(f"✅ 解析结果已保存到 {output_path}")


print("\n=== 端到端测试 ===")
try:
    # 1. 读取需求文件
    req_text = read_requirement_file("docs/requirement.txt")
    print(f"读取需求文件成功，共 {len(req_text)} 个字符")

    # 2. 解析
    result = parse_requirement(req_text)
    result.source_file = "docs/requirement.txt"
    print(f"\n{result.summarize()}")

    # 3. 打印详细结果
    for f in result.features:
        print(f"\n【{f.feature}】")
        print(f"  子功能 ({len(f.sub_features)} 个):")
        for sf in f.sub_features:
            print(f"    - {sf}")
        print(f"  约束条件 ({len(f.constraints)} 个):")
        for c in f.constraints:
            print(f"    - {c}")

    # 4. 保存为 JSON
    save_parsed_result(result, "docs/parsed_requirement.json")

except FileNotFoundError:
    print("⚠️  请先创建 docs/requirement.txt 文件（步骤 3）")