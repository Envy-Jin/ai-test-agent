"""
src/agent/interactive_analyzer.py —— 交互式需求分析对话脚本

Day 11 综合实战：多轮对话 + 历史管理 + 错误处理的最终融合

功能：
1. 创建一个需求分析对话会话
2. 支持多轮追问（需求分析 → 用例生成 → 补充优化 → 代码输出）
3. 随时查看对话历史
4. 支持导出对话记录
5. 全程使用 safe_text() + SafeChat，零 None 崩溃
"""

from google import genai
from google.genai import types
import os
import json
import time
from typing import Optional
from dotenv import load_dotenv
from utils import safe_text, safe_parts

# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

load_dotenv()
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-3.1-flash-lite"

SYSTEM_PROMPT = (
    "你是一名有 10 年经验的资深软件测试工程师，"
    "精通等价类划分、边界值分析、场景法等测试设计技术。"
    "你能根据需求描述，生成覆盖正向、边界、异常的测试用例，"
    "并标注优先级（P0/P1/P2）。"
    "回答专业、结构清晰、可直接用于测试工作。"
)

class InteractiveAnalyzer:
    """
    交互式需求分析器

    支持的命令：
    /analyze <需求文本>  — 分析新需求
    /cases               — 生成测试用例
    /refine <指令>       — 基于已有结果继续优化
    /code                — 生成 pytest 测试代码
    /history             — 查看对话历史
    /summary             — 对话摘要
    /export <路径>       — 导出对话记录为 JSON
    /help                — 显示帮助
    /quit                — 退出
    """
    def __init__(self):
        self.chat = client.chats.create(
            model=MODEL,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.2,
            ),
        )
        self.running = True

    def run(self):
        """运行交互式循环"""
        self._print_banner()
        while self.running:
            try:
                user_input = input("\n👤 你: ").strip()
                if not user_input:
                    continue
                self._handle_command(user_input)
            except KeyboardInterrupt:
                print("\n\n👋 再见！")
                break
            except EOFError:
                break

    def _print_banner(self):
        """打印欢迎横幅"""
        print("=" * 60)
        print("🧪  交互式需求分析对话系统")
        print("=" * 60)
        print("你可以：")
        print("  输入 /analyze <需求>  → 分析新需求")
        print("  输入 /cases           → 生成测试用例")
        print("  输入 /refine <指令>   → 优化补充")
        print("  输入 /code            → 生成 pytest 代码")
        print("  输入 /history         → 查看对话历史")
        print("  输入 /summary         → 对话摘要")
        print("  输入 /export <路径>   → 导出记录")
        print("  输入 /help            → 帮助")
        print("  输入 /quit            → 退出")
        print("  或直接输入任何需求/问题，自由对话")
        print("-" * 60)

    def _handle_command(self, user_input: str):
        """处理用户输入"""
        # 命令路由
        if user_input.startswith("/analyze "):
            requirement = user_input[len("/analyze "):]
            self._analyze(requirement)
        elif user_input == "/cases":
            self._generate_cases()
        elif user_input.startswith("/refine "):
            instruction = user_input[len("/refine "):]
            self._refine(instruction)
        elif user_input == "/code":
            self._generate_code()
        elif user_input == "/history":
            self._show_history()
        elif user_input == "/summary":
            self._show_summary()
        elif user_input.startswith("/export "):
            path = user_input[len("/export "):]
            self._export_history(path)
        elif user_input == "/help":
            self._print_banner()
        elif user_input == "/quit":
            self.running = False
            print("👋 再见！")
        else:
            # 自由对话
            self._chat(user_input)

    def _send(self, message: str) -> str:
        """发送消息并安全获取回复"""
        response = self.chat.send_message(message)
        return safe_text(response)

    def _send_stream(self, message: str) -> str:
        """流式发送消息"""
        full_text = ""
        print("\n🤖 AI: ", end="", flush=True)
        for chunk in self.chat.send_message_stream(message):
            text = safe_text(chunk)
            if text:
                print(text, end="", flush=True)
                full_text += text
        print()  # 换行
        return full_text

# ============================================================
# 命令实现
# ============================================================
    def _analyze(self, requirement: str):
            """分析需求"""
            prompt = f"""请分析以下需求，提取关键测试信息：

    需求：{requirement}

    请从以下几方面分析：
    1. 核心功能点识别
    2. 输入字段与约束条件
    3. 潜在风险点
    4. 建议的测试策略（功能/边界/异常/安全/性能）

    用结构化列表输出，方便后续生成测试用例。"""
            self._send_stream(prompt)

    def _generate_cases(self):
        """生成测试用例"""
        prompt = """基于以上需求分析，请生成完整的测试用例。

要求：
1. 覆盖正向（P0）、边界（P1）、异常（P1）
2. 每个用例包含：编号、标题、类型、优先级、步骤、预期结果
3. 每个数值约束生成「刚好满足」和「刚好不满足」的边界用例
4. 用 Markdown 表格格式输出"""
        self._send_stream(prompt)

    def _refine(self, instruction: str):
        """基于已有结果继续优化"""
        prompt = f"基于之前的分析和用例，请按以下要求优化：{instruction}"
        self._send_stream(prompt)

    def _generate_code(self):
        """生成 pytest 代码"""
        prompt = """基于以上测试用例，请生成 pytest 格式的自动化测试代码。

要求：
1. 使用 requests 库
2. 每个用例一个 test_ 方法
3. 包含 setup/teardown fixture
4. 异常用例标注 @pytest.mark.skip 并说明原因
5. 输出完整的 .py 文件代码"""
        self._send_stream(prompt)

    def _show_history(self):
        """显示对话历史"""
        history = self.chat.get_history()
        if not history:
            print("📭 暂无对话历史")
            return

        print(f"\n📋 对话历史（共 {len(history)} 条消息）：")
        print("-" * 60)
        for i, msg in enumerate(history):
            role_icon = "👤" if msg.role == "user" else "🤖"
            for part in safe_parts(msg):
                if part.text:
                    preview = part.text[:100].replace('\n', ' ')
                    print(f"  [{i}] {role_icon} {preview}...")
                    break
        print("-" * 60)

    def _show_summary(self):
        """显示对话摘要"""
        prompt = "请用 3-5 句话总结我们到目前为止的对话内容。"
        self._send_stream(prompt)

    def _export_history(self, path: str):
        """导出对话历史为 JSON"""
        history = self.chat.get_history()
        records = []
        for msg in history:
            text_parts = [
                part.text for part in safe_parts(msg) if part.text is not None
            ]
            records.append({
                "role": msg.role,
                "text": "\n".join(text_parts),
            })

        output = {
            "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
            "message_count": len(records),
            "messages": records,
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"✅ 对话记录已导出到: {path}")

    def _chat(self, message: str):
        """自由对话"""
        self._send_stream(message)

# ============================================================
# 实验 6：system_instruction 在多轮对话中的持续影响
# ============================================================

def system_instruction_behavior():
    """观察 system_instruction 在多轮对话中的持续性"""
    print("\n" + "=" * 60)
    print("🧪 实验 6：system_instruction 在多轮中的行为")
    print("=" * 60)

    # 对话 A：有角色设定
    chat_a = client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(
            system_instruction=(
                "你是一名测试工程师。每次回答的结尾，"
                "都要加上一句话：'以上建议来自测试工程师视角。'"
            ),
            temperature=0.2,
        ),
    )

    print("--- 对话 A（有 system_instruction）---")
    for i in range(3):
        resp = chat_a.send_message(f"问题 {i+1}：什么是边界值测试？用1句话")
        print(f"第{i+1}轮: {safe_text(resp)[:100]}...")

    # 对话 B：无角色设定
    chat_b = client.chats.create(
        model=MODEL,
        config=types.GenerateContentConfig(temperature=0.2),
    )

    print("\n--- 对话 B（无 system_instruction）---")
    for i in range(3):
        resp = chat_b.send_message(f"问题 {i+1}：什么是边界值测试？用1句话")
        print(f"第{i+1}轮: {safe_text(resp)[:100]}...")

    print("\n💡 结论：")
    print("   - system_instruction 在整个对话生命周期中持续生效")
    print("   - 每轮对话模型都会「看到」system_instruction")
    print("   - 多轮对话中不需要重复设置角色")

# ============================================================
# 入口
# ============================================================

if __name__ == "__main__":
    # analyzer = InteractiveAnalyzer()
    # analyzer.run()
    system_instruction_behavior()  # 新增
    print("\n✅ 多轮对话实验室全部完成！")

