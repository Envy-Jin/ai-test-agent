# FILE: test_day41_e2e.py
"""Day 41 测试：端到端接缝契约 + 缓存接线（全部零 API，且**不碰项目产物**）

测试策略（沿用 Day 39/40 的分层纪律）：
  · 接缝契约写厚：产物互斥 / 端口同源 / 靶场同源 / kind 由资产派生 —— 纯逻辑，零 IO；
  · 执行器只测**纯函数**（路径派生），不真跑 `run_flow`（那会写 outputs/，污染仓库）；
  · mock 场景化用**本地回环**打真 HTTP（零外网），独占测试端口，`finally` 里必关；
  · 缓存接线用假模型（`CountingChatModel`）—— 断言落在 `_generate` 的**调用次数**上，
    而不是"我们调过某个中间函数"；
  · 缓存的库路径一律走 `tmp_path`，绝不碰项目根的 `.cache/llm_cache.db`。

⚠️ 本文件刻意**不 import** `day31_bug_analyzer`（它顶层拖 langchain_google_genai，
   实测冷启动 ≈50-66s）。今天要验的是并发/缓存/契约，与那个模块无关。
"""
from __future__ import annotations

from pathlib import Path

import pytest
import requests
from click.testing import CliRunner, Result
from langchain_core.globals import get_llm_cache, set_llm_cache

from day30_mock_api import start_mock, stop_mock
from day33_change_schema import load_case_registry
from day34_flow_map import BLUEPRINT, StageSpec
from day34_orchestrator import (
    find_junit_input,
    pytest_suite_target,
    render_exec_report,
    scenario_label_of,
)
from day35_scenario import (
    LOGIN_SCENARIO,
    REGISTER_SCENARIO,
    SCENARIO_REGISTRY,
    build_blueprint,
    find_scenario_collisions,
    find_scenario_contract_violations,
    output_namespace,
)
from day40_llm_cache import SQLiteLLMCache
from day41_cache_wiring import (
    CountingChatModel,
    cache_prefix,
    install_llm_cache,
    uninstall_llm_cache,
)

# mock_pytest 契约字段（Day 41 新增 mock_port / mock_scenario 后一起比）
_CONTRACT_FIELDS: tuple[str, ...] = (
    "stage_id", "kind", "runner", "inputs", "outputs",
    "mock_bug", "mock_port", "mock_scenario",
)

# 测试独占端口（避开场景端口 8766/8767，防与真实跑冲突）
#
# ⚠️ 为什么每个用例**各用一个端口**（Day 41 全量跑偶发失败后改的）：
#    原来三个 mock 用例先后绑同一个端口 8799。Windows 上 `http.server.HTTPServer`
#    默认 `allow_reuse_address = 1` → 底层 `SO_REUSEADDR` 在 Windows 上是
#    **SO_REUSEPORT 语义**（允许第二个 socket 绑到同一端口，两个 listener 并存，
#    连接交给谁由内核决定）—— 于是"上一个用例的 listener 还在"时，断言会打到
#    **另一个场景的 handler**：`test_login_mock_does_not_serve_register_route`
#    期望 404 却收到 200（register 靶场的成功响应）。
#    症状特征：单文件跑必过、全量跑偶发（一次失败后重跑就绿）。
#    ⚠️ 这类"偶发"绝不该靠重跑掩盖 —— 共享可变资源（端口）在用例间**不隔离**，
#    就一定会以随机形态复现。修法是隔离，不是重试。
_TEST_PORT_REGISTER: int = 8791
_TEST_PORT_REGISTER_BUG: int = 8792
_TEST_PORT_LOGIN: int = 8793


# ═══════════════════════════════════════════════════════
# 第一组：跨场景接缝契约（纯逻辑，零 IO）
# ═══════════════════════════════════════════════════════
def test_two_scenarios_have_no_output_collisions() -> None:
    """★ 核心契约：两场景的产物路径互不相交（谁也不覆盖谁）。

    修复前这里是 8 处冲突：两场景共用同一份 generated_tests / junit / 报告，
    跑 register 会把 login 的产物静默盖掉 —— 状态列还全是绿的。
    """
    collisions: list[str] = find_scenario_collisions(tuple(SCENARIO_REGISTRY.values()))
    assert collisions == [], "产物路径仍有冲突：\n" + "\n".join(collisions)


def test_login_blueprint_stays_contract_equal(login_blueprint: list[StageSpec]) -> None:
    """★ 兼容层不破：login 蓝图与 Day 34 BLUEPRINT 契约逐项一致。

    login 的产物路径被 api_registry / README / Day39 截图引用，所以刻意保持平铺
    （见 day35_scenario.LEGACY_FLAT_SCENARIO 的说明）。这个断言就是"兼容层"的守卫。
    """
    assert len(login_blueprint) == len(BLUEPRINT)
    for built, base in zip(login_blueprint, BLUEPRINT, strict=True):
        for field in _CONTRACT_FIELDS:
            assert getattr(built, field) == getattr(base, field), f"{built.stage_id}.{field} 漂移"


def test_register_products_are_namespaced() -> None:
    """register 的**产物型**阶段必须落在 register 命名空间下（防半参数化回归）。"""
    namespaced_stages: set[str] = {
        "S4_test_codegen", "S5_test_data", "S6_execute_normal",
        "S7_execute_bug", "S8_exec_report",
    }
    for spec in build_blueprint(REGISTER_SCENARIO):
        if spec.stage_id not in namespaced_stages:
            continue
        assert spec.outputs, f"{spec.stage_id} 没有产物"
        for out in spec.outputs:
            assert "/register/" in out, f"{spec.stage_id} 的产物 {out!r} 不在命名空间下"


def test_kind_is_asset_driven() -> None:
    """★ kind 由**输入扩展名**派生，不是段固有属性。

    register 的接口文档是 .json（代码直读）、数据模型也是 .json →
    S3/S5 必须是 code；login 对应的是 .md，仍是 llm。
    """
    login_kinds: dict[str, str] = {s.stage_id: s.kind for s in build_blueprint(LOGIN_SCENARIO)}
    register_kinds: dict[str, str] = {s.stage_id: s.kind for s in build_blueprint(REGISTER_SCENARIO)}
    assert login_kinds["S3_api_plan"] == "llm"
    assert register_kinds["S3_api_plan"] == "code", "register 的接口文档是 .json，不该等 API"
    assert login_kinds["S5_test_data"] == "llm"
    assert register_kinds["S5_test_data"] == "code", "register 的数据模型是 .json，不该等 API"


def test_mock_contract_flows_into_blueprint() -> None:
    """★ 靶场契约进蓝图：端口与场景名都从 ScenarioConfig 流到执行段。"""
    for sc in (LOGIN_SCENARIO, REGISTER_SCENARIO):
        for spec in build_blueprint(sc):
            if spec.runner != "mock_pytest":
                continue
            assert spec.mock_port == sc.mock_port, f"{spec.stage_id} 端口没跟随场景"
            assert spec.mock_scenario == sc.name, f"{spec.stage_id} 靶场没跟随场景"


def test_scenario_contract_violations_empty() -> None:
    """两场景的契约自检都要通过（端口同源 / S5 点名本场景 schema / 靶场同源）。"""
    for sc in (LOGIN_SCENARIO, REGISTER_SCENARIO):
        violations: list[str] = find_scenario_contract_violations(sc)
        assert violations == [], f"{sc.name} 有契约违规：\n" + "\n".join(violations)


def test_port_mismatch_is_actually_detected() -> None:
    """★ 负向 sanity：把 mock_port 改错，校验**必须**报出来。

    没有这条，上面那条"全绿"可能只是校验函数永远返回空列表（假绿）。
    """
    broken = REGISTER_SCENARIO.model_copy(update={"mock_port": 9999})
    violations: list[str] = find_scenario_contract_violations(broken)
    assert any("9999" in v for v in violations), f"端口错位没被抓住：{violations}"


def test_output_namespace_rule() -> None:
    """命名空间规则：login 空（兼容）、其他场景等于场景名。"""
    assert output_namespace(LOGIN_SCENARIO) == ""
    assert output_namespace(REGISTER_SCENARIO) == "register"


# ═══════════════════════════════════════════════════════
# 第二组：执行器的路径派生（纯函数，不真跑）
# ═══════════════════════════════════════════════════════
def test_find_junit_input_reads_from_spec_inputs() -> None:
    """★ 回归 Day 41 去掉的硬编码：junit 路径必须从 spec.inputs 派生。"""
    spec: StageSpec = next(
        s for s in build_blueprint(REGISTER_SCENARIO) if s.stage_id == "S8_exec_report"
    )
    assert find_junit_input(spec, "normal") == "outputs/flow/register/junit_normal.xml"
    assert find_junit_input(spec, "bug") == "outputs/flow/register/junit_bug.xml"


def test_find_junit_input_returns_none_when_not_declared() -> None:
    """蓝图没声明 → 返回 None（调用方跳过并说明原因，而不是去找一个写死的路径）。"""
    spec = StageSpec(stage_id="X", title="x", source="test", kind="code", outputs=["outputs/x.md"])
    assert find_junit_input(spec, "normal") is None


def test_pytest_target_is_the_suite_file_not_the_dir() -> None:
    """★ 回归：执行段点名**文件**，不喂目录（否则会连带收集兄弟场景的用例）。"""
    spec: StageSpec = next(
        s for s in build_blueprint(REGISTER_SCENARIO) if s.stage_id == "S6_execute_normal"
    )
    target: str = pytest_suite_target(spec)
    assert target.endswith("test_api_suite.py")
    assert "register" in target.replace("\\", "/")


# ═══════════════════════════════════════════════════════
# 第二·补：报告标题的场景名（端到端才暴露的硬编码）
# ═══════════════════════════════════════════════════════
_JUNIT_STUB: str = (
    '<?xml version="1.0" encoding="utf-8"?>'
    '<testsuites><testsuite name="pytest" errors="0" failures="0" '
    'skipped="0" tests="1" time="0.01">'
    '<testcase classname="outputs.generated_tests.register.test_api_suite.TestApiRegister" '
    'name="test_normal" time="0.01" />'
    "</testsuite></testsuites>"
)


def test_scenario_label_comes_from_case_registry() -> None:
    """★ 回归：报告标题的场景名**从注册表推**，不写死 login。

    端到端跑 register 时，报告标题曾写着「login · 正常版」——因为原实现是
    `f"# 全流程执行报告：login · {label}"` 的字面量。login 场景下它恰好正确，
    所以**任何单测都不会红**；只有真跑第二个场景才会现形。硬编码的"对"是运气。
    """
    root: Path = Path(__file__).resolve().parents[1]
    register_registry = load_case_registry(str(root / "docs/cases/api_registry_register.json"))
    login_registry = load_case_registry(str(root / "docs/cases/api_registry.json"))

    assert scenario_label_of(register_registry) == "register"
    assert scenario_label_of(login_registry) == "login"
    assert scenario_label_of([]) == "unknown", "空注册表要有兜底，不能 IndexError"

    md: str = render_exec_report("normal", _JUNIT_STUB, register_registry)
    assert md.splitlines()[0] == "# 全流程执行报告：register · 正常版（基线）"
    # 兼容层守卫：login 的报告标题字符不变（它被 docs/ 与截图引用）
    assert render_exec_report("bug", _JUNIT_STUB, login_registry).splitlines()[0] == (
        "# 全流程执行报告：login · 埋 Bug 版（对照）"
    )


def test_exec_report_counts_its_own_nodes() -> None:
    """★ 回归：'**执行**' 行里的 node 数来自**本次 junit**，不是写死的 7。"""
    root: Path = Path(__file__).resolve().parents[1]
    registry = load_case_registry(str(root / "docs/cases/api_registry_register.json"))
    md: str = render_exec_report("normal", _JUNIT_STUB, registry)
    assert "（1 个 pytest node）" in md, md


# ═══════════════════════════════════════════════════════
# 第三组：mock 场景化（本地回环，零外网）
# ═══════════════════════════════════════════════════════
@pytest.fixture()
def register_mock_url():
    """起 register 靶场（本用例独占端口），用例结束后必关。"""
    start_mock(_TEST_PORT_REGISTER, scenario="register")
    try:
        yield f"http://127.0.0.1:{_TEST_PORT_REGISTER}"
    finally:
        stop_mock()


def test_register_mock_four_branches(register_mock_url: str) -> None:
    """正常版 4 分支：正常 / 缺 code / 缺 phone / 错验证码（= S6 全绿的前提）。"""
    def _post(payload: dict[str, str]) -> int:
        return requests.post(f"{register_mock_url}/api/register", json=payload, timeout=5).status_code

    assert _post({"code": "123456", "phone": "13900139000"}) == 200
    assert _post({"phone": "13900139000"}) == 400
    assert _post({"code": "123456"}) == 400
    assert _post({"code": "000000", "phone": "13900139000"}) == 401


def test_register_mock_bug_mode_skips_code_check() -> None:
    """埋 Bug 版：错误验证码也返回 200（= BUG-R01，S7 抓到的就是这个）。"""
    start_mock(_TEST_PORT_REGISTER_BUG, bug_mode=True, scenario="register")
    try:
        resp = requests.post(
            f"http://127.0.0.1:{_TEST_PORT_REGISTER_BUG}/api/register",
            json={"code": "000000", "phone": "13900139000"},
            timeout=5,
        )
        assert resp.status_code == 200
    finally:
        stop_mock()


def test_login_mock_does_not_serve_register_route() -> None:
    """★ 证明"靶场同源"不是可有可无：login 靶场没有 /api/register → 404。

    这正是修复前 register 端到端"4 failed 却判 run_ok"的真相。
    """
    start_mock(_TEST_PORT_LOGIN, scenario="login")
    try:
        resp = requests.post(
            f"http://127.0.0.1:{_TEST_PORT_LOGIN}/api/register",
            json={"code": "123456", "phone": "13900139000"},
            timeout=5,
        )
        assert resp.status_code == 404
    finally:
        stop_mock()


# ═══════════════════════════════════════════════════════
# 第四组：缓存接线（假模型 + tmp_path，零 API）
# ═══════════════════════════════════════════════════════
@pytest.fixture()
def temp_global_cache(tmp_path: Path):
    """装上**临时库**的全局缓存，用完卸载并还原原值（不污染同进程其它用例）。

    ⚠️ 绝不使用项目根的 `.cache/llm_cache.db` —— 那是"本地可再生状态"，
       测试碰它会让结果不可重复（Day 40 纪律）。
    """
    original = get_llm_cache()
    cache: SQLiteLLMCache = install_llm_cache(str(tmp_path / "probe.db"))
    try:
        yield cache
    finally:
        set_llm_cache(original)


def test_install_llm_cache_points_global_switch(temp_global_cache: SQLiteLLMCache) -> None:
    """装完之后 get_llm_cache() 就是我们这个实例（框架层拦截点就位）。"""
    assert get_llm_cache() is temp_global_cache


def test_uninstall_clears_global_switch(temp_global_cache: SQLiteLLMCache) -> None:
    """卸掉之后是 None（测试之间不许靠"顺手留下的全局状态"）。"""
    uninstall_llm_cache()
    assert get_llm_cache() is None


def test_chat_cache_hit_skips_model_call(temp_global_cache: SQLiteLLMCache) -> None:
    """★ 今天的主论点：同一 prompt 问两次，模型只被调 1 次。"""
    model = CountingChatModel(label="probe-A")
    first = model.invoke("同一句 prompt")
    second = model.invoke("同一句 prompt")
    assert model.calls == 1, "第二次不该再进模型（缓存没接上）"
    assert first.content == second.content


def test_different_fingerprint_never_hits(temp_global_cache: SQLiteLLMCache) -> None:
    """★ 换模型指纹 = 换问题 → 必须 miss（Day 40 二元组键的实战验证）。"""
    model_a = CountingChatModel(label="probe-A")
    model_b = CountingChatModel(label="probe-B")
    _ = model_a.invoke("同一句 prompt")
    _ = model_b.invoke("同一句 prompt")
    assert model_a.calls == 1 and model_b.calls == 1
    assert temp_global_cache.count() == 2, "两个 llm_string 应各存一条"


def test_chat_generation_roundtrip(temp_global_cache: SQLiteLLMCache) -> None:
    """★ 回归 Day 40 的漏测：chat 路径的载荷是 `ChatGeneration(message=AIMessage)`。

    Day 40 的白名单只放了 `Generation`（LLM 路径），chat 模型一命中就抛
    `ValueError: Deserialization of ('langchain','schema','messages','AIMessage') is not allowed`。
    这个用例就是那条缺陷的回归网。
    """
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatGeneration

    payload: list[ChatGeneration] = [ChatGeneration(message=AIMessage(content="chat 回答"))]
    temp_global_cache.update("p-chat", "llm-chat", payload)
    got = temp_global_cache.lookup("p-chat", "llm-chat")
    assert got is not None
    assert got[0].text == "chat 回答"


def test_cache_prefix_is_valid_python() -> None:
    """执行器要把它拼进 `python -c`：语法必须合法，且真的装了缓存。"""
    code: str = cache_prefix()
    compile(code, "<cache_prefix>", "exec")
    assert "install_llm_cache" in code


def test_cache_releases_file_handle(tmp_path: Path) -> None:
    """★ 回归 Day 41 实测暴出的句柄泄漏：缓存操作完必须能删掉库文件。

    ⚠️ 病因：`with sqlite3.connect(...) as conn:` 在 sqlite3 里是**事务**上下文，
       根本不关连接；连接与游标之间有引用环 → GC 不立刻回收 → 文件句柄悬挂。
       实测症状是删临时目录报 `PermissionError [WinError 32]`，而冒烟脚本用
       `rmtree(..., ignore_errors=True)` 把它**静默吞掉** → "清理干净"是假的。

    ⚠️ 这条断言**只在 Windows 上有牙齿**：POSIX 允许删除已打开的文件，
       Linux 上漏关连接也能删成功（所以别以为它是跨平台的通用守卫）。
    """
    import gc

    db: Path = tmp_path / "handle.db"
    cache: SQLiteLLMCache = SQLiteLLMCache(db)
    model = CountingChatModel(label="handle-probe")
    with_global_switch = get_llm_cache()
    try:
        set_llm_cache(cache)
        _ = model.invoke("探针 prompt")
        _ = cache.lookup("p", "l")
        _ = cache.count()
        _ = cache.stats()
        gc.collect()  # 真泄漏的连接要靠 GC 才收；修好了则这行是多余的保险
        db.unlink()  # 句柄没关 → Windows 上这里直接抛 PermissionError
        assert not db.exists()
    finally:
        set_llm_cache(with_global_switch)


# ═══════════════════════════════════════════════════════
# 第五组：入口层形状（写薄）
# ═══════════════════════════════════════════════════════
def test_cli_run_exposes_no_cache_flag() -> None:
    """`run --no-cache` 开关在位（关缓存 = 量冷启动真实耗时）。"""
    from cli import cli

    result: Result = CliRunner().invoke(cli, ["run", "--help"])
    assert result.exit_code == 0, result.output
    assert "--no-cache" in result.output


def test_cli_scan_prints_contract_check() -> None:
    """`scan` 顺手报契约校验 —— 「能不能跑」和「跑得对不对」要一起看。"""
    from cli import cli

    result: Result = CliRunner().invoke(cli, ["scan", "--scenario", "register"])
    assert result.exit_code == 0, result.output
    assert "契约校验" in result.output


def test_cli_report_rejects_unknown_scenario() -> None:
    """`report --scenario` 未知场景必须报错（绝不静默回落到 login）。"""
    from cli import cli

    result: Result = CliRunner().invoke(cli, ["report", "--scenario", "nope"])
    assert result.exit_code != 0
    assert "未知场景" in result.output