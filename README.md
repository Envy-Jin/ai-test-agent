# AI 测试辅助 Agent

## 项目简介

**AI 测试辅助 Agent** 是一个基于大语言模型的软件测试辅助工具，旨在帮助测试人员提升效率、减少重复劳动。通过 Agent 编排与工具调用，项目可覆盖常见测试场景，包括：

- **生成测试用例**：根据需求文档、接口定义或源代码，自动生成结构化测试用例
- **分析 Bug**：结合日志、堆栈与上下文，辅助定位问题根因并给出修复建议
- **接口测试**：解析 API 文档，生成并执行接口测试脚本，汇总测试结果

项目采用模块化设计，核心逻辑位于 `src/agent/`，便于后续扩展更多 Agent 角色与测试工具。

## 技术栈

| 类别 | 技术 | 说明 |
|------|------|------|
| 语言 | Python 3.10+ | 主开发语言 |
| 大模型 | Google Gemini | 通过 Gemini API 提供推理与生成能力 |
| Agent 框架 | LangChain | Agent 编排、工具链与 Prompt 管理 |
| 配置管理 | python-dotenv | 从 `.env` 加载 API Key 等环境变量 |
| 数据校验 | Pydantic | 结构化输入输出与类型约束 |
| HTTP 客户端 | requests | 接口测试与外部 API 调用 |

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

配置完成后即可开始开发与运行 Agent。后续可在 `src/agent/` 中扩展具体功能模块。
