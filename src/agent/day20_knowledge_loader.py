"""
Day 20 练习 1：知识库数据层 —— 多类型文档批量导入

设计智能测试知识库的数据层：
  - 三类文档：requirements（需求）/ test_cases（历史用例）/ bugs（Bug 报告）
  - 统一元数据体系：source（文件路径）+ doc_type（文档类型）+ category（分类）
  - ensure_sample_data()：目录缺失时自动生成示例数据（开箱即用）

数据目录（相对 src/agent/ 的 ../../docs/knowledge/）：
  docs/knowledge/
  ├── requirements/    # 需求文档（doc_type="requirement"）
  ├── test_cases/      # 历史测试用例（doc_type="test_case"）
  └── bugs/            # Bug 报告（doc_type="bug"）

⚠️ Pyright 注意事项：
  - Document.metadata 是 dict[str, Any]，取值用 str() 显式转换
  - 元数据字段统一用常量（DOC_TYPE_*），避免魔法字符串
  - 本脚本不调用 LLM/Embedding API，纯数据层

用法：直接运行跑全部实验，或在 main() 中注释掉不想跑的实验函数。
"""

import os
from pathlib import Path

from langchain_core.documents import Document

from dotenv import load_dotenv

load_dotenv()

# ═══════════════════════════════════════════════════════
# 模块级：常量 + 共享资源（所有实验共用）
# ═══════════════════════════════════════════════════════

KNOWLEDGE_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "docs", "knowledge")

# 文档类型常量（metadata 的 doc_type 字段值）
DOC_TYPE_REQUIREMENT: str = "requirement"
DOC_TYPE_TEST_CASE: str = "test_case"
DOC_TYPE_BUG: str = "bug"

# 子目录名 → doc_type 映射
TYPE_BY_DIR: dict[str, str] = {
    "requirements": DOC_TYPE_REQUIREMENT,
    "test_cases": DOC_TYPE_TEST_CASE,
    "bugs": DOC_TYPE_BUG,
}

# ═══════════════════════════════════════════════════════
# 示例数据生成（幂等：仅当目录缺失时创建，保证脚本开箱即用）
# ═══════════════════════════════════════════════════════

_SAMPLE_REQUIREMENT: str = """# 需求：用户登录功能

## 功能描述
用户可通过手机号+密码登录系统。

## 业务规则
- 手机号：11 位，以 1 开头
- 密码：8-20 位，包含字母和数字
- 连续输错 5 次锁定账号 30 分钟

## 异常场景
- 手机号格式错误：提示"手机号格式不正确"
- 密码错误：提示"密码错误"
- 账号锁定：提示"账号已锁定，请 30 分钟后再试"
"""

_SAMPLE_TEST_CASES: str = """# 历史测试用例：登录功能

## TC-001 正常登录（P0）
- 步骤：输入正确手机号和密码，点击登录
- 预期：登录成功，跳转首页

## TC-002 密码错误（P1）
- 步骤：输入正确手机号和错误密码
- 预期：提示"密码错误"，不跳转

## TC-003 手机号格式错误（P1）
- 步骤：输入非法手机号（如 12345）
- 预期：提示"手机号格式不正确"

## TC-004 连续输错锁定（P1）
- 步骤：连续输错密码 5 次
- 预期：账号锁定，提示联系客服
"""

_SAMPLE_BUGS: str = """# Bug 报告：登录模块

## BUG-001 登录后页面跳转错误（严重）
- 现象：手机号+密码正确登录后，跳转到空白页
- 复现：输入正确账号，点击登录，页面空白
- 影响：用户无法正常使用
- 状态：已修复

## BUG-002 验证码过期提示不明确（一般）
- 现象：验证码过期后提示"系统错误"
- 期望：应提示"验证码已过期，请重新获取"
- 状态：待修复

## BUG-003 密码错误次数计数异常（严重）
- 现象：输错 4 次后，第 5 次输入正确密码仍登录失败
- 期望：第 5 次输入正确密码应登录成功
- 状态：已修复
"""

_SAMPLE_BY_SUBDIR: dict[str, str] = {
    "requirements": _SAMPLE_REQUIREMENT,
    "test_cases": _SAMPLE_TEST_CASES,
    "bugs": _SAMPLE_BUGS,
}

def ensure_sample_data(root_dir: str = KNOWLEDGE_DIR) -> None:
    """幂等：若 knowledge 目录或子目录缺失，自动创建示例数据文件。

    已存在的目录不覆盖，方便用户后续放入真实文档。
    """
    for subdir, content in _SAMPLE_BY_SUBDIR.items():
        target_dir: Path = Path(root_dir) / subdir
        target_dir.mkdir(parents=True, exist_ok=True)
        sample_file: Path = target_dir / "sample.md"
        if not sample_file.exists():
            sample_file.write_text(content, encoding="utf-8")
            print(f"  📄 已生成示例: {sample_file.relative_to(Path(root_dir).parent)}")
        # 目录为空但 sample.md 已存在 → 说明用户已有数据，跳过


# ═══════════════════════════════════════════════════════
# KnowledgeLoader：按类型加载文档
# ═══════════════════════════════════════════════════════

def load_directory(directory: str, doc_type: str, category: str = "general") -> list[Document]:
    """加载目录下所有 .txt / .md 文件为带 doc_type 标签的 Document 列表。

    Args:
        directory: 子目录路径（如 docs/knowledge/bugs）
        doc_type: 文档类型（DOC_TYPE_* 常量）
        category: 功能分类（默认 "general"，可按需细分）

    Returns:
        带 metadata 的 Document 列表（source + doc_type + category）
    """
    docs: list[Document] = []
    for filepath in Path(directory).iterdir():
        if filepath.suffix not in (".txt", ".md"):
            continue
        with open(filepath, "r", encoding="utf-8") as f:
            content: str = f.read()
        docs.append(
            Document(
                page_content=content,
                metadata={
                    "source": str(filepath),
                    "doc_type": doc_type,
                    "category": category,
                },
            )
        )
    return docs

def load_knowledge_base(root_dir: str = KNOWLEDGE_DIR) -> list[Document]:
    """加载整个知识库（三类文档），按子目录名自动标注 doc_type。

    Returns:
        全部 Document 列表，每个都带 doc_type 元数据
    """
    all_docs: list[Document] = []
    for subdir, doc_type in TYPE_BY_DIR.items():
        dir_path: str = os.path.join(root_dir, subdir)
        if not os.path.isdir(dir_path):
            continue
        docs: list[Document] = load_directory(dir_path, doc_type)
        print(f"  📂 {subdir}（{doc_type}）: {len(docs)} 个文档")
        all_docs.extend(docs)
    return all_docs


# ═══════════════════════════════════════════════════════
# 实验 1：单类型加载 + 查看元数据
# ═══════════════════════════════════════════════════════

def exp1_single_type() -> None:
    """实验 1：加载 bugs 目录，查看 doc_type 元数据"""
    print("=" * 60)
    print("实验 1：单类型加载（bugs）")
    print("=" * 60)

    bugs_dir: str = os.path.join(KNOWLEDGE_DIR, "bugs")
    docs: list[Document] = load_directory(bugs_dir, DOC_TYPE_BUG, category="login")

    print(f"加载了 {len(docs)} 个 Bug 文档\n")
    for i, doc in enumerate(docs):
        source: str = str(doc.metadata.get("source", "unknown"))
        doc_type: str = str(doc.metadata.get("doc_type", "unknown"))
        print(f"  [{i}] {os.path.basename(source)}")
        print(f"      doc_type={doc_type}, category={doc.metadata.get('category')}")
        print(f"      内容预览: {doc.page_content[:60].replace(chr(10), ' ')}...")

    print(f"\n💡 metadata 三件套：source（溯源） + doc_type（过滤） + category（细分类）")


# ═══════════════════════════════════════════════════════
# 实验 2：加载整个知识库（三类文档）
# ═══════════════════════════════════════════════════════

def exp2_load_all() -> None:
    """实验 2：批量加载全部三类文档，统计各类型数量"""
    print("\n" + "=" * 60)
    print("实验 2：加载整个知识库")
    print("=" * 60)

    all_docs: list[Document] = load_knowledge_base()

    # 按 doc_type 统计
    type_count: dict[str, int] = {}
    for doc in all_docs:
        doc_type: str = str(doc.metadata.get("doc_type", "unknown"))
        type_count[doc_type] = type_count.get(doc_type, 0) + 1

    print(f"\n📊 知识库总量: {len(all_docs)} 个文档")
    for doc_type, count in sorted(type_count.items()):
        print(f"   {doc_type}: {count} 个")

    # 验证：所有文档都有 doc_type
    missing: int = sum(1 for d in all_docs if "doc_type" not in d.metadata)
    print(f"\n✅ 缺少 doc_type 标签的文档数: {missing}（应为 0）")


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    # ensure_sample_data()
    # exp1_single_type()
    exp2_load_all()

    print("\n💡 小结：")
    print("  - load_directory(dir, doc_type, category) 按类型加载并打标签")
    print("  - load_knowledge_base() 一键加载全部三类文档")
    print("  - metadata 三件套（source/doc_type/category）是检索过滤的基础")
    print("  - 下一步：给索引构建加锁（并发安全），并支持按 doc_type 过滤检索")
