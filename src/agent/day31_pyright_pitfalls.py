"""
Day 31 练习 5：Pyright 避坑演示 + 今日模块零 API 自检

坑 1：Literal 枚举 → metadata str——chroma metadata 只收 str/int/float/bool，
      status/severity/bug_type 是 Literal 类型，入库前显式 str()（不转 pyright 报类型不兼容）
坑 2：Chroma get() 返回 dict[str, object]——ids 取值后 isinstance 收窄为 list[str]
坑 3：私有属性 _vectorstore 访问——项目先例用 # type: ignore[attr-defined]
      （day21_kb_persist.py:121/203）；不 ignore 的话 pyright 报 reportPrivateUsage
坑 4：聚合字典推导——by_severity 用 .get(k, 0) 兜底（Day 29 坑 4 延续）
坑 5：嵌套 Schema 收窄——BugAnalysis → test_cases_to_add → BugTestCase 逐层遍历取数

用法：
  python day31_pyright_pitfalls.py   # 零 API 自检全绿
"""
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from day31_bug_analyzer import (
    BugAnalysis,
    BugTestCase,
    aggregate_stats,
    split_bug_reports,
    validate_bug_analysis,
)


def exp1_literal_to_str() -> None:
    """坑 1：Literal → str（metadata 只收 str/int/float/bool）。"""
    print("=" * 60)
    print("坑 1：Literal 枚举 → metadata str")
    a = BugAnalysis(
        bug_id="T1", title="t", bug_summary="s", bug_type="安全漏洞", severity="严重",
        root_cause_analysis="r", reproduce_steps=["1"], test_cases_to_add=[],
        regression_scope=["x"], prevention="p",
    )
    metadata: dict[str, str] = {
        "status": str(a.status),      # Literal['待修复'] → "待修复"（str 显式转换）
        "severity": str(a.severity),
        "bug_type": str(a.bug_type),
    }
    assert metadata == {"status": "待修复", "severity": "严重", "bug_type": "安全漏洞"}
    print(f"  ✅ Literal→str 转换 ok: {metadata}")


def exp2_get_result_narrow() -> None:
    """坑 2：Chroma get() 返回 dict[str, object] → ids 收窄。"""
    print("=" * 60)
    print("坑 2：Chroma get() 返回收窄（无 chroma 依赖，模拟返回形状）")
    fake_rows: dict[str, object] = {"ids": ["a1", "a2"], "metadatas": [{"bug_id": "B1"}, {"bug_id": "B2"}]}
    ids_obj: object = fake_rows.get("ids", [])
    ids: list[str] = ids_obj if isinstance(ids_obj, list) else []
    assert ids == ["a1", "a2"]
    # 非 list 兜底：缺 key / 形状异常不崩
    empty_obj: object = fake_rows.get("not_exist", [])
    empty_ids: list[str] = empty_obj if isinstance(empty_obj, list) else []
    assert empty_ids == []
    print(f"  ✅ get() ids 收窄 ok: {ids}；缺失 key 兜底空列表")


def exp3_private_attr() -> None:
    """坑 3：私有属性访问（演示项目先例的 ignore 用法，纯语法演示不真跑）。"""
    print("=" * 60)
    print("坑 3：私有属性 _vectorstore 访问（# type: ignore[attr-defined]）")
    # 真实代码见 day31_bug_archive._get_vectorstore：
    #   vs = indexer._vectorstore  # type: ignore[attr-defined]
    # pyright 默认 reportPrivateUsage 会报错；项目先例（day21:121/203）统一 ignore
    print("  ✅ 演示：day21_kb_persist.py:121/203 已有同类先例（_collection.count() 访问）")


def exp4_agg_dict() -> None:
    """坑 4：聚合字典推导（.get 兜底，缺 key 取 0）。"""
    print("=" * 60)
    print("坑 4：聚合字典推导（.get 兜底）")
    a1 = BugAnalysis(
        bug_id="B1", title="t1", bug_summary="s", bug_type="功能缺陷", severity="严重",
        root_cause_analysis="r", reproduce_steps=["1"], test_cases_to_add=[],
        regression_scope=["x"], prevention="p", status="待修复",
    )
    a2 = BugAnalysis(
        bug_id="B2", title="t2", bug_summary="s", bug_type="功能缺陷", severity="一般",
        root_cause_analysis="r", reproduce_steps=["1"], test_cases_to_add=[],
        regression_scope=["x"], prevention="p", status="已修复",
    )
    stats = aggregate_stats([a1, a2])
    assert stats.total == 2
    assert stats.by_status.get("待修复", 0) == 1
    assert stats.by_status.get("不存在", 0) == 0  # 缺失 key → 0 而非 KeyError
    print(f"  ✅ 聚合推导 ok: {stats.by_severity} / {stats.by_status}")


def exp5_nested_schema() -> None:
    """坑 5：嵌套 Schema 收窄——BugAnalysis → test_cases_to_add → BugTestCase。"""
    print("=" * 60)
    print("坑 5：嵌套 Schema 逐层取数")
    a = BugAnalysis(
        bug_id="B1", title="t", bug_summary="s", bug_type="功能缺陷", severity="一般",
        root_cause_analysis="r", reproduce_steps=["1"],
        test_cases_to_add=[
            BugTestCase(title="错误码文案校验", focus="40101 文案"),
            BugTestCase(title="兜底文案限 5xx", focus="5xx 才显示系统繁忙"),
        ],
        regression_scope=["登录"], prevention="p",
    )
    # 直接字段遍历（Pydantic BaseModel 子类的字段类型静态可知，无需收窄）
    focus_list: list[str] = [c.focus for c in a.test_cases_to_add]
    assert len(focus_list) == 2 and "40101 文案" in focus_list
    print(f"  ✅ 嵌套遍历 ok: {focus_list}")


def exp6_zero_api_selfcheck() -> None:
    """今日模块零 API 自检：分割 + 质检 + 聚合三件套（复用前几个实验的断言）。"""
    print("=" * 60)
    print("零 API 自检：今日纯逻辑三件套")
    here: str = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "..", "..", "docs", "bugs", "login_bugs.md"), "r", encoding="utf-8", errors="replace") as f:
        text: str = f.read()
    sections: list[str] = split_bug_reports(text)
    assert len(sections) == 4
    print(f"  ✅ split_bug_reports: {len(sections)} 段")
    # 手工构造 → 质检 → 断言（完整样例无 ERROR / 缺复现 ERROR）
    ok = BugAnalysis(
        bug_id="B1", title="t", bug_summary="s", bug_type="功能缺陷", severity="一般",
        root_cause_analysis="r", reproduce_steps=["1"],
        test_cases_to_add=[BugTestCase(title="x", focus="y")],
        regression_scope=["登录"], prevention="p",
    )
    assert not validate_bug_analysis(ok).has_error
    print("  ✅ validate_bug_analysis: 完整样例无 ERROR")
    print("✅ 零 API 自检通过")


def main() -> None:
    exp1_literal_to_str()
    exp2_get_result_narrow()
    exp3_private_attr()
    exp4_agg_dict()
    exp5_nested_schema()
    exp6_zero_api_selfcheck()
    print("\n✅ Day 31 Pyright 避坑演示 + 零 API 自检全部通过")


if __name__ == "__main__":
    main()
