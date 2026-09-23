"""
Day 30 练习 4：双接口 mock 靶场 —— POST /api/login（公开）+ GET /api/orders（需鉴权）

与 day28_mock_api.py 的关系（对照版，不修改 Day 28 文件）：
  - 双接口：登录（公开，测 正常/参数缺失/错误凭据）+ 订单（需鉴权，测 正常/越权）
  - bug_mode=True 埋 2 个缺陷（生产常见的两类问题）：
    🐛 缺陷 1：login 错误凭据 → 500（应 401——服务端把错误凭据当未捕获异常抛出）
    🐛 缺陷 2：orders 无 token → 200 返回数据（应 401——接口忘了鉴权 = 越权漏洞）

接口契约（与 docs/apis/login_api.md 严格对齐）：
  POST /api/login：
    - 空 phone 或空 password             → 400 {"code": 40001, "message": "手机号和密码不能为空"}
    - password 长度 < 8                  → 400 {"code": 40002, "message": "密码长度不能少于8位"}
    - phone 格式错误                     → 400 {"code": 40003, "message": "手机号格式错误"}
    - phone=13800138000 & password=Test123456 → 200 {"code": 0, "message": "登录成功", "data": {"token": "demo-token-123"}}
    - 其他（错误凭据）                  → 401 {"code": 40101, "message": "手机号或密码错误"}（bug_mode → 500）
  GET /api/orders：
    - Authorization: Bearer demo-token-123 → 200 {"code": 0, "data": {"orders": [{"id": "ORD-1001", "amount": 99.5}]}}
    - 无/错 token                       → 401 {"code": 40101, "message": "未授权"}(bug_mode → 200 泄露数据)
  其他路径 → 404

用法：
  python day30_mock_api.py              # verify 双接口（零外网）
  python -c "from day30_mock_api import start_mock, stop_mock; ..."
"""

import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

VALID_PHONE: str = "13800138000"
VALID_PASSWORD: str = "Test123456"
VALID_TOKEN: str = "demo-token-123"
PHONE_RE: re.Pattern[str] = re.compile(r"^1[3-9]\d{9}$")

# ── 注册场景契约（Day 41 新增，与 docs/apis/register_api.json 严格对齐）──
VALID_REGISTER_PHONE: str = "13900139000"
VALID_SMS_CODE: str = "123456"
REGISTER_USER_ID: str = "U10001"

# ── 退款场景契约（Day 42 新增，与 docs/apis/refund_api.json 严格对齐）──
VALID_ORDER_NO: str = "ORD-1001"
VALID_REFUND_AMOUNT: str = "99.5"
REFUND_ID: str = "RF10001"

def make_handler(bug_mode: bool = False, scenario: str = "login") -> type[BaseHTTPRequestHandler]:
    """按场景生成 handler（Day 41：mock 靶场从"只有登录"变成"按场景分派"）。

    scenario 决定实现哪套接口：
      "login"    → POST /api/login + GET /api/orders（**原实现逐字未动**）
      "register" → POST /api/register（短信验证码注册）
      "refund"   → POST /api/refund（订单退款申请）
    其他值 → 落到 login 分支（调用方传错场景时至少行为可预测；真起不来会 404 现形）。

    ⚠️ 为什么必须加这个维度：S6/S7 是「把生成的套件打到 mock 上」。没有场景维度的
       mock 只有 login 两个接口 → register 的套件全打 404 → 而执行器把"有用例失败"
       判为合法结果 → **绿着错**（报告里 4 条失败全被当成"发现了缺陷"）。
    """
    if scenario == "register":
        return _make_register_handler(bug_mode)
    if scenario == "refund":
        return _make_refund_handler(bug_mode)
    return _make_login_handler(bug_mode)

def _make_login_handler(bug_mode: bool = False) -> type[BaseHTTPRequestHandler]:
    """登录场景 handler：POST /api/login（公开）+ GET /api/orders（需鉴权）。"""

    def _do_post(self: BaseHTTPRequestHandler) -> None:
        if self.path != "/api/login":
            _send_json(self, 404, {"code": 40400, "message": f"未知接口 {self.path}"})
            return
        payload: dict[str, object] = _read_json(self)
        phone_raw: object = payload.get("phone", "")
        password_raw: object = payload.get("password", "")
        phone: str = phone_raw if isinstance(phone_raw, str) else ""
        password: str = password_raw if isinstance(password_raw, str) else ""
        if not phone or not password:
            _send_json(self, 400, {"code": 40001, "message": "手机号和密码不能为空"})
        elif len(password) < 8:
            _send_json(self, 400, {"code": 40002, "message": "密码长度不能少于8位"})
        elif not PHONE_RE.fullmatch(phone):
            _send_json(self, 400, {"code": 40003, "message": "手机号格式错误"})
        elif phone == VALID_PHONE and password == VALID_PASSWORD:
            _send_json(self, 200, {"code": 0, "message": "登录成功", "data": {"token": VALID_TOKEN}})
        elif bug_mode:
            # 🐛 缺陷 1：错误凭据应 401，这里 500（服务端未捕获异常）
            _send_json(self, 500, {"code": 50000, "message": "服务端内部异常（错误凭据未捕获）"})
        else:
            _send_json(self, 401, {"code": 40101, "message": "手机号或密码错误"})

    def _do_get(self: BaseHTTPRequestHandler) -> None:
        if self.path != "/api/orders":
            _send_json(self, 404, {"code": 40400, "message": f"未知接口 {self.path}"})
            return
        auth: str = self.headers.get("Authorization", "")
        if auth == f"Bearer {VALID_TOKEN}":
            orders: list[dict[str, object]] = [
                {"id": "ORD-1001", "amount": 99.5},
                {"id": "ORD-1002", "amount": 199.0},
            ]
            _send_json(self, 200, {"code": 0, "data": {"orders": orders}})
        elif bug_mode:
            # 🐛 缺陷 2：无 token 应 401，这里 200 返回数据（越权漏洞：忘了鉴权）
            _send_json(self, 200, {"code": 0, "data": {"orders": []}})
        else:
            _send_json(self, 401, {"code": 40101, "message": "未授权"})

    class DualHandler(BaseHTTPRequestHandler):
        """双接口 handler（do_POST/do_GET 覆盖父类方法，无需返回注解）。"""

        do_POST = _do_post
        do_GET = _do_get

        def log_message(self, format: str, *args: object) -> None:
            """静音默认日志（避免测试刷屏）。"""
            return

    return DualHandler

def _make_register_handler(bug_mode: bool = False) -> type[BaseHTTPRequestHandler]:
    """注册场景 handler：POST /api/register（手机号 + 短信验证码）。

    接口契约（与 docs/apis/register_api.json 对齐）：
      空 phone 或空 code                    → 400 {"code": 40001}
      phone=13900139000 & code=123456       → 200 {"code": 0, "data": {"user_id": "U10001"}}
      其他（验证码不匹配）                  → 401 {"code": 40101}（bug_mode → 200 且真的建号）
    其他路径 → 404；GET 一律 404（本场景暂无查询接口）。

    🐛 埋 Bug（bug_mode=True）：**验证码根本不校验** → 任意 code 都能注册成功。
       对应 docs/bugs/register_bugs.md 的 BUG-R01（验证码形同虚设）。
    """

    def _do_post(self: BaseHTTPRequestHandler) -> None:
        if self.path != "/api/register":
            _send_json(self, 404, {"code": 40400, "message": f"未知接口 {self.path}"})
            return
        payload: dict[str, object] = _read_json(self)
        code_raw: object = payload.get("code", "")
        phone_raw: object = payload.get("phone", "")
        code: str = code_raw if isinstance(code_raw, str) else ""
        phone: str = phone_raw if isinstance(phone_raw, str) else ""
        success: dict[str, object] = {
            "code": 0, "message": "注册成功", "data": {"user_id": REGISTER_USER_ID},
        }
        if not phone or not code:
            _send_json(self, 400, {"code": 40001, "message": "手机号和验证码不能为空"})
        elif phone == VALID_REGISTER_PHONE and code == VALID_SMS_CODE:
            _send_json(self, 200, success)
        elif bug_mode:
            # 🐛 缺陷：验证码未校验 → 错误验证码也注册成功（应 401）
            _send_json(self, 200, success)
        else:
            _send_json(self, 401, {"code": 40101, "message": "验证码错误"})

    def _do_get(self: BaseHTTPRequestHandler) -> None:
        _send_json(self, 404, {"code": 40400, "message": f"注册场景未实现 GET {self.path}"})

    class RegisterHandler(BaseHTTPRequestHandler):
        """注册接口 handler。"""

        do_POST = _do_post
        do_GET = _do_get

        def log_message(self, format: str, *args: object) -> None:
            """静音默认日志（避免测试刷屏）。"""
            return

    return RegisterHandler

def _make_refund_handler(bug_mode: bool = False) -> type[BaseHTTPRequestHandler]:
    """退款场景 handler：POST /api/refund（订单号 + 退款金额）。

    接口契约（与 docs/apis/refund_api.json 对齐）：
      空 order_id 或空 amount                → 400 {"code": 40001}
      order_id=ORD-1001 & amount=99.5        → 200 {"code": 0, "data": {"refund_id": "RF10001"}}
      其他（订单号不存在/不属于当前用户）    → 401 {"code": 40101}
      其他路径 → 404；GET 一律 404（本场景暂无查询接口）。

    🐛 埋 Bug（bug_mode=True）：**校验整段被摘掉** → 一律 200 受理成功。
       对应 docs/bugs/refund_bugs.md 的 BUG-F01（退款接口未做订单归属校验）。
       ⚠️ 与 register 的埋法**不同**：register 只放过「验证码不匹配」一支（S7 红 1 条），
          refund 是「所有分支全放过」（S7 红 3 条）——
          **埋 Bug 的爆炸半径决定 S7 的红度**，这本身是个值得看的观测。
    """

    def _do_post(self: BaseHTTPRequestHandler) -> None:
        if self.path != "/api/refund":
            _send_json(self, 404, {"code": 40400, "message": f"未知接口 {self.path}"})
            return
        payload: dict[str, object] = _read_json(self)
        order_raw: object = payload.get("order_id", "")
        amount_raw: object = payload.get("amount", "")
        order_no: str = order_raw if isinstance(order_raw, str) else ""
        amount: str = amount_raw if isinstance(amount_raw, str) else ""
        success: dict[str, object] = {
            "code": 0, "message": "退款申请已受理", "data": {"refund_id": REFUND_ID},
        }
        if bug_mode:
            # 🐛 缺陷：校验整段被摘掉 → 空参（应 400）与非法订单号（应 401）也一律受理
            _send_json(self, 200, success)
        elif not order_no or not amount:
            _send_json(self, 400, {"code": 40001, "message": "订单号和退款金额不能为空"})
        elif order_no == VALID_ORDER_NO and amount == VALID_REFUND_AMOUNT:
            _send_json(self, 200, success)
        else:
            _send_json(self, 401, {"code": 40101, "message": "订单不存在或不属于当前用户"})

    def _do_get(self: BaseHTTPRequestHandler) -> None:
        _send_json(self, 404, {"code": 40400, "message": f"退款场景未实现 GET {self.path}"})

    class RefundHandler(BaseHTTPRequestHandler):
        """退款接口 handler。"""

        do_POST = _do_post
        do_GET = _do_get

        def log_message(self, format: str, *args: object) -> None:
            """静音默认日志（避免测试刷屏）。"""
            return

    return RefundHandler


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, object]:
    """读取请求体并解析 JSON（Content-Length 是 str|None → or '0'，Day 27 坑位）。"""
    length_raw: str | None = handler.headers.get("Content-Length")
    length: int = int(length_raw or "0")
    raw: bytes = handler.rfile.read(length)
    try:
        data: object = json.loads(raw or b"{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _send_json(handler: BaseHTTPRequestHandler, status: int, payload: dict[str, object]) -> None:
    """写 JSON 响应（显式 Content-Length + utf-8）。"""
    body: bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


# ═══════════════════════════════════════════════════════
# 服务启停（全局 server + 后台线程，Day 27/28 模式）
# ═══════════════════════════════════════════════════════

_server: HTTPServer | None = None


def start_mock(port: int = 8766, bug_mode: bool = False, scenario: str = "login") -> HTTPServer:
    """启动双接口 mock（后台线程），返回 server 实例。

    ⚠️ stop_mock() 必须从【外部线程】调用（handler 内 shutdown 会死锁，Day 27 坑位）。
    """
    global _server
    if _server is not None:
        return _server
    try:
        server: HTTPServer = HTTPServer(("127.0.0.1", port), make_handler(bug_mode, scenario))
    except OSError as exc:
        raise RuntimeError(f"端口 {port} 被占用，换一个端口重试（start_mock(port=...)）") from exc
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _server = server
    mode: str = "埋Bug版" if bug_mode else "正常版"
    print(f"✅ [{scenario}] mock（{mode}）已启动: http://127.0.0.1:{port}")
    return server


def stop_mock() -> None:
    """关闭 mock 服务（幂等）。"""
    global _server
    if _server is not None:
        _server.shutdown()
        _server.server_close()
        _server = None
        print("✅ 双接口 mock 已关闭")


# ═══════════════════════════════════════════════════════
# 实验
# ═══════════════════════════════════════════════════════

def _fire(port: int, method: str, path: str, name: str, body: dict[str, str] | None = None,
          headers: dict[str, str] | None = None, expect_status: int = 200) -> None:
    """打一枪并断言状态码（verify 复用）。"""
    import requests  # noqa: PLC0415

    resp = requests.request(method, f"http://127.0.0.1:{port}{path}", json=body, headers=headers or {}, timeout=5)
    ok: bool = resp.status_code == expect_status
    print(f"  {name}: status={resp.status_code} body={resp.json()}  → {'✅' if ok else '❌'}")
    assert ok, f"{name} 分支不符合预期（期望 {expect_status}）"


def verify_mock(port: int = 8766) -> None:
    """正常版 7 分支验证（login 4 + orders 3，零外网）。"""
    print("=" * 60)
    print("实验：verify_mock —— 正常版 7 分支")
    server = start_mock(port)
    try:
        _fire(port, "POST", "/api/login", "正常登录", {"phone": VALID_PHONE, "password": VALID_PASSWORD}, expect_status=200)
        _fire(port, "POST", "/api/login", "空手机号", {"phone": "", "password": VALID_PASSWORD}, expect_status=400)
        _fire(port, "POST", "/api/login", "短密码", {"phone": VALID_PHONE, "password": "123"}, expect_status=400)
        _fire(port, "POST", "/api/login", "错误凭据", {"phone": VALID_PHONE, "password": "WrongPass1"}, expect_status=401)
        _fire(port, "GET", "/api/orders", "带 token 查订单", headers={"Authorization": f"Bearer {VALID_TOKEN}"}, expect_status=200)
        _fire(port, "GET", "/api/orders", "无 token", headers={}, expect_status=401)
        _fire(port, "GET", "/api/orders", "错 token", headers={"Authorization": "Bearer wrong-token"}, expect_status=401)
        print("✅ 正常版 7 分支全部符合预期")
    finally:
        stop_mock()


def verify_bug_mock(port: int = 8766) -> None:
    """埋 Bug 版验证：2 个缺陷分支行为确认（缺陷 1 → 500；缺陷 2 → 200 泄露）。"""
    print("=" * 60)
    print("实验：verify_bug_mock —— 埋 Bug 版（缺陷 1: 错误凭据→500；缺陷 2: 无 token→200）")
    server = start_mock(port, bug_mode=True)
    try:
        _fire(port, "POST", "/api/login", "错误凭据（应401实际500）", {"phone": VALID_PHONE, "password": "WrongPass1"}, expect_status=500)
        _fire(port, "GET", "/api/orders", "无 token（应401实际200）", headers={}, expect_status=200)
        print("✅ 埋 Bug 版缺陷行为确认（两个缺陷都在）")
    finally:
        stop_mock()

def verify_register_mock(port: int = 8767) -> None:
    """注册场景 4 分支验证（正常/缺 phone/缺 code/错验证码，零外网）。

    ⚠️ 端口用 8767（= docs/apis/register_api.json 的 base_url 端口）。
    """
    print("=" * 60)
    print("实验：verify_register_mock —— register 场景 4 分支")
    start_mock(port, scenario="register")
    try:
        _fire(port, "POST", "/api/register", "正常注册",
              {"code": VALID_SMS_CODE, "phone": VALID_REGISTER_PHONE}, expect_status=200)
        _fire(port, "POST", "/api/register", "缺 phone",
              {"code": VALID_SMS_CODE}, expect_status=400)
        _fire(port, "POST", "/api/register", "缺 code",
              {"phone": VALID_REGISTER_PHONE}, expect_status=400)
        _fire(port, "POST", "/api/register", "错验证码",
              {"code": "000000", "phone": VALID_REGISTER_PHONE}, expect_status=401)
        print("✅ register 正常版 4 分支全部符合预期")
    finally:
        stop_mock()

def verify_register_bug_mock(port: int = 8767) -> None:
    """注册场景埋 Bug 版验证：缺陷 BUG-R01（验证码未校验）行为确认。

    ⚠️ 端口用 8767（= docs/apis/register_api.json 的 base_url 端口）。
    正常分支不受影响、缺参仍是 400 —— 只有「验证码不匹配」这一支被放过，
    所以 S7 里那条期望 401 的用例会失败 → 缺陷现形。
    """
    print("=" * 60)
    print("实验：verify_register_bug_mock —— 埋 Bug 版（缺陷: 验证码未校验 → 应401实际200）")
    start_mock(port, bug_mode=True, scenario="register")
    try:
        _fire(port, "POST", "/api/register", "正常注册（不受影响）",
              {"code": VALID_SMS_CODE, "phone": VALID_REGISTER_PHONE}, expect_status=200)
        _fire(port, "POST", "/api/register", "错验证码（应401实际200）",
              {"code": "000000", "phone": VALID_REGISTER_PHONE}, expect_status=200)
        _fire(port, "POST", "/api/register", "缺 phone（仍 400）",
              {"code": VALID_SMS_CODE}, expect_status=400)
        print("✅ 埋 Bug 版缺陷行为确认（验证码未校验）")
    finally:
        stop_mock()

def verify_refund_mock(port: int = 8768) -> None:
    """退款场景 4 分支验证（正常/缺 order_id/缺 amount/非法订单号，零外网）。

    ⚠️ 端口用 8768（= docs/apis/refund_api.json 的 base_url 端口）。
    """
    print("=" * 60)
    print("实验：verify_refund_mock —— refund 场景 4 分支")
    start_mock(port, scenario="refund")
    try:
        _fire(port, "POST", "/api/refund", "正常退款申请",
              {"order_id": VALID_ORDER_NO, "amount": VALID_REFUND_AMOUNT}, expect_status=200)
        _fire(port, "POST", "/api/refund", "缺 order_id",
              {"amount": VALID_REFUND_AMOUNT}, expect_status=400)
        _fire(port, "POST", "/api/refund", "缺 amount",
              {"order_id": VALID_ORDER_NO}, expect_status=400)
        _fire(port, "POST", "/api/refund", "非法订单号",
              {"order_id": "invalid_value", "amount": VALID_REFUND_AMOUNT}, expect_status=401)
        print("✅ refund 正常版 4 分支全部符合预期")
    finally:
        stop_mock()

def verify_refund_bug_mock(port: int = 8768) -> None:
    """退款场景埋 Bug 版验证：缺陷 BUG-F01（校验整段被摘掉）行为确认。

    ⚠️ 端口用 8768（= docs/apis/refund_api.json 的 base_url 端口）。
    三支全部被放过（空参 200 / 非法订单号 200），只有正常申请**看不出来** ——
    所以 S7 里 4 个 node 会有 3 个失败：**缺陷的爆炸半径直接决定红了几条**。
    """
    print("=" * 60)
    print("实验：verify_refund_bug_mock —— 埋 Bug 版（缺陷: 校验被摘掉 → 空参/非法单号都 200）")
    start_mock(port, bug_mode=True, scenario="refund")
    try:
        _fire(port, "POST", "/api/refund", "正常退款申请（看不出来）",
              {"order_id": VALID_ORDER_NO, "amount": VALID_REFUND_AMOUNT}, expect_status=200)
        _fire(port, "POST", "/api/refund", "缺 order_id（应400实际200）",
              {"amount": VALID_REFUND_AMOUNT}, expect_status=200)
        _fire(port, "POST", "/api/refund", "非法订单号（应401实际200）",
              {"order_id": "invalid_value", "amount": VALID_REFUND_AMOUNT}, expect_status=200)
        print("✅ 埋 Bug 版缺陷行为确认（校验整段被摘掉）")
    finally:
        stop_mock()

if __name__ == "__main__":
    # verify_mock()
    verify_bug_mock()
    print("\n💡 要点回顾：")
    print("   mock = 接口契约的最小实现（文档是契约，mock 是实现，测试校验契约）")
    print("   bug_mode 埋两类生产缺陷：错误凭据 500（异常未处理）+ 无 token 200（越权漏洞）")