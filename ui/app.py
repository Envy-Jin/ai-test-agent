# FILE: app.py —— 真实落地到 ai_test_agent/ui/app.py（Day 37 第 4 层入口层）
"""AI 测试全流程 Agent · Streamlit 操作台（薄 UI 层：只调资产，不写业务）

运行（在 ai_test_agent 项目根）：
    .venv/Scripts/python.exe -m streamlit run ui/app.py
冒烟（无浏览器无 API）：
    .venv/Scripts/python.exe -m pytest tests/test_day37_app.py tests/test_day39_ui_stages.py -q

设计纪律（Day37 步骤 1 决策 A/D）：
  - 页面加载零 API：只跑 build_blueprint + scan_blueprint（纯文件系统盘点）
  - 昂贵动作（run_flow）只在按钮按下时执行，结果存 st.session_state 防 rerun 丢失
  - UI 里没有业务 for 循环：表格/报告全部委托 day34/35 资产函数
    （Day39 5.13 补充：**选段闭包也算业务**，同样委托 select_stages，UI 只做展示整形）
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import TYPE_CHECKING

# ── import 桥（决策 C）：真实资产在 src/agent 平铺、彼此裸 import → 把 src/agent 放 sys.path 首位
# 注意：pyproject [tool.pyright].extraPaths 需同步加 "src/agent"，否则运行能过但 pyright 报红
_AGENT_DIR: Path = Path(__file__).resolve().parents[1] / "src" / "agent"
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

import streamlit as st  # noqa: E402  # 需先桥接路径再导第三方无关，仅风格顺序

# 轻依赖资产：盘点页签页面加载就要用（day35_scenario 已不含执行器顶级导入 → 冷启动便宜）
from day35_scenario import (  # noqa: E402
    LOGIN_SCENARIO,
    REGISTER_SCENARIO,
    ScenarioConfig,
    build_blueprint,
    scan_blueprint,
    select_stages,
)
from utils import ROOT, read_text  # noqa: E402

if TYPE_CHECKING:  # 仅静态检查可见（Day38 冷启动瘦身）：这两个只用于类型注解
    from day34_flow_map import StageSpec
    from day34_orchestrator import FlowReport


# ── 场景注册表（数据：UI 只读不改）──
_SCENARIOS: dict[str, ScenarioConfig] = {
    LOGIN_SCENARIO.name: LOGIN_SCENARIO,
    REGISTER_SCENARIO.name: REGISTER_SCENARIO,
}

# ── 结果目录：flow 报告/junit 都在这（相对 ROOT）──
_FLOW_DIR_REL: str = "outputs/flow"


def _scenario_names() -> list[str]:
    """返回可选的场景名（供 selectbox）。"""
    return list(_SCENARIOS.keys())


def _pick_scenario(name: str) -> ScenarioConfig:
    """按名字取场景配置；未知名字回退 login（selectbox 选项保证不会发生）。"""
    return _SCENARIOS.get(name, LOGIN_SCENARIO)


def _load_report_markdowns() -> dict[str, str]:
    """读 outputs/flow 下的 .md 报告（供产物页签展示），返回 {文件名: 内容}。"""
    flow_dir: Path = Path(ROOT) / _FLOW_DIR_REL
    result: dict[str, str] = {}
    if not flow_dir.is_dir():
        return result
    for path in sorted(flow_dir.glob("*.md")):
        result[path.name] = read_text(str(path))
    return result


def _render_scan_table(blueprint: list[StageSpec]) -> list[dict[str, str]]:
    """盘点结果 → 表格行（只做展示整形，不含业务判断；判断在 scan_blueprint 里）。"""
    rows = scan_blueprint(blueprint)
    return [
        {
            "阶段": spec.stage_id,
            "标题": spec.title,
            "类型": spec.kind,
            "执行器": spec.runner,
            "状态": status,
            "说明": reason,
        }
        for spec, status, reason in rows
    ]


def _report_to_rows(report: FlowReport) -> list[dict[str, str | float]]:
    """FlowReport → 表格行（FlowReport.stages: StageRecord 列表）。"""
    out: list[dict[str, str | float]] = []
    for record in report.stages:
        out.append(
            {
                "阶段": record.stage_id,
                "状态": record.status,
                "耗时(s)": record.duration_s,
                "指纹": ", ".join(record.fingerprints),
                "说明": record.detail,
            }
        )
    return out

def _title_of(blueprint: list[StageSpec], stage_id: str) -> str:
    """stage_id → 标题（仅控件展示用；找不到给空串，不抛异常）。"""
    return next((spec.title for spec in blueprint if spec.stage_id == stage_id), "")


def _fmt_stage(blueprint: list[StageSpec], stage_id: str) -> str:
    """多选框的显示文案：`S8_exec_report · JUnit → 执行报告（缺陷反查注册表）`。

    ⚠️ 精确 id 必须显示在最前面：文档/CLI 里出现的都是 stage_id，
       把它藏起来（只显示标题）会让"页面上选了哪段"对不上日志。
    """
    return f"{stage_id} · {_title_of(blueprint, stage_id)}"


def _resolve_ui_stages(blueprint: list[StageSpec], picked: list[str]) -> list[StageSpec]:
    """UI 侧选段：空选 = 全流程；非空 = 精确 id 子集 + 自动补齐上游依赖闭包。

    为什么 UI 不复用 CLI 的 `resolve_stage_ids`（Day 38 决策，别"顺手统一"）：
      · 那个函数是**命令行特有的容错**——用户敲的是裸字符串（`S4`），所以要"唯一前缀
        猜谜 + 歧义报错"，而它 raise 的是 `click.BadParameter`；
      · UI 的输入来自 **multiselect 的 options**，选项就是 `build_blueprint` 自己给出的
        精确 stage_id → 天然精确、天然无歧义，既不需要猜谜也不需要校验；
      · 跨入口层横向 import（`ui` 引 `cli`）会把 click 拉进 UI 冷启动，还会制造
        "两个入口互为依赖"的假耦合。
    闭包补齐这一步是**资产层的业务**，所以委托 `select_stages`（UI 不自己写图算法）。
    """
    if not picked:
        return blueprint
    return select_stages(blueprint, set(picked))


def main() -> None:
    """页面主体（streamlit run 把本文件当 __main__ 执行）。"""
    st.set_page_config(page_title="AI 测试 Agent 操作台", page_icon=":test_tube:", layout="wide")
    st.title(":test_tube: AI 测试全流程 Agent 操作台")
    st.caption("第 4 层入口层：业务全部委托 day29-35 编排资产（蓝图/实现/执行器）")

    # ── 侧边栏：场景 + 执行档位（数据收集区）──
    with st.sidebar:
        st.header("参数")
        scenario_name: str = st.selectbox("被测场景", _scenario_names(), index=0)
        with_llm: bool = st.checkbox("调用真实 LLM（模型段）", value=False,
                                     help="关：llm 段显示 skipped_needs_api；开：需 .env 有 GEMINI_API_KEY")
        bug_probe_on: bool = st.checkbox("执行档位：S7 变异自验证对照", value=True,
                                         help="Day36 定稿档位：默认开（向后兼容）；关则摘 S7、S8 报告自适应")
        force: bool = st.checkbox("强制重跑（忽略既有产物）", value=False)
        fail_fast: bool = st.checkbox("遇失败即中断（fail_fast）", value=False)

    sc: ScenarioConfig = _pick_scenario(scenario_name).model_copy(update={"bug_probe": bug_probe_on})
    blueprint: list[StageSpec] = build_blueprint(sc)

    # ── 三个页签 ──
    tab_overview, tab_run, tab_artifacts = st.tabs(["🗺️ 蓝图盘点", "▶ 全流程执行", "📁 产物浏览"])

    with tab_overview:
        st.subheader(f"蓝图盘点（{scenario_name} · {len(blueprint)} 段 · 零 API）")
        rows: list[dict[str, str]] = _render_scan_table(blueprint)
        st.dataframe(rows, width="stretch", hide_index=True)
        st.caption("状态图例：reused=产物在位可回放 · run_ready=code 段现场跑 · needs_api=llm 段待补跑 · "
                   "missing_input=资产缺口（register 缺 schemas/bugs 即此态）· manual_pending=评审门等人")

    with tab_run:
        st.subheader("全流程执行")
        st.write("按蓝图顺序执行：失败隔离（一段挂了不中断），勾 fail_fast 才中断。")

        # ── 选段（Day39 5.13）：options 来自【当前档位的蓝图】—— 关掉 S7 时它就不在选项里 ──
        picked: list[str] = st.multiselect(
            "只跑指定阶段（留空 = 全流程）",
            options=[spec.stage_id for spec in blueprint],
            default=[],
            format_func=lambda sid: _fmt_stage(blueprint, sid),
            key=f"stage_pick_{scenario_name}_{bug_probe_on}",
            help="依赖上游自动补齐（闭包）：只选 S8_exec_report → 自动带上 S3/S4/S6/S7。",
        )
        plan: list[StageSpec] = _resolve_ui_stages(blueprint, picked)
        if not plan:
            st.error("当前档位下没有可执行的段（选择已被档位过滤，如关档位后仍选着 S7）→ 请重选。")
        elif picked:
            added: list[str] = [spec.stage_id for spec in plan if spec.stage_id not in set(picked)]
            st.info(f"子集执行：{len(plan)} 段（自动补齐上游 {len(added)} 段：{', '.join(added) or '无'}）")
        else:
            st.caption(f"全流程：{len(plan)} 段（未选段 = 全跑，与 CLI 不带 --stage 一致）")

        if st.button("▶ 执行", type="primary", disabled=not plan):
            from day34_orchestrator import run_flow  # 延迟导入（Day38）：页面加载不为它付冷启动

            with st.spinner("正在执行（mock/报告段本地跑，模型段按档位跳过或调真 API）..."):
                report = run_flow(blueprint=plan, with_llm=with_llm,
                                  force=force, fail_fast=fail_fast)
            st.session_state["last_report"] = report
            st.session_state["last_scenario"] = scenario_name
            st.session_state["last_bug_probe"] = bug_probe_on
            st.session_state["last_stages"] = [spec.stage_id for spec in plan]
        if "last_report" in st.session_state:
            scope: list[str] = st.session_state.get("last_stages", [])
            st.success(f"最近一次执行：场景 {st.session_state['last_scenario']} · "
                       f"bug_probe={st.session_state['last_bug_probe']} · {len(scope)} 段"
                       + ("（全流程）" if len(scope) == len(blueprint) else "（子集）"))
            st.dataframe(_report_to_rows(st.session_state["last_report"]),
                         width="stretch", hide_index=True)

    with tab_artifacts:
        st.subheader("产物浏览（outputs/flow）")
        reports: dict[str, str] = _load_report_markdowns()
        if not reports:
            st.info("outputs/flow 下暂无 .md 报告——先到「全流程执行」跑一次。")
        else:
            picked_report: str = st.selectbox("选择报告", list(reports.keys()))
            st.markdown(reports[picked_report])


if __name__ == "__main__":
    main()
