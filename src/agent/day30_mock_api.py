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

def make_handler(bug_mode: bool = False) -> type[BaseHTTPRequestHandler]:
    """动态生成双接口 handler（闭包捕获 bug_mode，Day 28 模式）。"""

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


def start_mock(port: int = 8766, bug_mode: bool = False) -> HTTPServer:
    """启动双接口 mock（后台线程），返回 server 实例。

    ⚠️ stop_mock() 必须从【外部线程】调用（handler 内 shutdown 会死锁，Day 27 坑位）。
    """
    global _server
    if _server is not None:
        return _server
    try:
        server: HTTPServer = HTTPServer(("127.0.0.1", port), make_handler(bug_mode))
    except OSError as exc:
        raise RuntimeError(f"端口 {port} 被占用，换一个端口重试（start_mock(port=...)）") from exc
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _server = server
    mode: str = "埋Bug版" if bug_mode else "正常版"
    print(f"✅ 双接口 mock（{mode}）已启动: http://127.0.0.1:{port}（POST /api/login + GET /api/orders）")
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





if __name__ == "__main__":
    # verify_mock()
    verify_bug_mock()
    print("\n💡 要点回顾：")
    print("   mock = 接口契约的最小实现（文档是契约，mock 是实现，测试校验契约）")
    print("   bug_mode 埋两类生产缺陷：错误凭据 500（异常未处理）+ 无 token 200（越权漏洞）")