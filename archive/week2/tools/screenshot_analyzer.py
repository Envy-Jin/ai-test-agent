"""
src/agent/screenshot_analyzer.py —— UI 截图分析器

Day 10 核心实战：给一张 UI 截图，自动识别界面元素并生成 UI 测试用例
融合多模态输入 + Prompt 工程 + Pydantic Schema
"""

from __future__ import annotations

import os
from pathlib import Path

import PIL.Image
from dotenv import load_dotenv
from google import genai
from google.genai import types
from pydantic import ValidationError

from prompts import SYSTEM_UI_ANALYST, build_screenshot_prompt
from screenshot_schema import ScreenshotAnalysis

# os.environ["HTTPS_PROXY"] = "http://127.0.0.1:7890"

load_dotenv()

MODEL = "gemini-3.1-flash-lite"
MAX_IMAGE_SIZE = 1536
MAX_OUTPUT_TOKENS = 4096


class ScreenshotAnalysisError(Exception):
    """截图分析或 Schema 校验失败时抛出。"""

    def __init__(self, message: str, raw: str | None = None) -> None:
        super().__init__(message)
        self.raw = raw


def _escape_markdown_cell(text: str) -> str:
    """转义 Markdown 表格单元格中的特殊字符。"""
    return text.replace("|", "\\|").replace("\n", " ")


def _build_analyze_config() -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=SYSTEM_UI_ANALYST,
        temperature=0.2,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        response_mime_type="application/json",
        response_schema=ScreenshotAnalysis,
    )


class ScreenshotAnalyzer:
    """UI 截图分析器"""

    def __init__(
        self,
        model: str = MODEL,
        client: genai.Client | None = None,
        max_image_size: int = MAX_IMAGE_SIZE,
    ) -> None:
        self.model = model
        self.max_image_size = max_image_size
        self._client = client or self._create_client()

    @staticmethod
    def _create_client() -> genai.Client:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("未找到 GEMINI_API_KEY，请检查 .env 文件")
        return genai.Client(api_key=api_key)

    def _load_image(self, image_path: str | Path) -> PIL.Image.Image:
        """加载图片并按需缩放（限制长边，控制 Token 消耗）"""
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"截图文件不存在: {path}")

        with PIL.Image.open(path) as img:
            original_size = img.size
            image = img.convert("RGB")
            image.thumbnail(
                (self.max_image_size, self.max_image_size),
                PIL.Image.Resampling.LANCZOS,
            )
            if image.size != original_size:
                print(f"📐 图片缩放：{original_size} → {image.size}（{path.name}）")
            return image.copy()

    def _parse_response(self, raw: str) -> ScreenshotAnalysis:
        if not raw:
            raise ScreenshotAnalysisError("API 返回了空内容")
        try:
            return ScreenshotAnalysis.model_validate_json(raw)
        except ValidationError as exc:
            raise ScreenshotAnalysisError(
                "模型输出不符合 ScreenshotAnalysis Schema",
                raw=raw,
            ) from exc

    def analyze(self, image_path: str | Path) -> ScreenshotAnalysis:
        """
        分析 UI 截图，返回结构化分析结果

        Args:
            image_path: 截图文件路径

        Returns:
            ScreenshotAnalysis 对象

        Raises:
            FileNotFoundError: 图片不存在
            ScreenshotAnalysisError: Schema 校验失败
        """
        image = self._load_image(image_path)

        response = self._client.models.generate_content(
            model=self.model,
            contents=[build_screenshot_prompt(), image],
            config=_build_analyze_config(),
        )
        return self._parse_response(response.text or "")

    def to_markdown(self, analysis: ScreenshotAnalysis) -> str:
        """把分析结果转为 Markdown 报告"""
        lines = [f"# {_escape_markdown_cell(analysis.page_name)} - UI 测试分析报告\n"]
        lines.append(f"**页面描述**：{_escape_markdown_cell(analysis.page_description)}\n")

        if analysis.analysis_summary:
            lines.append(f"**分析摘要**：{_escape_markdown_cell(analysis.analysis_summary)}\n")

        lines.append("## 一、识别到的界面元素\n")
        lines.append("| ID | 类型 | 标识 | 位置 | 状态 |")
        lines.append("|----|------|------|------|------|")
        for el in analysis.elements:
            state = el.state or "—"
            lines.append(
                "| "
                f"{_escape_markdown_cell(el.element_id)} | "
                f"{_escape_markdown_cell(el.element_type)} | "
                f"{_escape_markdown_cell(el.label)} | "
                f"{_escape_markdown_cell(el.location)} | "
                f"{_escape_markdown_cell(state)} |"
            )

        lines.append(f"\n## 二、UI 测试用例（共 {len(analysis.test_cases)} 个）\n")
        lines.append("| ID | 类型 | 优先级 | 范围 | 标题 | 目标元素 | 预期结果 |")
        lines.append("|----|------|--------|------|------|----------|----------|")
        for tc in analysis.test_cases:
            lines.append(
                "| "
                f"{_escape_markdown_cell(tc.id)} | "
                f"{_escape_markdown_cell(tc.type)} | "
                f"{_escape_markdown_cell(tc.priority)} | "
                f"{_escape_markdown_cell(tc.test_scope)} | "
                f"{_escape_markdown_cell(tc.title)} | "
                f"{_escape_markdown_cell(tc.target_element)} | "
                f"{_escape_markdown_cell(tc.expected)} |"
            )

        lines.append("\n## 三、详细测试步骤\n")
        for tc in analysis.test_cases:
            lines.append(f"### {tc.id} - {tc.title}")
            lines.append(
                f"- **类型**：{tc.type} | **优先级**：{tc.priority} | "
                f"**范围**：{tc.test_scope} | **目标元素**：{tc.target_element}"
            )
            if tc.target_element_id:
                lines.append(f"- **元素 ID**：{tc.target_element_id}")
            lines.append("- **步骤**：")
            for index, step in enumerate(tc.steps, 1):
                lines.append(f"  {index}. {step}")
            lines.append(f"- **预期**：{tc.expected}\n")

        if analysis.visual_issues:
            lines.append("## 四、潜在视觉/可用性问题\n")
            for issue in analysis.visual_issues:
                lines.append(f"- ⚠️ {issue}")

        return "\n".join(lines)

    def save_to_markdown(self, analysis: ScreenshotAnalysis, filepath: str | Path) -> Path:
        """将分析结果保存为 Markdown 报告。"""
        output_path = Path(filepath)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.to_markdown(analysis), encoding="utf-8")
        return output_path

    def save_to_json(self, analysis: ScreenshotAnalysis, filepath: str | Path) -> Path:
        """将分析结果保存为 JSON 文件。"""
        output_path = Path(filepath)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(
            analysis.model_dump_json(indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        return output_path


# ============================================================
# 自检
# ============================================================
if __name__ == "__main__":
    print("🧪 测试 ScreenshotAnalyzer...\n")

    analyzer = ScreenshotAnalyzer()
    project_root = Path(__file__).resolve().parents[2]
    docs_dir = project_root / "docs"

    candidate_paths = [
        docs_dir / "images" / "leetcode.png",
        # docs_dir / "images" / "mock_login.png",
    ]
    image_path = next((p for p in candidate_paths if p.is_file()), None)

    if image_path is None:
        print("⚠️  请先运行 python src/agent/make_test_image.py 生成测试图片")
    else:
        print(f"📷 分析截图：{image_path}\n")
        analysis = analyzer.analyze(image_path)

        print(f"页面：{analysis.page_name}")
        print(f"描述：{analysis.page_description}")
        if analysis.analysis_summary:
            print(f"分析：{analysis.analysis_summary[:120]}...")

        print(f"\n识别到 {len(analysis.elements)} 个界面元素：")
        for el in analysis.elements:
            state_text = f"，{el.state}" if el.state else ""
            print(f"  - [{el.element_id}] [{el.element_type}] {el.label}（{el.location}{state_text}）")

        print(f"\n生成 {len(analysis.test_cases)} 个测试用例：")
        for tc in analysis.test_cases:
            print(f"  {tc.id} [{tc.priority}] [{tc.type}] [{tc.test_scope}] {tc.title}")

        if analysis.visual_issues:
            print(f"\n发现 {len(analysis.visual_issues)} 个潜在问题：")
            for issue in analysis.visual_issues:
                print(f"  ⚠️ {issue}")

        md_path = analyzer.save_to_markdown(analysis, docs_dir / "screenshot_analysis_report.md")
        json_path = analyzer.save_to_json(analysis, docs_dir / "screenshot_analysis_report.json")
        print(f"\n📄 报告已保存：{md_path}")
        print(f"📄 JSON 已保存：{json_path}")

        print("\n✅ ScreenshotAnalyzer 测试通过！")
