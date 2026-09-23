# FILE: test_day42_third_scenario.py
"""Day 42 测试：第三场景（refund）契约 + 入口层同源（全部零 API，不碰项目产物）

为什么新开一个文件、而不是往 test_day41_e2e.py 里加：
  Day 41 那份是「两场景时代」的产物，里面有几处断言只对 login/register 成立
  （例如 `test_scenario_contract_violations_empty` 逐个数两个名字）。
  它是当天的**历史证据**，不该被后来的事实改写。
  今天的做法是**新增一份"任意场景数都成立"的契约网**：
    · 一律**遍历 SCENARIO_REGISTRY**，不点名场景；
    · 每条契约配一条**负向 sanity**，证明它真的会红（否则"全绿"可能只是
      函数恒返回空列表）；
    · 把今天"第三场景照妖镜"照出来的三处「第二份写死的清单」钉住
      （seam_probe 的覆盖清单 / ui 的场景清单 / UI 测试的字面量断言）。

测试策略（沿用 Day 39–41 的分层纪律）：
  · 接缝契约写厚：产物互斥 / 端口同源 / 靶场同源 / 命名空间 —— 纯逻辑，零 IO；
  · mock 场景化用**本地回环**打真 HTTP（零外网），**每个用例独占端口**（Windows 上
    `SO_REUSEADDR` 是 `SO_REUSEPORT` 语义，共享端口会"单跑必过、全量偶发"），
    `finally` 里必关；
  · 源码级检查（ui/app.py 与 test_day37_app.py）用**文本断言**而不是 import：
    `import ui.app` 会把 streamlit 拖进来（单次渲染 ≈10s，Day 39 已为此把三条
    UI 断言并为一次渲染）。这里要守的是**写法**——「别再写第二份字面量清单」。
"""
from __future__ import annotations

from pathlib import Path

import pytest
import requests

from day30_mock_api import start_mock, stop_mock
from day35_scenario import (
    LOGIN_SCENARIO,
    REFUND_SCENARIO,
    REGISTER_SCENARIO,
    SCENARIO_REGISTRY,
    ScenarioConfig,
    build_blueprint,
    find_scenario_collisions,
    find_scenario_contract_violations,
    output_namespace,
)
from day41_seam_probe import SCENARIOS
from day42_review_probe import (
    check_cli_surface,
    check_readme_assets,
    check_scenario_contracts,
    check_single_source,
)

# 测试独占端口（避开场景端口 8766/8767/8768，防与真实跑冲突）
_TEST_PORT_REFUND: int = 8794
_TEST_PORT_REFUND_BUG: int = 8795
_TEST_PORT_LOGIN: int = 8796


# ═══════════════════════════════════════════════════════
# 第一组：第三场景的接缝契约（纯逻辑，零 IO）
# ═══════════════════════════════════════════════════════
def test_three_scenarios_registered() -> None:
    """注册表里有三个场景，且 refund 的端口与其他场景不撞。"""
    assert set(SCENARIO_REGISTRY) == {"login", "register", "refund"}
    ports: list[int] = [sc.mock_port for sc in SCENARIO_REGISTRY.values()]
    assert len(set(ports)) == len(ports), f"场景端口必须两两不同：{ports}"


def test_all_scenarios_have_no_output_collisions() -> None:
    """★ 通用契约：**注册表里任意个**场景的产物路径互不相交。"""
    scenarios: tuple[ScenarioConfig, ...] = tuple(SCENARIO_REGISTRY.values())
    collisions: list[str] = find_scenario_collisions(scenarios)
    assert collisions == [], "产物路径仍有冲突：\n" + "\n".join(collisions)


def test_all_scenarios_pass_contract_selfcheck() -> None:
    """★ 通用契约：每个场景的端口同源 / S5 点名本场景 schema / 靶场同源。"""
    for sc in SCENARIO_REGISTRY.values():
        violations: list[str] = find_scenario_contract_violations(sc)
        assert violations == [], f"{sc.name} 有契约违规：\n" + "\n".join(violations)


def test_negative_sanity_collision_is_detected() -> None:
    """★ 负向 sanity：同名场景必然报冲突（证明冲突检测函数**有牙齿**）。

    没有这条，上面那条"全绿"可能只是 `find_scenario_collisions` 恒返回空列表。
    """
    clone: ScenarioConfig = LOGIN_SCENARIO.model_copy()
    collisions: list[str] = find_scenario_collisions((LOGIN_SCENARIO, clone))
    assert collisions, "同名场景的产物路径重叠没被抓住"


def test_negative_sanity_port_mismatch_is_detected() -> None:
    """★ 负向 sanity：把 refund 的 mock_port 改错 → 契约校验必须报出来。"""
    broken: ScenarioConfig = REFUND_SCENARIO.model_copy(update={"mock_port": 9999})
    violations: list[str] = find_scenario_contract_violations(broken)
    assert any("9999" in v for v in violations), f"端口错位没被抓住：{violations}"


def test_refund_products_are_namespaced() -> None:
    """refund 的**产物型**阶段必须落在 refund 命名空间下（防半参数化回归）。"""
    assert output_namespace(REFUND_SCENARIO) == "refund"
    namespaced_stages: set[str] = {
        "S4_test_codegen", "S5_test_data", "S6_execute_normal",
        "S7_execute_bug", "S8_exec_report",
    }
    for spec in build_blueprint(REFUND_SCENARIO):
        if spec.stage_id not in namespaced_stages:
            continue
        assert spec.outputs, f"{spec.stage_id} 没有产物"
        for out in spec.outputs:
            assert "/refund/" in out, f"{spec.stage_id} 的产物 {out!r} 不在命名空间下"


def test_refund_kinds_are_code_driven() -> None:
    """★ refund 的接口文档与数据模型都是 `.json` → S3/S5 必须是 `code`（不进模型）。

    这是 Day 41「kind 由资产扩展名派生」在第三个场景上的复验：只要资产还是 .json，
    代码链（S3→S8）就**一句提示都不用等 API** 就能整条跑通。
    """
    kinds: dict[str, str] = {s.stage_id: s.kind for s in build_blueprint(REFUND_SCENARIO)}
    assert kinds["S3_api_plan"] == "code", "refund 的接口文档是 .json，不该等 API"
    assert kinds["S5_test_data"] == "code", "refund 的数据模型是 .json，不该等 API"
    # 需求文档（.txt）与 Bug 报告（.md）是人写的文档 → 仍走模型
    assert kinds["S1_requirement_cases"] == "llm"
    assert kinds["S9_bug_analyze"] == "llm"


def test_refund_mock_contract_flows_into_blueprint() -> None:
    """★ 靶场契约进蓝图：端口 8768 与场景名 refund 都从 ScenarioConfig 流到执行段。"""
    for spec in build_blueprint(REFUND_SCENARIO):
        if spec.runner != "mock_pytest":
            continue
        assert spec.mock_port == REFUND_SCENARIO.mock_port
        assert spec.mock_scenario == "refund"


# ═══════════════════════════════════════════════════════
# 第二组：refund 靶场（本地回环，零外网）
# ═══════════════════════════════════════════════════════
@pytest.fixture()
def refund_mock_url():
    """起 refund 靶场（本用例独占端口），用例结束后必关。"""
    start_mock(_TEST_PORT_REFUND, scenario="refund")
    try:
        yield f"http://127.0.0.1:{_TEST_PORT_REFUND}"
    finally:
        stop_mock()


def test_refund_mock_four_branches(refund_mock_url: str) -> None:
    """正常版 4 分支 = S6 全绿的前提（与生成套件的 4 个 node 一一对应）。"""
    def _post(payload: dict[str, str]) -> int:
        return requests.post(f"{refund_mock_url}/api/refund", json=payload, timeout=5).status_code

    assert _post({"order_id": "ORD-1001", "amount": "99.5"}) == 200
    assert _post({"amount": "99.5"}) == 400                 # 缺 order_id
    assert _post({"order_id": "ORD-1001"}) == 400           # 缺 amount
    assert _post({"order_id": "invalid_value", "amount": "99.5"}) == 401


def test_refund_mock_bug_mode_strips_validation() -> None:
    """埋 Bug 版：**校验整段被摘掉** → 连空参也受理（S7 因此红 3 条）。

    ⚠️ 与 register 的埋法**不同**（register 只放过"验证码不匹配"这一支 → 红 1 条）。
    「埋 Bug 的爆炸半径决定 S7 的红度」—— 这本身就是一条值得看的观测。
    """
    start_mock(_TEST_PORT_REFUND_BUG, bug_mode=True, scenario="refund")
    try:
        base: str = f"http://127.0.0.1:{_TEST_PORT_REFUND_BUG}"
        assert requests.post(f"{base}/api/refund", json={"amount": "99.5"}, timeout=5).status_code == 200
        assert requests.post(
            f"{base}/api/refund",
            json={"order_id": "invalid_value", "amount": "99.5"},
            timeout=5,
        ).status_code == 200
    finally:
        stop_mock()


def test_login_mock_does_not_serve_refund_route() -> None:
    """★ 靶场同源的负向证据：login 靶场没有 /api/refund → 404。

    这正是"没有场景维度的 mock"会让第三个场景**全打 404 却仍判 run_ok** 的真相。
    """
    start_mock(_TEST_PORT_LOGIN, scenario="login")
    try:
        resp = requests.post(
            f"http://127.0.0.1:{_TEST_PORT_LOGIN}/api/refund",
            json={"order_id": "ORD-1001", "amount": "99.5"},
            timeout=5,
        )
        assert resp.status_code == 404
    finally:
        stop_mock()


# ═══════════════════════════════════════════════════════
# 第三组：入口层 / 工具层同源（把"第二份清单"钉住）
# ═══════════════════════════════════════════════════════
def test_seam_probe_covers_the_whole_registry() -> None:
    """★ 同源：接缝探测覆盖的场景清单 == 注册表（多一个少一个都要红）。

    修复前这里是 `SCENARIOS = (LOGIN_SCENARIO, REGISTER_SCENARIO)`：
    加第三个场景**不会报错**，只会让探测"少看一个"，而报告照旧 0/0/0 ——
    **假绿**。这条断言就是那次的回归网。
    """
    assert SCENARIOS == tuple(SCENARIO_REGISTRY.values())


def test_hardcoded_scenario_tuple_would_be_caught() -> None:
    """★ 负向 sanity：证明"探测少看场景"这件事**可被断言**（否则上面那条是空话）。"""
    hardcoded: tuple[ScenarioConfig, ...] = (LOGIN_SCENARIO, REGISTER_SCENARIO)
    assert hardcoded != tuple(SCENARIO_REGISTRY.values()), "写死两个场景就该与注册表不等"


def test_ui_scenario_dict_is_derived_from_registry() -> None:
    """★ 源码级契约：UI 的场景清单**派生自注册表**，不是第二份字面量。

    为什么用文本断言：`import ui.app` 会把 streamlit 拖进来（≈10s）。
    这里要守的是一个**写法** —— 「别再写 `{LOGIN.name: LOGIN, ...}`」。

    5.2a 追加（5.2 验收发现的 UI bug）：同一条纪律还要管**读侧** —— 产物浏览取报告时
    也必须按场景派生。修复前它是**无参数**的，扫的是 `outputs/flow` **根目录**（非递归）
    ⇒ 侧边栏换场景，下拉里一个字都不变，**而且不报错**（根上恰好只有 login 的产物）。
    加在同一条用例里、不新开一条：**不动"20 条"这个已实测计数** —— 否则就得重跑全套。
    """
    src: str = (Path(__file__).resolve().parents[1] / "ui" / "app.py").read_text(encoding="utf-8")
    assert "dict(SCENARIO_REGISTRY)" in src
    assert "_SCENARIOS: dict[str, ScenarioConfig] = {" not in src
    # ── 5.2a：报告路径也必须从场景派生（读侧同源）──
    assert "output_namespace(sc)" in src, "产物浏览的报告路径必须来自资产层的场景派生"
    assert "_load_report_markdowns(sc, blueprint)" in src, "调用点必须把场景与蓝图传进去"


def test_ui_test_derives_options_from_registry() -> None:
    """★ 源码级契约：UI 测试的场景断言也已派生（不再写死两个名字）。

    ⚠️ 标记取的是**带上下文的整行**（`set(selector.options) == {...}`），不是光秃秃的
    `== {"login", "register"}` —— 后者会被 `test_day37_app.py` 里那句**解释怎么改**的
    注释命中，判成「还留着第二份清单」（**假红**）。假红比假绿更烦：它会让人去删一段
    正确的注释。同理，凡是要查"某个写法还在不在"，标记都要取足上下文。
    """
    src: str = (
        Path(__file__).resolve().parents[1] / "tests" / "test_day37_app.py"
    ).read_text(encoding="utf-8")
    code: str = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
    assert "set(SCENARIO_REGISTRY)" in src
    assert 'set(selector.options) == {"login", "register"}' not in code


# ═══════════════════════════════════════════════════════
# 第四组：复盘探测本身必须"干净"（把 Day 42 的验收门也纳入回归）
# ═══════════════════════════════════════════════════════
def test_review_probe_scenario_contracts_clean() -> None:
    """复盘探测 A-1：遍历注册表的场景契约检查必须零阻塞项。"""
    assert check_scenario_contracts() == []


def test_review_probe_cli_surface_clean() -> None:
    """复盘探测 A-2：CLI 命令面完整（scan / run / report / cache 及其 --help）。"""
    assert check_cli_surface() == []


def test_review_probe_readme_assets_clean() -> None:
    """复盘探测 A-3：README 引用的截图在盘上、写的 cli 子命令真实存在。"""
    assert check_readme_assets() == []


def test_review_probe_single_source_clean() -> None:
    """复盘探测 A-4：三处「第二份场景清单」已全部同源。"""
    assert check_single_source() == []


def test_test_ports_do_not_collide_with_scenario_ports() -> None:
    """测试端口必须与场景端口**不相交**（防"测试打到了真场景靶场"这种串味）。

    ⚠️ 判据是"两个集合不相交"，不是"测试端口比某个阈值大"——
    后者的阈值一改就静默失效（我第一版就是 `_MAX_PORT < _TEST_PORT`，是个假契约）。
    """
    scenario_ports: set[int] = {sc.mock_port for sc in SCENARIO_REGISTRY.values()}
    test_ports: set[int] = {_TEST_PORT_REFUND, _TEST_PORT_REFUND_BUG, _TEST_PORT_LOGIN}
    assert scenario_ports.isdisjoint(test_ports), f"端口撞了：{scenario_ports & test_ports}"