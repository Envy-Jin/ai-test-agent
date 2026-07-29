"""
src/agent/doc_reader.py —— 需求文档读取器

Day 13 核心模块之一：负责读取需求文档，输出纯文本供后续分析。
支持 .txt 和 .md 格式。

注意：与 Day 6 的 requirement_parser.py（正则提取+CLI）职责不同，
本模块只做文件读取，不涉及内容解析。
"""

import os
from typing import Any
from logger_config import setup_logger

logger = setup_logger("ai_test_agent")

class DocReader:
    """
    需求文档读取器

    职责：
    1. 读取 .txt / .md 需求文档
    2. 验证文件存在和可读性
    3. 返回纯文本内容（去掉多余空行）
    4. 支持从文本字符串直接加载（用于交互式场景）

    使用示例：
        reader = DocReader()
        text = reader.parse_file("docs/requirements/login_req.md")
        print(f"读取了 {len(text)} 个字符")
    """

    # 支持的文件扩展名
    SUPPORTED_EXTENSIONS = {".txt", ".md", ".markdown"}

    def parse_file(self, file_path: str, encoding: str = "utf-8") -> str:
        """
        读取需求文档文件，返回纯文本

        设计约定：错误一律用异常抛出（FileNotFoundError / ValueError / UnicodeDecodeError），
        不返回 None。返回类型因此保证是 str，不会出现 str | None。

        Args:
            file_path: 文件路径
            encoding: 文件编码

        Returns:
            文件内容（纯文本，类型保证为 str）

        Raises:
            FileNotFoundError: 文件不存在
            ValueError: 不支持的文件格式
            UnicodeDecodeError: 编码无法解析
        """
        
        # 验证文件存在
        if not os.path.exists(file_path):
            logger.error(f"文件不存在: {file_path}")
            raise FileNotFoundError(f"需求文档不存在: {file_path}")

        # 验证扩展名
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in self.SUPPORTED_EXTENSIONS:
            logger.error(f"不支持的文件格式: {ext}")
            raise ValueError(f"不支持的文件格式: {ext}，支持 {self.SUPPORTED_EXTENSIONS}")

        logger.info(f"开始解析需求文档: {file_path}")

        try:
            with open(file_path, "r", encoding=encoding) as f:
                raw_text = f.read()
        except UnicodeDecodeError:
            # 尝试 gbk 编码（Windows 常见）
            logger.warning("UTF-8 解码失败，尝试 GBK")
            with open(file_path, "r", encoding="gbk") as f:
                raw_text = f.read()

        # 清洗文本：去掉多余空行，但保留段落间的一个空行
        lines = raw_text.split("\n")
        cleaned_lines = []
        prev_empty = False
        for line in lines:
            stripped = line.strip()
            if stripped:
                cleaned_lines.append(stripped)
                prev_empty = False
            elif not prev_empty:
                cleaned_lines.append("")
                prev_empty = True

        text = "\n".join(cleaned_lines).strip()

        logger.info(f"需求文档解析完成: {len(text)} 字符, {len(text.splitlines())} 行")
        return text

    def parse_text(self, text: str) -> str:
        """
        直接从文本字符串加载需求（用于交互式或 API 场景）

        Args:
            text: 需求文本

        Returns:
            清洗后的文本
        """
        logger.info(f"从文本加载需求: {len(text)} 字符")
        return text.strip()

    def get_file_info(self, file_path: str) -> dict[str, Any]:
        """
        获取需求文档的基本信息

        设计约定：与 parse_file 一致——文件不存在时直接抛 FileNotFoundError，
        返回 dict 不掺杂 error 兜底字段，类型干净。

        Returns:
            {"path": str, "size": int, "format": str, "lines": int}

        Raises:
            FileNotFoundError: 文件不存在
        """
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"需求文档不存在: {file_path}")

        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

        return {
            "path": file_path,
            "size": len(text),
            "format": os.path.splitext(file_path)[1].lower(),
            "lines": len(text.splitlines()),
        }

# ============================================================
# 自检
# ============================================================

def test_reader():
    """测试 DocReader"""
    import tempfile

    print("=" * 60)
    print("🧪 测试 DocReader")
    print("=" * 60)

    reader = DocReader()

    # 测试 1：创建临时 .md 文件并解析
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".md", delete=False, encoding="utf-8"
    ) as f:
        f.write("""# 用户登录功能需求

## 功能描述
用户可以通过手机号或邮箱登录系统。

## 输入字段
- 手机号：11位数字，以1开头
- 邮箱：标准邮箱格式
- 密码：不少于8位，必须包含数字和字母

## 约束条件
- 密码错误超过5次锁定账号30分钟
- 同一账号最多3个设备同时在线
- 连续登录失败需输入图形验证码
""")
        temp_path = f.name

    try:
        # 解析文件
        text = reader.parse_file(temp_path)
        print(f"解析成功: {len(text)} 字符")
        print(f"前 200 字符: {text[:200]}...")
        assert len(text) > 0, "❌ 解析结果为空"

        # 文件信息
        info = reader.get_file_info(temp_path)
        print(f"文件信息: {info}")

        # 文本直接加载
        text2 = reader.parse_text("简单的需求文本")
        assert text2 == "简单的需求文本", "❌ 文本加载失败"

        print("\n✅ DocReader 测试通过！")

    finally:
        os.unlink(temp_path)


if __name__ == "__main__":
    test_reader()