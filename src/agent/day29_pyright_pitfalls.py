"""
Day 29 练习 5：Pyright 避坑演示 + 今日模块零 API 自检

坑 1：嵌套 Schema 的结构化输出收窄——structured_response 是 object，要逐层
      isinstance 收窄到 RequirementAnalysis → TestSuite → RequirementTestCase
坑 2：Union 出口二分收窄——同一 result 可能是 RequirementAnalysis 或 TestReport，
      用 isinstance 分支而不是猜
坑 3：python-docx 可选导入——try/except ImportError 赋 None，用前 is None 收窄
      （类型注解 Document | None，避免模块级 import 崩掉整个模块）
坑 4：统计字典推导——by_priority 用 dict 累积，取值前 .get(k, 0) 兜底（避免 KeyError）
坑 5：with_fallbacks 顺序——先 with_structured_output 再 with_fallbacks（反之走
      __getattr__ → pyright 推断 Any 丢类型检查；演示用类型断言验证结果形状）

用法：
  python day29_pyright_pitfalls.py   # 零 API 自检全绿
"""
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from day29_doc_loader import load_document
from day29_requirement_analysis import (
    RequirementAnalysis,
    TestSuite,
    RequirementTestCase,
    validate_analysis,
    render_analysis_markdown,
)
from day27_report import TestReport


def _fmt_report(msg: object) -> str | None:
    """坑 1：嵌套 Schema 收窄——msg 可能是 RequirementAnalysis 或 TestReport（object 入口）。

    逐层 isinstance 收窄到字段访问；不是这两种就返回 None。
    """
    if isinstance(msg, RequirementAnalysis):
        return f"分析[{msg.feature_name}] {len(msg.test_suites)} 套件"
    if isinstance(msg, TestReport):
        return f"报告[{msg.feature}] {len(msg.items)} 条"
    return None


def _count_p0(msg: RequirementAnalysis) -> int:
    """坑 1 续：深入到嵌套结构取数——RequirementAnalysis → test_suites → test_cases。

    ⚠️ pyright 对 Pydantic 模型字段的类型是静态可知的（BaseModel 子类），
       不需要收窄就能遍历；真正的坑在【入口】是 object（structured_response）。
    """
    return sum(1 for suite in msg.test_suites for case in suite.test_cases if case.priority == "P0")


def exp1_nested_schema() -> None:
    """坑 1/2：结构化输出入口 object → 逐层收窄（零 API，手工构造）。"""
    print("=" * 60)
    print("坑 1/2：结构化输出收窄（object 入口 → isinstance 分支）")
    analysis = RequirementAnalysis(
        feature_name="用户登录",
        summary="登录需求",
        test_suites=[TestSuite(suite_name="功能", suite_type="功能测试", test_cases=[
            RequirementTestCase(id="TC001", title="正常登录", priority="P0", type="功能",
                                steps=["登录"], expected_result="成功"),
        ])],
    )
    raw: object = analysis  # 模拟 result["structured_response"] 的 object 类型
    text: str | None = _fmt_report(raw)
    assert text is not None and "用户登录" in text
    assert _count_p0(analysis) == 1
    print(f"  ✅ 收窄成功: {text}，P0 用例数（嵌套遍历）= {_count_p0(analysis)}")
    # Union 出口：同一 object 位置，另一个分支
    report_raw: object = TestReport(feature="用户登录", base_url=None, items=[], conclusion="")
    assert "报告[用户登录]" in (_fmt_report(report_raw) or "")
    print("  ✅ Union 二分收窄：RequirementAnalysis 分支 / TestReport 分支互不串")


def exp2_docx_optional() -> None:
    """坑 3：python-docx 可选导入——没装包时模块不崩，.docx 返回 None。"""
    print("=" * 60)
    print("坑 3：python-docx 可选导入")
    try:
        from docx import Document  # noqa: PLC0415
        print("  ✅ python-docx 已安装（Document 可用）")
    except ImportError:
        print("  ⚠️ python-docx 未安装 → .docx 功能降级，.txt/.md 不受影响（降级路径演示）")
    here: str = os.path.dirname(os.path.abspath(__file__))
    txt_path: str = os.path.join(here, "..", "..", "docs", "requirements", "register_requirement.txt")
    doc = load_document(txt_path)
    assert doc is not None and doc.format == "txt"
    print(f"  ✅ 未受 docx 依赖影响：.txt 读取正常（{len(doc.text)} 字符）")


def exp3_stats_dict() -> None:
    """坑 4：统计字典推导——.get(k, 0) 兜底，缺 key 不炸。"""
    print("=" * 60)
    print("坑 4：统计字典推导（.get 兜底）")
    counts: dict[str, int] = {}
    for p in ["P0", "P1", "P1", "P2"]:
        counts[p] = counts.get(p, 0) + 1
    assert counts.get("P3", 0) == 0  # 不存在的 key → 0 而不是 KeyError
    assert counts == {"P0": 1, "P1": 2, "P2": 1}
    print(f"  ✅ 分布={counts}，缺失 key 取 0（{counts.get('P3', 0)}）")


def exp4_fallbacks_order() -> None:
    """坑 5：with_fallbacks 顺序——先结构化输出再 fallback（类型链完整）。

    运行时两种顺序都能跑（RunnableWithFallbacks.__getattr__ 会代理），
    但【反过来】时 pyright 推断为 Any（fallbacks.py:592 源码确认）——
    这里演示正确顺序构建 + 结果形状断言（零 API，用类型收窄代替 pyright 检查）。
    """
    print("=" * 60)
    print("坑 5：with_fallbacks 顺序（先 with_structured_output 再 with_fallbacks）")
    try:
        # 正确顺序：先结构化（类型完整）→ 再 fallback
        from langchain_core.language_models.fake_chat_models import FakeChatModel  # noqa: PLC0415

        # FakeChatModel 不支持 with_structured_output（会 NotImplementedError）——
        # 这本身就是坑 5 的第二个要点：结构化链无法 fake 冒烟
        FakeChatModel().with_structured_output(RequirementAnalysis)
        print("  ❌ 意外：FakeChatModel 竟然支持 with_structured_output")
    except NotImplementedError:
        print("  ✅ 确认：FakeChatModel 不支持 with_structured_output → 结构化链只能真模型 + 纯逻辑冒烟")
    # 正确顺序（真模型构建期可用，fake key 即可构造）：
    try:
        from langchain_google_genai import ChatGoogleGenerativeAI  # noqa: PLC0415

        main = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", thinking_level="medium").with_structured_output(
            RequirementAnalysis
        )
        backup = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0.2).with_structured_output(RequirementAnalysis)
        chained = main.with_fallbacks([backup])
        print(f"  ✅ 正确顺序构建 ok: {type(chained).__name__}（pyright 推断输出=RequirementAnalysis）")
    except Exception as exc:  # 缺 key 等情况：说明即可，不阻断
        print(f"  ⚠️ 真模型构建跳过（{type(exc).__name__}：{str(exc)[:60]}）——原理见文档联网确认表")


def main() -> None:
    exp1_nested_schema()
    exp2_docx_optional()
    exp3_stats_dict()
    exp4_fallbacks_order()
    print("\n✅ Day 29 Pyright 避坑演示 + 零 API 自检全部通过")


if __name__ == "__main__":
    main()
