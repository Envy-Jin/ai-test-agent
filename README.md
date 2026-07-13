# AI 测试辅助 Agent

## 项目简介

**AI 测试辅助 Agent** 是一个基于大语言模型的软件测试辅助工具，旨在帮助测试人员提升效率、减少重复劳动。通过 Agent 编排与工具调用，项目可覆盖常见测试场景，包括：

- **生成测试用例**：根据需求文档、接口定义或源代码，自动生成结构化测试用例
- **分析 Bug**：结合日志、堆栈与上下文，辅助定位问题根因并给出修复建议
- **接口测试**：解析 API 文档，生成并执行接口测试脚本，汇总测试结果

项目采用模块化设计，核心逻辑位于 `src/agent/`，便于后续扩展更多 Agent 角色与测试工具。

## 当前功能

| 模块 | 文件 | 功能说明 |
|------|------|----------|
| 需求解析 | `requirement_parser.py` | 从 `.txt` 需求文档提取功能点、子功能、约束条件，支持单文件/批量解析 |
| 需求分析 | `requirement_analyzer.py` | 统计需求字数与行数，提取含关键词的规则行，输出 JSON |
| 测试用例管理 | `test_case_model.py` | `TestCase` 数据类 + `TestCaseManager`（增删查、JSON 读写、Markdown 导出） |
| 测试用例预生成 | `test_case_pregenerator.py` | 根据解析结果为约束条件自动生成边界值测试用例框架 |
| 测试数据生成 | `data_generator.py` | 按字段定义批量生成随机测试数据 |
| 多格式输出 | `requirement_parser.py` | 解析结果支持 **JSON / Markdown / CSV** 三种格式 |
| 环境检查 | `check_env.py` | 验证 Python 版本、虚拟环境、依赖是否就绪 |

## 技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.10+ | 主开发语言 |
| 大模型 | Google Gemini | 通过 Gemini API 提供推理与生成能力（规划中） |
| Agent 框架 | LangChain | Agent 编排、工具链与 Prompt 管理（规划中） |
| 配置管理 | python-dotenv | 从 `.env` 加载 API Key 等环境变量 |
| 数据校验 | Pydantic | 结构化输入输出与类型约束 |
| HTTP 客户端 | requests | 接口测试与外部 API 调用 |
| 测试框架 | pytest | 单元测试与断言验证 |

## 快速开始

### 1. 克隆项目并进入目录

```bash
git clone <your-repo-url>
cd ai_test_agent
```

### 2. 创建虚拟环境并安装依赖

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. 配置环境变量

在项目根目录创建或编辑 `.env` 文件，填入你的 API Key：

```env
GEMINI_API_KEY=your_api_key_here
LANGCHAIN_API_KEY=your_key_here
```

### 4. 验证环境

```bash
python check_env.py
```

## 使用示例

### 需求文档解析（命令行）

```bash
# 解析单个需求文件，输出 JSON（默认）
python src/agent/requirement_parser.py docs/requirement.txt

# 显示详细解析结果
python src/agent/requirement_parser.py docs/requirement.txt -v

# 输出 Markdown 格式
python src/agent/requirement_parser.py docs/requirement_ecommerce.txt -f markdown -o docs/ecommerce_parsed.md

# 输出 CSV 格式
python src/agent/requirement_parser.py docs/requirement_education.txt -f csv -o docs/education_parsed.csv

# 解析并预生成边界值测试用例
python src/agent/requirement_parser.py docs/requirement.txt -t -o docs/parsed_requirement.json

# 批量解析 docs/ 目录下所有 .txt 文件
python src/agent/requirement_parser.py -b docs -v
```

### 测试用例管理（Python API）

```python
from src.agent.test_case_model import TestCase, TestCaseManager

manager = TestCaseManager()
manager.add_case(TestCase(
    id="TC-001",
    title="用户登录正常流程",
    steps=["打开登录页", "输入账号密码", "点击登录"],
    expected_result="跳转首页",
    priority="P0",
))

manager.save_to_json("docs/sample_test_cases.json")
manager.export_to_markdown("docs/sample_test_cases.md")
print(manager.count_by_priority())  # {'P0': 1}
```

### 测试用例预生成（Python API）

```python
from src.agent.requirement_parser import read_requirement_file, parse_requirement
from src.agent.test_case_pregenerator import generate_from_parsed_requirement

text = read_requirement_file("docs/requirement.txt")
parsed = parse_requirement(text)
cases_by_feature = generate_from_parsed_requirement(parsed)

for name, cases in cases_by_feature.items():
    print(f"{name}: 生成 {len(cases)} 条边界用例")
```

## 测试说明

项目使用 **pytest** 进行单元测试，测试文件位于 `tests/` 目录。

```bash
# 运行全部测试
pytest

# 显示详细输出
pytest -v

# 只运行需求解析器测试
pytest tests/test_requirement_parser.py -v

# 只运行基础练习测试
pytest tests/test_basic.py -v

# 显示打印信息（调试用）
pytest -s
```

测试覆盖范围包括：

- 功能分段、子功能提取、约束条件提取
- 完整需求解析流程
- JSON / Markdown / CSV 多格式输出
- 约束条件数字提取（边界值预生成）

## 第 1 周学习进度

| 天数 | 主题 | 状态 | 产出 |
|------|------|------|------|
| Day 1-2 | 项目搭建与环境配置 | ✅ 完成 | 目录结构、`.env`、`check_env.py`、`README` |
| Day 3 | Python 语法（上） | ✅ 完成 | 推导式、类型注解、异常处理、文件读写（`day3_practice.py`） |
| Day 4 | Python 语法（下） | ✅ 完成 | dataclass、JSON 序列化、环境变量、HTTP 请求（`day4_practice.py`） |
| Day 5 | 测试用例数据模型 | ✅ 完成 | `test_case_model.py`（TestCase + TestCaseManager） |
| Day 6 | 正则表达式 | ✅ 完成 | 需求解析器 `requirement_parser.py`、正则练习（`day6_practice.py`） |
| Day 7 | 集成与测试 | ✅ 完成 | 预生成器 `test_case_pregenerator.py`、pytest 单元测试、多格式输出、批量解析 |

> 第 1 周目标：完成需求文档 → 结构化解析 → 边界用例预生成 的完整链路。第 2 周计划接入 Gemini + LangChain 实现 AI 驱动的用例生成与 Bug 分析。

## 项目文档

- 架构说明：[docs/architecture.md](docs/architecture.md)
- 示例需求：`docs/requirement.txt`、`docs/requirement_ecommerce.txt`、`docs/requirement_education.txt`、`docs/requirement_social.txt`

## 目录结构（简要）

```
ai_test_agent/
├── src/agent/          # 核心业务模块
├── docs/               # 需求文档与解析/用例输出
├── tests/              # pytest 单元测试
├── check_env.py        # 环境检查脚本
├── requirements.txt
└── README.md
```
