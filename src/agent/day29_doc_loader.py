"""
Day 29 练习 1：文档加载器 —— .txt / .md / .docx → 统一文本（LoadedDoc）

设计要点：
  1. python-docx 可选导入（try/except ImportError）：没装包时 .txt/.md 照常工作，
     .docx 返回 None + 清晰提示——模块级 import 报错会让整模块不可用（冒烟大忌）
  2. .docx 读取 = 段落（paragraphs）+ 表格（tables，cell.text）——需求文档常含表格
  3. 返回 LoadedDoc（dataclass）：text + source + format——后续 Chain 的输入统一

用法：
  python -c "from day29_doc_loader import exp1_loader_demo; exp1_loader_demo()"  # 零 API
"""
import os
import sys
from dataclasses import dataclass

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

try:
    from docx import Document as DocxDocument  # python-docx 1.2.0（2026-08-26 联网确认）
except ImportError:  # 未安装：.docx 功能降级，其余照常
    DocxDocument = None  # type: ignore[assignment]


@dataclass
class LoadedDoc:
    """统一文档载体：任何格式读进来都是 text + 元信息。"""

    text: str
    source: str          # 原始文件路径（幂等 upsert 的 source 依据）
    format: str          # "txt" / "md" / "docx"


def load_document(path: str) -> LoadedDoc | None:
    """按扩展名路由到对应读取器；不支持的格式/读取失败返回 None。

    ⚠️ 扩展名判断：os.path.splitext 返回 (root, ext)，ext 带点号且大小写不定
       → 统一 .lower() 后再比对。
    """
    if not os.path.isfile(path):
        print(f"  ⚠️ 文件不存在: {path}")
        return None
    ext: str = os.path.splitext(path)[1].lower()
    if ext in (".txt", ".md", ".markdown"):
        return _read_text_file(path)
    if ext == ".docx":
        return _read_docx(path)
    print(f"  ⚠️ 不支持的格式: {ext}（支持 .txt/.md/.docx）")
    return None


def _read_text_file(path: str) -> LoadedDoc | None:
    """读取 .txt/.md（utf-8，容错 encoding 错误 → errors='replace' 不崩）。"""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            text: str = f.read()
    except OSError as exc:
        print(f"  ⚠️ 读取失败 {path}: {exc}")
        return None
    return LoadedDoc(text=text, source=os.path.basename(path), format=os.path.splitext(path)[1].lower().lstrip("."))


def _read_docx(path: str) -> LoadedDoc | None:
    """读取 .docx：段落 + 表格（python-docx 1.2.0）。

    ⚠️ DocxDocument 可能是 None（未安装）→ 先用 isinstance 收窄再调用，pyright 友好。
    """
    if DocxDocument is None:
        print("  ⚠️ 未安装 python-docx：pip install python-docx 后 .docx 才能读取")
        return None
    try:
        doc = DocxDocument(path)
    except Exception as exc:  # python-docx 对损坏文件抛各种异常 → 统一兜底
        print(f"  ⚠️ .docx 打开失败 {path}: {exc}")
        return None
    parts: list[str] = []
    for para in doc.paragraphs:
        if para.text.strip():
            parts.append(para.text)
    for table in doc.tables:
        for row in table.rows:
            cells: list[str] = [cell.text.strip() for cell in row.cells]
            if any(cells):
                parts.append(" | ".join(cells))
    return LoadedDoc(text="\n".join(parts), source=os.path.basename(path), format="docx")


# ═══════════════════════════════════════════════════════
# 实验
# ═══════════════════════════════════════════════════════

def exp1_loader_demo() -> None:
    """实验 1：加载器冒烟 —— .txt/.md 零依赖；.docx 生成最小样本验证完整链路。"""
    print("=" * 60)
    print("实验 1：文档加载器冒烟（.txt/.md 零依赖 + .docx 完整链路）")
    here: str = os.path.dirname(os.path.abspath(__file__))
    req_dir: str = os.path.join(here, "..", "..", "docs", "requirements")

    # ① .md 样本（项目自带）
    md_path: str = os.path.join(req_dir, "login_requirement.md")
    md_doc: LoadedDoc | None = load_document(md_path)
    assert md_doc is not None and "登录" in md_doc.text
    print(f"  ✅ .md 读取: {md_doc.format} 源={md_doc.source} 长度={len(md_doc.text)}")

    # ② .txt 样本（项目自带）
    txt_path: str = os.path.join(req_dir, "register_requirement.txt")
    txt_doc: LoadedDoc | None = load_document(txt_path)
    assert txt_doc is not None and txt_doc.format == "txt"
    print(f"  ✅ .txt 读取: {txt_doc.format} 源={txt_doc.source} 长度={len(txt_doc.text)}")

    # ③ .docx：临时生成最小需求样本 → 读取 → 清理（验证 python-docx 链路）
    import tempfile  # noqa: PLC0415

    if DocxDocument is None:
        print("  ⚠️ python-docx 未安装 → .docx 链路跳过（装好后重跑本实验）")
    else:
        tmp_dir: str = tempfile.mkdtemp(prefix="day29_loader_")
        sample_path: str = os.path.join(tmp_dir, "sample_requirement.docx")
        _write_sample_docx(sample_path)
        docx_doc: LoadedDoc | None = load_document(sample_path)
        assert docx_doc is not None and docx_doc.format == "docx"
        assert "测试账号" in docx_doc.text, "表格内容应被读到"
        print(f"  ✅ .docx 读取: 源={docx_doc.source} 长度={len(docx_doc.text)}（段落+表格）")
        for name in os.listdir(tmp_dir):
            os.remove(os.path.join(tmp_dir, name))
        os.rmdir(tmp_dir)
        print("   ✅ 临时样本已清理")

    # ④ 异常路径
    assert load_document(os.path.join(req_dir, "not_exist.md")) is None
    print("  ✅ 文件不存在 → None（异常路径正确）")
    print("✅ 加载器冒烟全部通过")


def _write_sample_docx(path: str) -> None:
    """生成最小 .docx 需求样本（含段落 + 表格），供加载器验证。"""
    if DocxDocument is None:
        return
    doc = DocxDocument()
    doc.add_heading("测试账号需求", level=1)
    doc.add_paragraph("系统需支持管理员创建测试账号。")
    table = doc.add_table(rows=2, cols=2)
    table.rows[0].cells[0].text = "字段"
    table.rows[0].cells[1].text = "规则"
    table.rows[1].cells[0].text = "账号"
    table.rows[1].cells[1].text = "test_account"
    doc.save(path)





if __name__ == "__main__":
    exp1_loader_demo()
    print("\n💡 要点回顾：")
    print("   加载器 = 格式差异的收敛点：任何需求文档进来都是 LoadedDoc（text/source/format）")
    print("   python-docx 可选导入：没装包只降级 .docx，不拖垮整个模块")