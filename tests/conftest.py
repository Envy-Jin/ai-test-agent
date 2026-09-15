# FILE: conftest.py —— 真实落地到 ai_test_agent/tests/conftest.py
"""Day 39：tests/ 共享夹具（pytest **自动加载**，无需 import）。

为什么需要 conftest：
  ① **路径桥**：让 `from cli import cli`（项目根）与 `from day35_scenario import ...`
     （src/agent）在任何调用姿势下都能解析——pyproject 的 `pythonpath` 只覆盖 src / src-agent，
     项目根靠 pytest 的 rootdir 插入；这里显式补一遍，跑法换 cwd 也不怕。
  ② **共享夹具**：把"每个测试文件都要写一遍"的东西收敛到一处。

⚠️ conftest.py 自身**不会**被当作测试文件收集；它只在收集阶段被 pytest 导入。
⚠️ 夹具参数在测试函数上要写注解（如 `login_blueprint: list[StageSpec]`）——
   pyright 不认识 pytest 的注入魔法，注解由你给，它才好做静态检查。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_ROOT: Path = Path(__file__).resolve().parents[1]
_AGENT: Path = _ROOT / "src" / "agent"
for _candidate in (str(_ROOT), str(_AGENT)):
    if _candidate not in sys.path:
        sys.path.insert(0, _candidate)


@pytest.fixture(scope="session")
def login_blueprint():
    """LOGIN 场景的 9 段蓝图（session 级：纯构造，构建一次够用）。

    ⚠️ 不写返回注解：`StageSpec` 在函数体内导入，写注解就得把它提到模块顶层；
       留空由 pyright 从 return 语句推断（项目规范：构建函数返回注解留空）。
    """
    from day35_scenario import LOGIN_SCENARIO, build_blueprint

    return build_blueprint(LOGIN_SCENARIO)
