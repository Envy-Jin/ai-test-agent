"""Day 33 练习 6：Pyright 避坑演示 + 今日模块零 API 自检。

坑清单（详情与正确写法在本文件各函数注释里）：
  坑 1  ET.find() 返回 Element | None —— 判空后收窄再取属性
  坑 2  dict.get(key) 不传默认值才返回 V | None（typeshed 重载）——
       把 XML time 转 float 时用 (x or 0.0) 兜底
  坑 3  结构化输出 raw: object —— isinstance 收窄链（Day 29 坑 1 模式）
  坑 4  模板塞代码/JSON 用 str.replace，不用 .format/f-string（花括号冲突）
  坑 5  subprocess stdout 是 bytes | None —— or b"" 后 decode
  坑 6  Literal 状态判定用显式 == 展开，别依赖 in (tuple) 的窄化

实验（cd src/agent）：
  python -c "from day33_pyright_pitfalls import exp8_self_check_zero_api; exp8_self_check_zero_api()"
  python day33_pyright_pitfalls.py
"""
from __future__ import annotations

import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

# 假 key：仅构造期校验，零 API（冒烟规范）
os.environ.setdefault("GEMINI_API_KEY", "smoke-fake-key")

import day33_change_schema as cs   # noqa: E402
import day33_regression_analyzer as ra  # noqa: E402
import day33_report_pipeline as rp  # noqa: E402

# ── 坑 1/2 现场（正确写法，pyright 0 errors）──
#   elem = testcase.find("failure")      # Element | None
#   if elem is not None:                 # 判空收窄
#       msg = elem.attrib.get("message")  # str | None（不传默认值）
#       text = msg or ""                  # 兜底
#   见 day33_report_pipeline._failure_message / parse_junit_xml

# ── 坑 3 现场 ──
#   def parse(raw: object) -> Plan | None:
#       if isinstance(raw, Plan): return raw
#       if isinstance(raw, dict): return Plan.model_validate(raw)
#       return None
#   见 ra.parse_regression_plan

# ── 坑 4 现场 ──
#   prompt = TEMPLATE.replace("{data}", json_text)   # 安全
#   # prompt = TEMPLATE.format(data=json_text)        # json 里的 {} 会炸
#   见 ra._render_regression_input

# ── 坑 5 现场 ──
#   proc = subprocess.run(argv, capture_output=True)
#   tail = (proc.stdout or b"").decode("utf-8", errors="replace")
#   见 rp.run_regression_subset

# ── 坑 6 现场 ──
#   if o.status == "failed" or o.status == "error":   # 显式展开
#   见 rp.find_defects


# ═══════════════════════════════════════════════════════
# 实验：零 API 全链路自检（全内存样例，不碰文件/API）
# ═══════════════════════════════════════════════════════
_SAMPLE_DIFF = """diff --git a/src/agent/auth_common.py b/src/agent/auth_common.py
new file mode 100644
--- /dev/null
+++ b/src/agent/auth_common.py
@@ -0,0 +1,2 @@
+def require_auth(auth_header: str) -> str | None:
+    return None
diff --git a/src/agent/day30_mock_api.py b/src/agent/day30_mock_api.py
--- a/src/agent/day30_mock_api.py
+++ b/src/agent/day30_mock_api.py
@@ -10,7 +10,6 @@
-        if auth != "Bearer demo-token-123":
-            return None
         return None
"""

_SAMPLE_REGISTRY = """[
  {"case_id": "TC001", "title": "正常登录", "module": "login", "method": "POST",
   "path": "/api/login", "test_type": "功能", "priority": "P0",
   "pytest_ids": ["outputs/generated_tests/test_api_suite.py::TestApiLogin::test_normal"]},
  {"case_id": "TC005", "title": "越权访问", "module": "orders", "method": "GET",
   "path": "/api/orders", "test_type": "越权访问", "priority": "P0",
   "pytest_ids": ["outputs/generated_tests/test_api_suite.py::TestApiOrders::test_unauthorized[headers0]"]}
]"""

_SAMPLE_JUNIT = """<?xml version="1.0" encoding="utf-8"?>
<testsuites><testsuite name="pytest" errors="0" failures="1" skipped="0" tests="2" time="0.5">
  <testcase classname="test_api_suite.TestApiLogin" name="test_normal" time="0.080"/>
  <testcase classname="test_api_suite.TestApiOrders" name="test_unauthorized[headers0]" time="0.088">
    <failure message="AssertionError: 期望 401 实际 200"/>
  </testcase>
</testsuite></testsuites>"""


def exp8_self_check_zero_api() -> None:
    """零 API 全链路：变更解析 → 计划收窄 → junit 解析/统计/报告渲染（内存样例）。"""
    import json

    # 1. 变更解析（cs）
    change = cs.parse_git_diff(_SAMPLE_DIFF)
    assert len(change.changed_files) == 2, "变更解析应得 2 个文件"
    print(f"✅ [cs] parse_git_diff -> {len(change.changed_files)} 文件, total_add={change.total_add}")

    # 2. 计划收窄（ra）
    plan_raw: dict[str, object] = {
        "change_summary": "自检样例",
        "impacted_modules": ["login", "orders"],
        "must_regression": [{"case_id": "TC001", "module": "login", "reason": "自检"}],
        "should_regression": [],
        "can_skip": [],
        "need_add": [],
    }
    plan = ra.parse_regression_plan(plan_raw)
    assert plan is not None, "计划收窄失败"
    print(f"✅ [ra] parse_regression_plan -> must={plan.case_ids('must')}")

    # 3. junit 解析/统计/渲染（rp，registry 用内存 JSON 构造）
    registry = [cs.CaseEntry.model_validate(item) for item in json.loads(_SAMPLE_REGISTRY)]
    outcomes = rp.parse_junit_xml(_SAMPLE_JUNIT)
    stats = rp.summarize(outcomes)
    defects = rp.find_defects(outcomes)
    assert stats.total == 2 and stats.failed == 1, "统计应与 XML 一致"
    conclusion = rp.rule_conclusion(stats, defects, registry)
    md = rp.render_markdown_report(
        "自检场景", change, plan, registry,
        outcomes, stats, defects, conclusion,
    )
    assert "## 执行摘要" in md and "缺陷列表" in md, "报告应含关键段落"
    print(f"✅ [rp] junit -> total={stats.total} failed={stats.failed} 通过率={stats.pass_rate}%")
    print(f"✅ [rp] 报告渲染 OK（{len(md)} 字符），结论: {conclusion[:40]}...")
    print("=" * 56)
    print("零 API 自检全绿：今日 3 个功能模块 import + 全链路函数可用")


def main() -> None:
    exp8_self_check_zero_api()


if __name__ == "__main__":
    main()
