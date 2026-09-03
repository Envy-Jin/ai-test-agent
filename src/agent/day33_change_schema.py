"""Day 33 练习 1：变更解析（git diff → ChangeInfo）+ 用例注册表加载。

回归的输入侧有两样东西要先"结构化"：
  1. 代码变更（git diff）——unified diff 是确定性格式（---/+++ 文件头、@@ 位置头、
     +/- 行），用正则解析成 ChangeInfo（改了哪些文件、增删多少行、hunk 数、改动了
     哪些符号）。解析归代码：模型数行数会错（Day 31 铁律：模型不数数）。
  2. 现有用例清单（注册表 .json）——机器可读 → json.loads + Pydantic 校验直读
     （Day 30 教训：.json 不走 load_document）。

注意能力边界：行级 diff 能拿到统计与"新增符号"（如新文件里的 def），但看不到
"函数内部删了哪段校验"——后者要喂模型看原文（练习 2 的输入设计），规则基线也
必须扫行内容（练习 3 exp5）。今天对解析结果诚实：拿不到的就不假装拿得到。

实验（cd src/agent）：
  python -c "from day33_change_schema import exp1_parse_change_diff; exp1_parse_change_diff()"
  python -c "from day33_change_schema import exp2_load_case_registry; exp2_load_case_registry()"
  python day33_change_schema.py     # main 完成态：exp1 + exp2（零 API 冒烟）
"""

from __future__ import annotations

import json
import os
import re
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from pydantic import BaseModel, Field


# ── 路径基准钉 __file__（2026-08-28 规范：IDE/命令行/pytest 三种 cwd 都能命中）──
_BASE_DIR: str = os.path.dirname(os.path.abspath(__file__))
_ROOT: str = os.path.dirname(os.path.dirname(_BASE_DIR))  # src/agent → 项目根
DOCS_DIR: str = os.path.join(_ROOT, "docs")
CHANGE_DIFF_PATH: str = os.path.join(DOCS_DIR, "changes", "auth_refactor.diff")
CASE_REGISTRY_PATH: str = os.path.join(DOCS_DIR, "cases", "api_registry.json")


# ═══════════════════════════════════════════════════════
# Schema（练习 1：变更 + 用例注册表）
# ═══════════════════════════════════════════════════════
class ChangedFile(BaseModel):
    """一个变更文件的解析结果（确定性统计，不含语义判断）。"""

    path: str
    add_lines: int = 0
    del_lines: int = 0
    hunk_count: int = 0
    symbols: list[str] = Field(default_factory=list)  # 增删行里能抓到的 def/class 名


class ChangeInfo(BaseModel):
    """一次代码变更的解析结果（喂给模型的"变更摘要"事实层）。"""

    changed_files: list[ChangedFile]
    total_add: int = 0
    total_del: int = 0

    @property
    def paths(self) -> list[str]:
        return [f.path for f in self.changed_files]


class CaseEntry(BaseModel):
    """用例注册表条目（真实项目由测试资产管理 / pytest --collect-only 导出）。"""

    case_id: str
    title: str
    module: str          # 业务模块（login / orders）
    method: str
    path: str
    test_type: str       # 功能 / 参数缺失 / 错误凭据 / 越权访问
    priority: str        # 用例自身优先级（P0/P1/P2，与"回归档位"是两回事）
    pytest_ids: list[str]  # 对应生成套件的可执行 node id（变体逐条列出）


# ═══════════════════════════════════════════════════════
# git diff 解析（确定性：正则 + 行前缀判定，零 API）
# ═══════════════════════════════════════════════════════
_FILE_RE = re.compile(r"^\+\+\+\s+b/(.+)$")
_HUNK_RE = re.compile(r"^@@ -\d+(?:,\d+)? \+\d+(?:,\d+)? @@")
_SYMBOL_RE = re.compile(r"^[+-]\s*(?:(?:async\s+)?def\s+(\w+)|class\s+(\w+))")


def parse_git_diff(diff_text: str) -> ChangeInfo:
    """解析 unified diff 文本 → ChangeInfo。

    只认确定性结构：+++ b/<path> 开新文件、@@ 计 hunk、+/- 行计增删并尝试抓符号。
    "\\ No newline at end of file" 等以反斜杠开头的行不匹配 +/-，不会误计。
    """
    files: list[ChangedFile] = []
    current: ChangedFile | None = None
    for line in diff_text.splitlines():
        file_match = _FILE_RE.match(line)
        if file_match:
            if current is not None:
                files.append(current)
            current = ChangedFile(path=file_match.group(1))
            continue
        if current is None:
            continue
        if _HUNK_RE.match(line):
            current.hunk_count += 1
            continue
        if line.startswith("+") and not line.startswith("+++"):
            current.add_lines += 1
        elif line.startswith("-") and not line.startswith("---"):
            current.del_lines += 1
        else:
            continue  # 上下文行（空格开头）
        symbol_match = _SYMBOL_RE.match(line)
        if symbol_match:
            name: str = symbol_match.group(1) or symbol_match.group(2)
            if name not in current.symbols:
                current.symbols.append(name)
    if current is not None:
        files.append(current)
    return ChangeInfo(
        changed_files=files,
        total_add=sum(f.add_lines for f in files),
        total_del=sum(f.del_lines for f in files),
    )


# ═══════════════════════════════════════════════════════
# 用例注册表加载（.json 机器可读 → 确定性直读，Day 30/32 分派第三次落地）
# ═══════════════════════════════════════════════════════
def load_case_registry(path: str) -> list[CaseEntry]:
    with open(path, "r", encoding="utf-8") as f:
        raw = json.load(f)
    return [CaseEntry.model_validate(item) for item in raw]


def read_change_diff(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ═══════════════════════════════════════════════════════
# 实验
# ═══════════════════════════════════════════════════════
def exp1_parse_change_diff() -> None:
    """解析 auth_refactor.diff → 打印每个变更文件的确定性统计（零 API）。"""
    diff_text = read_change_diff(CHANGE_DIFF_PATH)
    info = parse_git_diff(diff_text)
    print(f"变更文件数: {len(info.changed_files)}  总增 {info.total_add} 行 / 总删 {info.total_del} 行")
    for f in info.changed_files:
        print(f"  {f.path}: +{f.add_lines} / -{f.del_lines} / hunks={f.hunk_count} / symbols={f.symbols}")


def exp2_load_case_registry() -> None:
    """读取 api_registry.json → 打印用例清单与 pytest node 总数（零 API）。"""
    entries = load_case_registry(CASE_REGISTRY_PATH)
    total_nodes = sum(len(c.pytest_ids) for c in entries)
    print(f"注册表用例数: {len(entries)}  对应 pytest node 总数: {total_nodes}")
    for c in entries:
        print(f"  {c.case_id} [{c.module}/{c.priority}] {c.title} -> {len(c.pytest_ids)} node(s)")




if __name__ == "__main__":
    # exp1_parse_change_diff()
    exp2_load_case_registry()
