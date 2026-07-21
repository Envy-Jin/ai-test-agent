"""
src/agent/multimodal_assistant.py —— 多模态测试助手

Day 10 综合实战：融合多模态 + 流式 + Prompt 工程 + Schema
能力：
1. 截图分析 → UI 测试用例（结构化输出）
2. 流式生成测试用例（实时打印）
3. 截图 + 文字混合指令
4. Markdown 报告导出
"""

from google import genai
from google.genai import types
import os
import json
import time
from dotenv import load_dotenv
import PIL.Image
from screenshot_schema import ScreenshotAnalysis
from case_schema import TestCaseCollection


# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

load_dotenv()
_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

MODEL = "gemini-3.1-flash-lite"

SYSTEM_PROMPT = (
    "你是一名有 10 年经验的资深软件测试工程师，"
    "精通 UI 测试、功能测试、边界值分析。"
    "你能根据截图和文字描述，生成全面的测试用例。"
)

class MultimodalTestAssistant:
    """多模态测试助手"""

    def __init__(self, model: str = MODEL):
        self.model = model

    # ============================================================
    # 能力 1：截图分析（结构化输出，非流式）
    # ============================================================

    def analyze_screenshot(self, image_path: str) -> ScreenshotAnalysis:
        """分析 UI 截图，返回结构化结果（仅允许 PNG/JPEG/WebP 图片）"""
        # 校验图片格式
        allowed_exts = {'.png', '.jpg', '.jpeg', '.webp'}
        ext = os.path.splitext(image_path)[1].lower()
        if ext not in allowed_exts:
            raise ValueError(
                f"仅支持 PNG、JPEG、WebP 格式的图片，当前为 {ext or '无扩展名'}"
            )

        image = self._load_image(image_path)

        prompt = """请分析这张应用界面截图：
1. 识别页面名称和功能
2. 列出所有界面元素
3. 生成 UI 测试用例（正向/边界/异常/视觉/交互）
4. 指出潜在的视觉和可用性问题

每个输入框至少 1 个边界用例，每个按钮至少 1 个正向用例。"""

        response = _client.models.generate_content(
            model=self.model,
            contents=[prompt, image],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=ScreenshotAnalysis,
            ),
        )
        return ScreenshotAnalysis.model_validate_json(response.text or "")
 

    # ============================================================
    # 能力 2：流式生成测试用例（实时打印 + 最终解析）
    # ============================================================

    def stream_generate_cases(self, requirement: str, verbose: bool = True) -> TestCaseCollection:
        """
        流式生成测试用例，实时打印并最终返回结构化对象

        Args:
            requirement: 需求文本
            verbose: 是否实时打印

        Returns:
            TestCaseCollection 对象
        """
        prompt = f"""请为以下需求生成测试用例，覆盖正向、边界、异常场景。

需求：{requirement}

要求：
- 每个数值约束生成「刚好满足」和「刚好不满足」的边界用例
- 异常用例覆盖空值、格式错误、超长输入
- 正向用例标 P0，边界和异常标 P1"""

        full_text = ""
        for chunk in _client.models.generate_content_stream(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.2,
                response_mime_type="application/json",
                response_schema=TestCaseCollection,
            ),
        ):
            if chunk.text:
                if verbose:
                    print(chunk.text, end="", flush=True)
                full_text += chunk.text

        return TestCaseCollection.model_validate_json(full_text)

    # ============================================================
    # 能力 3：截图 + 文字混合指令（自由文本输出）
    # ============================================================

    def ask_with_image(self, image_path: str, question: str) -> str | None:
        """
        给一张截图 + 一个问题，返回文本回答

        Args:
            image_path: 截图路径
            question: 自然语言问题

        Returns:
            文本回答
        """
        image = self._load_image(image_path)
        response = _client.models.generate_content(
            model=self.model,
            contents=[question, image],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.3,
            ),
        )
        return response.text

    # ============================================================
    # 能力 4：流式自由问答（打字机效果）
    # ============================================================

    def stream_chat(self, question: str):
        """流式自由问答，实时打印"""
        for chunk in _client.models.generate_content_stream(
            model=self.model,
            contents=question,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                temperature=0.4,
            ),
        ):
            if chunk.text:
                print(chunk.text, end="", flush=True)
        print()  # 最后换行

    # ============================================================
    # 辅助方法
    # ============================================================

    def _load_image(self, image_path: str) -> PIL.Image.Image:
        """加载并按需缩放图片"""
        image = PIL.Image.open(image_path)
        max_width = 1536
        if image.width > max_width:
            ratio = max_width / image.width
            new_size = (max_width, int(image.height * ratio))
            image = image.resize(new_size, PIL.Image.Resampling.LANCZOS)
        return image

    def export_report(self, analysis: ScreenshotAnalysis, output_path: str):
        """导出截图分析报告为 Markdown"""
        lines = [f"# {analysis.page_name} - UI 测试分析报告\n"]
        lines.append(f"**页面描述**：{analysis.page_description}\n")
        lines.append(f"**生成时间**：{time.strftime('%Y-%m-%d %H:%M:%S')}\n")

        lines.append("## 一、界面元素\n")
        lines.append("| 类型 | 标识 | 位置 |")
        lines.append("|------|------|------|")
        for el in analysis.elements:
            lines.append(f"| {el.element_type} | {el.label} | {el.location} |")

        lines.append(f"\n## 二、测试用例（{len(analysis.test_cases)} 个）\n")
        for tc in analysis.test_cases:
            lines.append(f"### {tc.id} {tc.title}")
            lines.append(f"- 类型：{tc.type} | 优先级：{tc.priority} | 目标：{tc.target_element}")
            lines.append("- 步骤：")
            for i, s in enumerate(tc.steps, 1):
                lines.append(f"  {i}. {s}")
            lines.append(f"- 预期：{tc.expected}\n")

        if analysis.visual_issues:
            lines.append("## 三、潜在问题\n")
            for issue in analysis.visual_issues:
                lines.append(f"- ⚠️ {issue}")

        with open(output_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print(f"📄 报告已导出：{output_path}")


# ============================================================
# 自检：演示四种能力
# ============================================================
if __name__ == "__main__":
    assistant = MultimodalTestAssistant()

    print("=" * 60)
    print("🧪 多模态测试助手 - 能力演示")
    print("=" * 60)

    # 能力 1：截图分析
    image_path = "docs/images/mock_login.png"
    if os.path.exists(image_path):
        print("\n--- 能力 1：截图分析 ---")
        analysis = assistant.analyze_screenshot(image_path)
        print(f"页面：{analysis.page_name}，元素：{len(analysis.elements)} 个，用例：{len(analysis.test_cases)} 个")
        assistant.export_report(analysis, "docs/multimodal_report.md")

    # 能力 2：流式生成测试用例
    print("\n--- 能力 2：流式生成测试用例 ---")
    collection = assistant.stream_generate_cases(
        "购物车功能：支持添加商品、修改数量、删除商品，数量范围1-99"
    )
    print(f"\n✅ 生成 {len(collection.test_cases)} 个用例：{collection.feature_name}")

    # 能力 3：截图 + 文字混合
    if os.path.exists(image_path):
        print("\n--- 能力 3：截图 + 文字混合指令 ---")
        answer = assistant.ask_with_image(
            image_path,
            "这个界面的「获取验证码」按钮，应该测试哪些场景？列出 3 个。"
        )
        print(answer)

    # 能力 4：流式自由问答
    print("\n--- 能力 4：流式自由问答 ---")
    assistant.stream_chat("用 3 句话解释什么是「探索性测试」？")

    print("\n✅ 多模态测试助手演示完成！")