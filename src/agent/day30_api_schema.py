"""
Day 30 练习 1/2：接口文档 → 结构化接口计划（ApiDoc Schema + 加载分派 + 解析 Chain + 三件套计划）

设计（步骤 1 的 4 个决策落地）：
  A. 主线形态 = Chain（固定单任务）：prompt | llm.with_fallbacks | with_structured_output(ApiDoc)
  B. 分层：模型只出"接口语义"（ApiDoc），pytest 代码由 day30_pytest_generator 模板渲染
  C. 三件套计划（正常/参数缺失/越权或错误凭据）由确定性代码生成——学习计划硬性要求
  D. 分段闭环：plan 落盘 json+md（可评审）→ 练习 3 从 json 读回再生成代码（不重跑 LLM）

加载分派（教学点）：
  .md/.txt  → 人写文档 → 模型解析（LLM）
  .json     → 机器可读文档 → 确定性解析（json.loads + model_validate，零 LLM）
  ——"机器能读懂的用代码，只有人写文档才用模型"

实验：
  exp1_schema_smoke()   零 API：手工构造 ApiDoc → 渲染可评审文本 → 断言
  exp2_analyze_file()   端到端：docs/apis/login_api.md → ApiDoc → plan 落盘（真实 API）
  exp3_plan_demo()      零 API：确定性三件套计划断言（login 公开 + orders 需鉴权）

用法：
  python -c "from day30_api_schema import exp3_plan_demo; exp3_plan_demo()"  # 零 API
  python day30_api_schema.py   # 默认跑纯逻辑实验（真实 API 取消注释）
"""

import json
import os
import sys
from dataclasses import dataclass, field

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()  # ⚠️ 必须在 langchain import 之前（Day 25 口诀）

from typing import Literal

from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, Field

from day29_doc_loader import load_document

# ═══════════════════════════════════════════════════════
# ApiDoc 分级 Schema（设计决策 B：接口语义，模型只出这个）
# ═══════════════════════════════════════════════════════

ParamLocation = Literal["path", "query", "header", "body"]
HttpMethod = Literal["GET", "POST", "PUT", "DELETE", "PATCH"]

here: str = os.path.dirname(os.path.abspath(__file__))
API_DIR: str = os.path.join(here, "..", "..", "docs", "apis")

class ApiParam(BaseModel):
    """单个请求参数（模型从文档提取，example 供测试模板填参数值）。"""

    name: str = Field(description="参数名")
    location: ParamLocation = Field(description="参数位置：path/query/header/body")
    required: bool = Field(default=True, description="是否必填")
    param_type: str = Field(default="string", description="参数类型：string/int/bool 等")
    example: str = Field(default="", description="合法示例值（测试正常调用时使用）")
    description: str = Field(default="", description="参数说明")


class ApiEndpoint(BaseModel):
    """一个接口端点的语义（含测试期望码——期望值来自文档，不是拍脑袋）。"""

    name: str = Field(description="接口名，如 '用户登录'")
    method: HttpMethod = Field(description="HTTP 方法")
    path: str = Field(description="接口路径，如 /api/login")
    summary: str = Field(default="", description="接口功能一句话说明")
    params: list[ApiParam] = Field(default_factory=list, description="请求参数列表")
    auth_required: bool = Field(default=True, description="是否需要鉴权（true=需 token，决定越权测试）")
    expected_status: int = Field(default=200, description="正常调用期望状态码")
    error_status: int = Field(default=400, description="参数缺失/非法输入期望状态码")
    unauthorized_status: int = Field(default=401, description="未授权/越权期望状态码")
    response_fields: list[str] = Field(default_factory=list, description="响应体结构断言字段，如 ['code','data.token']")


class ApiDoc(BaseModel):
    """接口文档解析结果（练习 3 的 pytest 渲染器输入）。"""

    title: str = Field(description="接口文档标题")
    base_url: str = Field(default="http://127.0.0.1:8766", description="服务基地址")
    endpoints: list[ApiEndpoint] = Field(description="接口列表")


# ═══════════════════════════════════════════════════════
# 加载分派（教学点：机器可读用代码，人写文档用模型）
# ═══════════════════════════════════════════════════════
def _read_text_file(path: str) -> str | None:
    """读取文本文件内容（OSError 兜底返回 None）。

    ⚠️ 2026-08-30 修正：json 是机器可读结构化数据，不走 load_document
       （Day 29 加载器只支持 .txt/.md/.docx，json 会直接返回 None）→
       标准库 open 读文本 + _parse_api_doc_json 结构化，最干净。
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError as exc:
        print(f"  ⚠️ 读取失败 {path}: {exc}")
        return None


def load_api_doc(path: str) -> ApiDoc | None:
    """按格式分派：.json 确定性解析（零 LLM，绕开 load_document）；.md/.txt 模型解析。

    ⚠️ .json 解析失败（字段不对）→ 返回 None + 打印原因，不抛异常。
    ⚠️ 2026-08-30 修正：.json 不走 load_document——通用加载器只服务"人写的文档"
       （.txt/.md/.docx），json 是机器可读数据 → open 读文本 + json.loads 最干净。
    """
    ext: str = os.path.splitext(path)[1].lower()
    if ext == ".json":
        text: str | None = _read_text_file(path)
        if text is None:
            return None
        return _parse_api_doc_json(text, source=os.path.basename(path))
    doc = load_document(path)
    if doc is None:
        return None
    return analyze_api_doc(doc.text)


def _parse_api_doc_json(text: str, source: str) -> ApiDoc | None:
    """确定性解析：json.loads → 校验 dict → ApiDoc.model_validate（零 LLM）。"""
    try:
        data: object = json.loads(text)
    except json.JSONDecodeError as exc:
        print(f"  ⚠️ JSON 解析失败 {source}: {exc}")
        return None
    if not isinstance(data, dict):
        print(f"  ⚠️ {source} 的 JSON 顶层必须是对象（dict）")
        return None
    return ApiDoc.model_validate(data)


# ═══════════════════════════════════════════════════════
# 解析 Chain（设计决策 A：固定单任务 + with_fallbacks 容错）
# ═══════════════════════════════════════════════════════

API_DOC_PARSE_PROMPT = """你是一名接口测试工程师，擅长从接口文档中提取结构化接口信息。

接口文档：
{api_doc}

请按以下要求解析（输出符合给定 Schema）：

【每个端点必须提取】
1. name：接口名（如 用户登录）；method/path：HTTP 方法与路径（如 POST /api/login）
2. params：请求参数列表——name/location（body/query/header/path）/required（是否必填）/
   param_type（string/int/bool）/example（**合法示例值**，测试正常调用时用，必须从文档示例或字段规则推断）/
   description（参数说明）
3. auth_required：是否需鉴权——文档写"需要鉴权/Bearer token" → true；登录/注册等公开接口 → false
4. expected_status：正常调用期望状态码（默认 200）；error_status：参数缺失/非法输入期望码（文档错误响应里的 4xx）；
   unauthorized_status：未授权/越权期望码（如 401/403）
5. response_fields：响应体结构断言字段——从"响应体结构/正常响应"里提取关键路径，
   嵌套用点号（如 code、data.token、data.orders）；不要提具体值（如 token 的内容）

【注意】
- example 必须填合法值（能让接口返回成功），不能留空——三件套的正常调用靠它
- 错误码语义区分：参数问题（缺失/格式/长度）归 error_status；凭据/权限问题归 unauthorized_status
- 若文档没有某个期望码，用该场景的行业惯例（参数错误 400、未授权 401）"""


def build_api_doc_chain():
    """接口解析 Chain：prompt | llm（主+备 with_fallbacks）| 结构化输出。

    ⚠️ 返回注解【留空】（Day 29 口诀 25 的 Chain 版）：让 pyright 推断真实链类型。
    ⚠️ 顺序坑（Day 29 源码级实测，fallbacks.py:592）：【先】with_structured_output
       【再】with_fallbacks——反了 RunnableWithFallbacks.__getattr__ 返回 Any 丢类型检查。
    """
    llm_primary = ChatGoogleGenerativeAI(model="gemini-3.5-flash-lite", thinking_level="medium")  # 主（Day 27 确认）
    # 备：3.1-flash-lite 支持 temperature（0-2，2026-08-27 联网确认）→ 解析是确定性优先任务，设 0.2
    llm_backup = ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite", temperature=0.2)
    main = llm_primary.with_structured_output(ApiDoc)
    backup = llm_backup.with_structured_output(ApiDoc)
    llm = main.with_fallbacks([backup])
    prompt = ChatPromptTemplate.from_messages([
        ("system", API_DOC_PARSE_PROMPT),
        ("human", "请解析以下接口文档并输出 ApiDoc：\n\n{api_doc}"),
    ])
    return prompt | llm


def analyze_api_doc(text: str) -> ApiDoc:
    """一行函数入口：接口文档文本 → ApiDoc（Pydantic 实例）。

    ⚠️ 返回注解【明确写 ApiDoc】（与 build_api_doc_chain 留空不同）：链 invoke 的静态
       推断是 dict | BaseModel 联合（LCEL 固有限制），运行时收窄 + model_validate 兜底
       （Day 29 坑 1 + 2026-08-27 用户实操二阶收窄经验）。
    """
    chain = build_api_doc_chain()
    result = chain.invoke({"api_doc": text})
    if isinstance(result, ApiDoc):
        return result
    if not isinstance(result, dict):
        raise ValueError(
            f"解析失败：链返回 {type(result).__name__}，期望 dict 或 ApiDoc"
        )
    return ApiDoc.model_validate(result)


def analyze_api_doc_file(path: str) -> ApiDoc | None:
    """加载接口文档 → 解析 → 返回 ApiDoc；加载失败返回 None（fail fast，Day 28 原则）。
    ⚠️ 2026-08-30 修正：.json 不走 load_document（只支持 .txt/.md/.docx）→
       open 读文本 + 确定性解析；.md/.txt 照旧走模型解析。
    """
    ext: str = os.path.splitext(path)[1].lower()
    if ext == ".json":
        text: str | None = _read_text_file(path)
        if text is None:
            return None
        print(f"  📄 已加载: {os.path.basename(path)}（{len(text)} 字符，格式 json）")
        return _parse_api_doc_json(text, source=os.path.basename(path))
    doc = load_document(path)
    if doc is None:
        return None
    print(f"  📄 已加载: {doc.source}（{len(doc.text)} 字符，格式 {doc.format}）")
    return analyze_api_doc(doc.text)


# ═══════════════════════════════════════════════════════
# 三件套计划（设计决策 C：确定性生成——结构代码保证，参数值来自 example）
# ═══════════════════════════════════════════════════════

@dataclass
class PlanCase:
    """一条计划用例（pytest 渲染器的中间表示，不是最终代码）。"""

    case_id: str
    title: str
    category: str                    # normal / missing / unauthorized / invalid_credentials
    http_method: str
    path: str
    body: dict[str, str] = field(default_factory=dict)          # 正常/错误凭据用例的请求体
    headers: dict[str, str] = field(default_factory=dict)       # 正常用例的请求头
    variants: list[dict[str, str]] = field(default_factory=list)  # missing 的 payload 变体 / unauthorized 的 headers 变体
    expected_status: int = 200
    response_fields: list[str] = field(default_factory=list)


@dataclass
class EndpointPlan:
    """一个端点的完整测试计划（三件套必出，学习计划硬性要求）。"""

    endpoint_name: str
    method: str
    path: str
    cases: list[PlanCase] = field(default_factory=list)


CATEGORY_LABEL: dict[str, str] = {
    "normal": "正常调用",
    "missing": "参数缺失",
    "unauthorized": "越权访问",
    "invalid_credentials": "错误凭据",
}

# 测试常量（模板渲染用；与 day30_mock_api 的凭据保持一致）
VALID_PHONE: str = "13800138000"
VALID_PASSWORD: str = "Test123456"
WRONG_PASSWORD: str = "WrongPass1"
VALID_TOKEN: str = "demo-token-123"


def _bad_credentials_body(body: dict[str, str]) -> dict[str, str]:
    """错误凭据的请求体：有 password 字段就换错值；否则替换第一个示例值。"""
    if not body:
        return body
    if "password" in body:
        return {**body, "password": WRONG_PASSWORD}
    first_key: str = next(iter(body))
    return {**body, first_key: "invalid_value"}


def generate_endpoint_plan(endpoint: ApiEndpoint, start_id: int) -> EndpointPlan:
    """一个端点的三件套计划（确定性）：正常 / 参数缺失 / 越权或错误凭据。

    ⚠️ 教学点：公开接口（auth_required=False）没有"越权"概念 → 第三类自动
       换成"错误凭据"（贴合接口语义，不机械套模板）。
    """
    base_body: dict[str, str] = {
        p.name: p.example for p in endpoint.params if p.location == "body" and p.example
    }
    base_headers: dict[str, str] = {}
    if endpoint.auth_required:
        base_headers = {"Authorization": f"Bearer {VALID_TOKEN}"}

    cases: list[PlanCase] = []
    n: int = start_id

    # ① 正常调用
    n += 1
    cases.append(PlanCase(
        case_id=f"TC{n:03d}",
        title=f"{endpoint.name} 正常调用",
        category="normal",
        http_method=endpoint.method,
        path=endpoint.path,
        body=base_body,
        headers=base_headers,
        expected_status=endpoint.expected_status,
        response_fields=endpoint.response_fields,
    ))

    # ② 参数缺失（逐个删必填 body/query 参数；无必填参数的接口自动跳过）
    missing_variants: list[dict[str, str]] = []
    for p in endpoint.params:
        if p.required and p.location in ("body", "query") and p.example:
            missing_variants.append({k: v for k, v in base_body.items() if k != p.name})
    if missing_variants:
        n += 1
        cases.append(PlanCase(
            case_id=f"TC{n:03d}",
            title=f"{endpoint.name} 缺失必填参数",
            category="missing",
            http_method=endpoint.method,
            path=endpoint.path,
            variants=missing_variants,
            expected_status=endpoint.error_status,
        ))

    # ③ 越权访问（需鉴权）/ 错误凭据（公开接口）
    n += 1
    if endpoint.auth_required:
        cases.append(PlanCase(
            case_id=f"TC{n:03d}",
            title=f"{endpoint.name} 越权访问",
            category="unauthorized",
            http_method=endpoint.method,
            path=endpoint.path,
            body=base_body,
            variants=[{}, {"Authorization": "Bearer wrong-token"}],
            expected_status=endpoint.unauthorized_status,
        ))
    else:
        cases.append(PlanCase(
            case_id=f"TC{n:03d}",
            title=f"{endpoint.name} 错误凭据",
            category="invalid_credentials",
            http_method=endpoint.method,
            path=endpoint.path,
            body=_bad_credentials_body(base_body),
            expected_status=endpoint.unauthorized_status,
        ))

    return EndpointPlan(endpoint_name=endpoint.name, method=endpoint.method, path=endpoint.path, cases=cases)


def generate_api_plan(api_doc: ApiDoc) -> list[EndpointPlan]:
    """全部端点的三件套计划（plan id 全局递增）。"""
    plans: list[EndpointPlan] = []
    next_id: int = 0
    for endpoint in api_doc.endpoints:
        plan = generate_endpoint_plan(endpoint, next_id)
        next_id += len(plan.cases)
        plans.append(plan)
    return plans


def render_plan_markdown(api_doc: ApiDoc, plans: list[EndpointPlan]) -> str:
    """渲染可评审的三件套计划（确定性代码，人工评审对象）。"""
    lines: list[str] = [
        f"# 接口测试计划：{api_doc.title}",
        "",
        f"**基地址**: {api_doc.base_url}",
        f"**端点数**: {len(api_doc.endpoints)}",
        "",
        "| ID | 接口 | 类别 | 方法 | 路径 | 期望码 | 请求体 / 变体 |",
        "|----|------|------|------|------|--------|----------------|",
    ]
    for plan in plans:
        for case in plan.cases:
            detail: str = _fmt_case_detail(case)
            lines.append(
                f"| {case.case_id} | {plan.endpoint_name} | {CATEGORY_LABEL.get(case.category, case.category)} "
                f"| {plan.method} | {plan.path} | {case.expected_status} | {detail} |"
            )
    return "\n".join(lines) + "\n"


def _fmt_case_detail(case: PlanCase) -> str:
    """用例详情 → 紧凑字符串（正常/错误凭据显示 body；缺失/越权显示变体数）。"""
    if case.category in ("missing", "unauthorized"):
        return f"{len(case.variants)} 个变体"
    if not case.body:
        return "-"
    return ", ".join(f"{k}={v}" for k, v in case.body.items())


def save_api_plan(api_doc: ApiDoc, plans: list[EndpointPlan], name: str) -> tuple[str, str]:
    """落盘：JSON（= ApiDoc，评审对象 + 练习 3 输入）+ Markdown（计划渲染）。

    ⚠️ 只存 ApiDoc：plan 是 ApiDoc 的确定性函数（generate_api_plan），
       评审通过后从 json 读回 ApiDoc 即可复现同一份 plan（不重跑 LLM）——Day 28 评审门思想。
    """
    out_dir: str = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "outputs")
    os.makedirs(out_dir, exist_ok=True)
    json_path: str = os.path.join(out_dir, f"api_test_plan_{name}.json")
    md_path: str = os.path.join(out_dir, f"api_test_plan_{name}.md")
    with open(json_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(api_doc.model_dump(), ensure_ascii=False, indent=2))
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(render_plan_markdown(api_doc, plans))
    return json_path, md_path


def load_api_plan(path: str) -> ApiDoc | None:
    """从已落盘 json 读回 ApiDoc（练习 3 输入；不重跑 LLM → 评审后行为可复现）。

    ⚠️ 2026-08-30 修正：.json 不走 load_document（Day 29 加载器只支持 .txt/.md/.docx，
       json 会直接返回 None）→ open 读文本 + _parse_api_doc_json 确定性解析。
    """
    text: str | None = _read_text_file(path)
    if text is None:
        return None
    return _parse_api_doc_json(text, source=os.path.basename(path))



# ═══════════════════════════════════════════════════════
# 实验
# ═══════════════════════════════════════════════════════

def exp1_schema_smoke() -> None:
    """实验 1：Schema 冒烟（零 API）——手工构造 ApiDoc → 渲染可评审文本 → 断言。"""
    print("=" * 60)
    print("实验 1：ApiDoc Schema 冒烟（零 API）")
    api_doc = ApiDoc(
        title="登录服务接口",
        base_url="http://127.0.0.1:8766",
        endpoints=[
            ApiEndpoint(
                name="用户登录", method="POST", path="/api/login",
                summary="手机号+密码登录", auth_required=False,
                expected_status=200, error_status=400, unauthorized_status=401,
                response_fields=["code", "data.token"],
                params=[
                    ApiParam(name="phone", location="body", required=True, param_type="string",
                             example="13800138000", description="11 位手机号"),
                    ApiParam(name="password", location="body", required=True, param_type="string",
                             example="Test123456", description="不少于 8 位"),
                ],
            ),
            ApiEndpoint(
                name="查询订单列表", method="GET", path="/api/orders",
                summary="查询当前用户订单", auth_required=True,
                expected_status=200, error_status=400, unauthorized_status=401,
                response_fields=["code", "data.orders"],
                params=[],
            ),
        ],
    )
    assert len(api_doc.endpoints) == 2
    login = api_doc.endpoints[0]
    assert login.path == "/api/login" and login.auth_required is False
    assert login.params[0].example == "13800138000"
    print(f"  ✅ Schema 校验通过: {api_doc.title}，{len(api_doc.endpoints)} 个端点")
    print(f"     {login.name}: {login.method} {login.path}（公开，期望 200/400/401）")
    print(f"     {api_doc.endpoints[1].name}: {api_doc.endpoints[1].method} {api_doc.endpoints[1].path}（需鉴权）")

    # .json 文档确定性解析（机器可读 → 零 LLM）
    json_text = json.dumps(api_doc.model_dump(), ensure_ascii=False)
    parsed: ApiDoc | None = _parse_api_doc_json(json_text, source="inline.json")
    assert parsed is not None and parsed.title == "登录服务接口"
    print("  ✅ .json 确定性解析（json.loads + model_validate，零 LLM）ok")

    # 反例：非法 method → Pydantic 校验失败
    bad = json_text.replace('"POST"', '"TRACE"')
    try:
        _parse_api_doc_json(bad, source="bad.json")
        print("  ❌ 意外：非法 method 竟然通过")
    except Exception as exc:
        print(f"  ✅ 非法 method 被 Pydantic 拦截（{type(exc).__name__}）——枚举硬约束生效")
    print("✅ Schema 冒烟全部通过")


def exp2_analyze_file(path: str, name: str) -> str | None:
    """端到端：加载 → 模型解析 → 三件套计划 → 落盘 json + md（真实 API）。

    返回 Markdown 计划路径（加载失败返回 None）。
    """
    print("=" * 60)
    print(f"实验：exp2_analyze_file —— 接口文档解析（{path}）")
    api_doc: ApiDoc | None = analyze_api_doc_file(path)
    if api_doc is None:
        print("❌ 文档加载/解析失败")
        return None
    plans: list[EndpointPlan] = generate_api_plan(api_doc)
    print(f"  ✅ 解析完成: title={api_doc.title!r}，{len(api_doc.endpoints)} 个端点，{sum(len(p.cases) for p in plans)} 条计划用例")
    for plan in plans:
        print(f"     {plan.method} {plan.path}（{plan.endpoint_name}）→ {len(plan.cases)} 类测试: "
              + " / ".join(CATEGORY_LABEL.get(c.category, c.category) for c in plan.cases))
    json_path, md_path = save_api_plan(api_doc, plans, name)
    print(f"  ✅ 已落盘: {json_path}")
    print(f"               {md_path}")
    print(render_plan_markdown(api_doc, plans)[:900])
    return md_path


def exp3_plan_demo() -> None:
    """实验 3：三件套计划纯逻辑断言（零 API）——login 公开 + orders 需鉴权。"""
    print("=" * 60)
    print("实验：exp3_plan_demo —— 三件套计划确定性生成（零 API）")
    api_doc = ApiDoc(
        title="登录服务接口", base_url="http://127.0.0.1:8766",
        endpoints=[
            ApiEndpoint(
                name="用户登录", method="POST", path="/api/login", auth_required=False,
                expected_status=200, error_status=400, unauthorized_status=401,
                response_fields=["code", "data.token"],
                params=[
                    ApiParam(name="phone", location="body", required=True, param_type="string",
                             example=VALID_PHONE, description="11 位手机号"),
                    ApiParam(name="password", location="body", required=True, param_type="string",
                             example=VALID_PASSWORD, description="不少于 8 位"),
                ],
            ),
            ApiEndpoint(
                name="查询订单列表", method="GET", path="/api/orders", auth_required=True,
                expected_status=200, error_status=400, unauthorized_status=401,
                response_fields=["code", "data.orders"], params=[],
            ),
        ],
    )
    plans: list[EndpointPlan] = generate_api_plan(api_doc)
    assert len(plans) == 2
    login_plan, orders_plan = plans[0], plans[1]

    # login（公开接口）：正常 / 缺失（2 变体）/ 错误凭据 —— 三件套
    login_cats: list[str] = [c.category for c in login_plan.cases]
    assert login_cats == ["normal", "missing", "invalid_credentials"], login_cats
    assert login_plan.cases[0].body == {"phone": VALID_PHONE, "password": VALID_PASSWORD}
    assert len(login_plan.cases[1].variants) == 2          # 删 phone / 删 password
    assert {"phone": VALID_PHONE} in login_plan.cases[1].variants
    assert {"password": VALID_PASSWORD} in login_plan.cases[1].variants
    assert login_plan.cases[2].body["password"] == WRONG_PASSWORD  # 错误凭据自动换错值

    # orders（需鉴权）：正常（带 token）/ 越权（2 变体）——无必填 body 参数 → 无 missing
    orders_cats: list[str] = [c.category for c in orders_plan.cases]
    assert orders_cats == ["normal", "unauthorized"], orders_cats
    assert orders_plan.cases[0].headers == {"Authorization": f"Bearer {VALID_TOKEN}"}
    assert orders_plan.cases[1].variants == [{}, {"Authorization": "Bearer wrong-token"}]

    md: str = render_plan_markdown(api_doc, plans)
    assert "| TC001 | 用户登录 | 正常调用 | POST | /api/login | 200 | phone=13800138000, password=Test123456 |" in md
    assert "| TC005 | 查询订单列表 | 越权访问 | GET | /api/orders | 401 | 2 个变体 |" in md
    print(md)
    print("  ✅ 断言通过：公开接口第三类=错误凭据；需鉴权接口第三类=越权；plan id 全局递增")
    print("✅ 三件套计划冒烟全部通过")


if __name__ == "__main__":
    # exp1_schema_smoke()
    exp2_analyze_file(os.path.join(API_DIR, "login_api.md"), name='login')  # 真实 API，练习 2 跑
    print("\n💡 要点回顾：")
    print("   ApiDoc = 接口语义的收敛点：模型只出这个，pytest 代码交给模板（分层）")
    print("   .md/.txt 走模型解析；.json 走确定性解析——机器能读懂的用代码")
