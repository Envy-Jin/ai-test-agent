"""
Day 28 练习 1：双模式 mock 登录 API —— 正常版 5 分支 / 埋 Bug 版（错误凭据→500）

与 Day 27 day27_mock_api.py 的关系（对照版，不修改 Day 27 文件）：
  - 新增第 4 个校验分支：手机号格式错误 → 400（补测"格式边界"有靶场可打）
  - bug_mode=True 时"错误凭据"分支返回 500 而非 401（模拟生产缺陷：
    服务端把错误凭据当未捕获异常抛出——应该返回标准 401，实际抛 500）
  - 默认端口 8766（Day 27 的 8765 保留，可同时起两个靶场对照）

接口：POST http://127.0.0.1:{port}/api/login
分支（bug_mode=False）：
  - 空 phone 或空 password            → 400 {"code": 40001, "message": "手机号和密码不能为空"}
  - password 长度 < 8                 → 400 {"code": 40002, "message": "密码长度不能少于8位"}
  - phone 格式错误（非 1[3-9] 开头 11 位）→ 400 {"code": 40003, "message": "手机号格式错误"}
  - phone=13800138000 & password=Test123456 → 200 {"code": 0, "message": "登录成功", "data": {"token": "demo-token-123"}}
  - 其他（错误凭据）                  → 401 {"code": 40101, "message": "手机号或密码错误"}
分支（bug_mode=True）：仅最后一行改为 → 500 {"code": 50000, "message": "服务端内部异常（错误凭据未捕获）"}
其他路径 → 404

用法：
  python day28_mock_api.py                                    # 跑两套 verify（正常 + 埋 Bug，零外网）
  python -c "from day28_mock_api import verify_mock; verify_mock()"      # 只验正常版
  python -c "from day28_mock_api import verify_bug_mock; verify_bug_mock()"  # 只验埋 Bug 版
"""
import json
import re
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

# 测试凭据（与知识库播种文档保持一致，见 day28_agent_followup.CREDENTIAL_DOC）
VALID_PHONE: str = "13800138000"
VALID_PASSWORD: str = "Test123456"
PHONE_RE: re.Pattern[str] = re.compile(r"^1[3-9]\d{9}$")


# ═══════════════════════════════════════════════════════
# 闭包工厂：按 bug_mode 动态生成 handler 类
# ═══════════════════════════════════════════════════════

def make_login_handler(bug_mode: bool = False) -> type[BaseHTTPRequestHandler]:
    """动态生成登录 handler 类。

    Python 技巧：http.server 的 handler 类由 HTTPServer 内部实例化（无参构造），
    没法直接传参 → 用闭包把 bug_mode 捕获进类方法的作用域。
    bug_mode=False 正常 5 分支；True 时错误凭据返回 500（埋 Bug）。
    """
    def _do_post(self: BaseHTTPRequestHandler) -> None:
        payload: dict[str, object] = _read_json(self)
        if self.path != "/api/login":
            _send_json(self, 404, {"code": 40400, "message": f"未知接口 {self.path}"})
            return
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
            _send_json(self, 200, {"code": 0, "message": "登录成功", "data": {"token": "demo-token-123"}})
        elif bug_mode:
            # 🐛 埋 Bug：错误凭据应该返回 401（标准语义），这里错误地返回 500
            _send_json(self, 500, {"code": 50000, "message": "服务端内部异常（错误凭据未捕获）"})
        else:
            _send_json(self, 401, {"code": 40101, "message": "手机号或密码错误"})

    class MockLoginHandler(BaseHTTPRequestHandler):
        """双模式登录 handler（do_POST 覆盖父类方法，无需返回注解）。"""

        do_POST = _do_post

        def log_message(self, format: str, *args: object) -> None:
            """静音默认日志（避免测试刷屏）。"""
            return

    return MockLoginHandler


def _read_json(handler: BaseHTTPRequestHandler) -> dict[str, object]:
    """读取请求体并解析 JSON（Content-Length 是 str|None → 兜底 or "0"，Day 27 坑位）。"""
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
# 服务启停（全局 server 变量 + 后台线程，Day 27 模式）
# ═══════════════════════════════════════════════════════

_server: HTTPServer | None = None


def start_mock(port: int = 8766, bug_mode: bool = False) -> HTTPServer:
    """启动 mock 登录接口（后台线程），返回 server 实例。

    ⚠️ stop_mock() 必须从【外部线程】调用（handler 内调用 shutdown 会死锁，Day 27 坑位）。
    """
    global _server
    if _server is not None:
        return _server
    try:
        server: HTTPServer = HTTPServer(("127.0.0.1", port), make_login_handler(bug_mode))
    except OSError as exc:
        raise RuntimeError(f"端口 {port} 被占用，换一个端口重试（start_mock(port=...)）") from exc
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _server = server
    mode: str = "埋Bug版" if bug_mode else "正常版"
    print(f"✅ mock 登录 API（{mode}）已启动: http://127.0.0.1:{port}/api/login")
    return server


def stop_mock() -> None:
    """关闭 mock 服务（幂等）。"""
    global _server
    if _server is not None:
        _server.shutdown()
        _server.server_close()
        _server = None
        print("✅ mock 登录 API 已关闭")


# ═══════════════════════════════════════════════════════
# 实验
# ═══════════════════════════════════════════════════════

def _fire(port: int, name: str, body: dict[str, str], expect_status: int) -> None:
    """打一枪并断言状态码（避免 verify 里重复代码）。"""
    import requests  # noqa: PLC0415

    resp = requests.post(f"http://127.0.0.1:{port}/api/login", json=body, timeout=5)
    ok: bool = resp.status_code == expect_status
    print(f"  {name}: status={resp.status_code} body={resp.json()}  → {'✅' if ok else '❌'}")
    assert ok, f"{name} 分支不符合预期（期望 {expect_status}）"


def verify_mock(port: int = 8766) -> None:
    """正常版 5 分支验证（起服务 → 打 5 枪 → 关服务，零外网）。"""
    print("=" * 60)
    print("实验：verify_mock —— 正常版 5 分支")
    server = start_mock(port)
    try:
        _fire(port, "正常登录", {"phone": VALID_PHONE, "password": VALID_PASSWORD}, 200)
        _fire(port, "空手机号", {"phone": "", "password": VALID_PASSWORD}, 400)
        _fire(port, "短密码", {"phone": VALID_PHONE, "password": "123"}, 400)
        _fire(port, "手机号格式错误", {"phone": "12345", "password": VALID_PASSWORD}, 400)
        _fire(port, "错误凭据", {"phone": VALID_PHONE, "password": "WrongPass1"}, 401)
        print("✅ 正常版 5 分支全部符合预期")
    finally:
        stop_mock()


def verify_bug_mock(port: int = 8766) -> None:
    """埋 Bug 版验证：前 4 分支不变，错误凭据 → 500。"""
    print("=" * 60)
    print("实验：verify_bug_mock —— 埋 Bug 版（错误凭据 → 500）")
    server = start_mock(port, bug_mode=True)
    try:
        _fire(port, "正常登录", {"phone": VALID_PHONE, "password": VALID_PASSWORD}, 200)
        _fire(port, "短密码", {"phone": VALID_PHONE, "password": "123"}, 400)
        _fire(port, "手机号格式错误", {"phone": "12345", "password": VALID_PASSWORD}, 400)
        _fire(port, "错误凭据(Bug)", {"phone": VALID_PHONE, "password": "WrongPass1"}, 500)
        print("✅ 埋 Bug 版验证通过：错误凭据 → 500，可作 FAIL 分支靶场")
    finally:
        stop_mock()


def main() -> None:
    verify_mock()
    verify_bug_mock()
    print("\n💡 要点回顾：")
    print("   闭包工厂 make_login_handler(bug_mode) = 一个文件两个靶场")
    print("   正常版 5 分支（含手机号格式校验）；埋 Bug 版错误凭据 → 500")
    print("   默认端口 8766，与 Day 27 的 8765 不冲突，可并行对照")


if __name__ == "__main__":
    main()
