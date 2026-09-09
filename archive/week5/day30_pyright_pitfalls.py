"""
Day 30 练习 5：Pyright 避坑演示 + 今日模块零 API 自检

坑 1：生成代码的模板拼接——f-string 套 f-string 是花括号地狱 → 行列表拼接，
      渲染层 f-string 里 {{ }} 转义 = 生成代码里的 { } 字面量（运行时才解析）
坑 2：ast.parse 校验生成代码——SyntaxError 捕获，pyright 对 ast.Module 无压力
坑 3：subprocess 输出——text=True + encoding/errors 直接拿 str（否则 bytes 要 decode）
坑 4：pytest 9 parametrize argvalues 必须 list（9.1.0 起迭代器弃用，2026-06-13 联网确认）
坑 5：结构化输出收窄延续（ApiDoc 版）+ with_fallbacks 顺序（Day 29 坑延续）
坑 6：遍历 dataclass 列表直接用字段名——c.case.category 里 c.case 是未知属性
      （PlanCase 无 case 字段，category 是直接字段），error 类型传染 dict.get 重载解析，
      join 报出 "Generator[str | None, ...]" 假象；附带知识点：dict.get(key, default)
      传了 default 时静态返回不含 None（typeshed 重载2 get(key, default) -> V | _T），
      不传 default 才是 V | None（2026-08-30 用户实操 exp2 实测校准）

用法：
  python day30_pyright_pitfalls.py   # 零 API 自检全绿
"""
import ast
import subprocess
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from day30_api_schema import ApiDoc, ApiEndpoint, ApiParam, analyze_api_doc
from day30_pytest_generator import render_conftest, render_test_module, validate_python_syntax


def exp1_template_join() -> None:
    """坑 1：行列表拼接避开 f-string 花括号地狱（生成代码里的 {} 原样保留）。"""
    print("=" * 60)
    print("坑 1：模板拼接（渲染层 f-string 的 {{ }} = 生成代码的 { }）")
    expected_status: int = 401
    # 渲染层 f-string：{{resp.status_code}} 转义 → 生成代码里的 f-string {resp.status_code}
    line: str = f"        assert resp.status_code == {expected_status}, f\"期望 401 实际 {{resp.status_code}}: {{resp.text[:200]}}\""
    assert "f\"期望 401 实际 {resp.status_code}: {resp.text[:200]}\"" in line
    validate_python_syntax(line, "assert 行")  # ast.parse 对单行也能校验（函数体外也合法语法）
    print(f"  ✅ 生成代码里的 f-string 原样保留: {line.strip()}")
    print("     （渲染层 {{ 是转义，生成代码里是 {；运行时才解析——两层 f-string 不冲突）")


def exp2_ast_check() -> None:
    """坑 2：ast.parse 校验（可编译保证；SyntaxError 捕获并转清晰报错）。"""
    print("=" * 60)
    print("坑 2：ast.parse 语法校验")
    good: str = "def test_x():\n    assert 1 == 1\n"
    tree: ast.Module = ast.parse(good)
    assert isinstance(tree, ast.Module)
    print(f"  ✅ 合法代码通过: {type(tree).__name__}")
    bad: str = "def test_x(:\n    pass\n"
    try:
        ast.parse(bad)
        print("  ❌ 意外：坏代码竟然通过")
    except SyntaxError as exc:
        print(f"  ✅ 坏代码被拦截: {type(exc).__name__}: {exc}")
    # 复用今日渲染器：生成的 conftest 可编译
    api_doc = ApiDoc(title="t", base_url="http://x", endpoints=[])
    validate_python_syntax(render_conftest(api_doc), "conftest")
    print("  ✅ 空端点 ApiDoc 也能渲染合法 conftest（零端点退化路径不炸）")


def exp3_subprocess_text() -> None:
    """坑 3：subprocess.run(text=True) 直接拿 str（CompletedProcess[str]）。"""
    print("=" * 60)
    print("坑 3：subprocess 输出收窄（text=True → stdout 是 str，不用 bytes.decode）")
    proc: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, "-c", "print('hello from subprocess')"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
    )
    stdout: str = proc.stdout or ""
    assert "hello from subprocess" in stdout
    print(f"  ✅ stdout 直接是 str（pyright: CompletedProcess[str]）: {stdout.strip()!r}")


def exp4_parametrize_list() -> None:
    """坑 4：pytest 9 的 parametrize argvalues 必须 list（生成器 9.1.0 弃用）。"""
    print("=" * 60)
    print("坑 4：parametrize argvalues 用 list 字面量（pytest 9.1.0 弃用迭代器，2026-06-13 确认）")
    # 渲染器生成的 parametrize 代码（含 list 字面量，从三件套计划的 variants 来）
    variants: list[dict[str, str]] = [
        {"password": "Test123456"},
        {"phone": "13800138000"},
    ]
    # 生成代码片段：显式 list（不是生成器推导式——生成器会被耗尽，用例静默丢失）
    rendered: str = "@pytest.mark.parametrize(\"payload\", [\n    " + ",\n    ".join(
        f"{v!r}" for v in variants
    ) + ",\n])"
    assert "generator" not in rendered and "[" in rendered
    validate_python_syntax(rendered, "parametrize")
    print(f"  ✅ 渲染为 list 字面量: {rendered.replace(chr(10), ' ')}")


def exp5_structured_narrow() -> None:
    """坑 5：结构化输出收窄延续（ApiDoc 版）——object 入口 → isinstance 分支。"""
    print("=" * 60)
    print("坑 5：结构化输出收窄（ApiDoc：object → isinstance → model_validate 兜底）")
    raw: object = ApiDoc(
        title="t", base_url="http://x",
        endpoints=[ApiEndpoint(name="e", method="GET", path="/api/x", auth_required=False)],
    )
    if isinstance(raw, ApiDoc):
        assert raw.endpoints[0].path == "/api/x"
        print(f"  ✅ isinstance 收窄成功: title={raw.title!r}，{len(raw.endpoints)} 端点")
    # 反例：dict 兜底路径（模拟链返回 dict 的场景）
    from day30_api_schema import analyze_api_doc  # noqa: F811, PLC0415

    dict_raw: object = {"title": "t", "base_url": "http://x", "endpoints": []}
    if isinstance(dict_raw, dict):
        parsed: ApiDoc = ApiDoc.model_validate(dict_raw)
        print(f"  ✅ dict 兜底 model_validate: {parsed.title}")


def exp6_dataclass_field() -> None:
    """坑 6：遍历 dataclass 列表直接用字段名（别写不存在的嵌套属性）。

    2026-08-30 用户实操校准：exp2 的 "c.case.category" 是笔误——c 遍历
    plan.cases（list[PlanCase]），category 是 PlanCase 的直接字段，没有 case 字段。
    c.case 是未知属性 → error 类型传染 dict.get 重载解析 → join 报出
    "Generator[str | None, ...]" 的假象（真正的 str | None 只来自不传 default 的 get）。
    """
    print("=" * 60)
    print("坑 6：遍历 dataclass 列表直接用字段名（c.case.category 是笔误，PlanCase 无 case 字段）")
    from day30_api_schema import CATEGORY_LABEL, PlanCase  # noqa: PLC0415

    cases: list[PlanCase] = [
        PlanCase(case_id="TC001", title="正常调用", category="normal", http_method="POST", path="/api/login"),
        PlanCase(case_id="TC002", title="参数缺失", category="missing", http_method="POST", path="/api/login"),
    ]
    # ✅ 正确：category 是 PlanCase 直接字段（str）→ 生成器元素 str → join 收
    labels: str = " / ".join(CATEGORY_LABEL.get(c.category, c.category) for c in cases)
    assert labels == "正常调用 / 参数缺失"
    # ⚠️ dict.get(key, default) 传了 default → Pylance 推断 str（typeshed 重载2，不含 None）
    label: str = CATEGORY_LABEL.get("normal", "normal")
    assert label == "正常调用"
    print(f"  ✅ 直接字段 + get 传 default: {labels}")
    print("     dict.get(key, default) 传 default → 静态返回 str（typeshed 重载2，不含 None）")
    print("     不传 default → V | None（那才是 str | None 的真正来源）")
    print("     c.case 是未知属性 → error 类型传染 get 重载解析 → join 报 str | None 假象")


def main() -> None:
    exp1_template_join()
    exp2_ast_check()
    exp3_subprocess_text()
    exp4_parametrize_list()
    exp5_structured_narrow()
    exp6_dataclass_field()
    print("\n✅ Day 30 Pyright 避坑演示 + 零 API 自检全部通过")


if __name__ == "__main__":
    main()
