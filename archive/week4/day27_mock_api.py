"""
Day 27 练习 2：本地 mock 登录 API —— 让 run_api_test 有真实的接口可打

接口：POST http://127.0.0.1:{port}/api/login
入参：JSON body {"phone": "...", "password": "..."}
三分支（故意设计成可测的分支逻辑）：
  - phone/password 任一为空       → 400  {"code": 40001, "message": "手机号和密码不能为空"}
  - password 长度 < 8             → 400  {"code": 40002, "message": "密码长度不能少于8位"}
  - phone=13800138000 & password=Test123456 → 200 {"code": 0, "message": "登录成功", "data": {"token": "demo-token-123"}}
  - 其他                          → 401  {"code": 40101, "message": "手机号或密码错误"}
其他路径 → 404

用法：
  python -c "from day27_mock_api import start_mock_server, stop_mock_server, verify_mock; verify_mock()"   # 起服务→打3枪→关服务（零外网）
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

# ═══════════════════════════════════════════════════════
# HTTP handler：处理 POST /api/login（三分支）
# ═══════════════════════════════════════════════════════

class MockLoginHandler(BaseHTTPRequestHandler):
    """mock 登录接口 handler（do_POST 覆盖父类方法，无需返回注解）。"""

    def do_POST(self) -> None:
        payload: dict[str, object] = self._read_json()
        if self.path != "/api/login":
            self._send_json(404, {"code": 40400, "message": f"未知接口 {self.path}"})
            return
        # ⚠️ 收窄不能跨两次 .get()：先取临时变量（object）再 isinstance 收窄（口诀 2 变体）
        phone_raw: object = payload.get("phone", "")
        password_raw: object = payload.get("password", "")
        phone: str = phone_raw if isinstance(phone_raw, str) else ""
        password: str = password_raw if isinstance(password_raw, str) else ""
        if not phone or not password:
            self._send_json(400, {"code": 40001, "message": "手机号和密码不能为空"})
        elif len(password) < 8:
            self._send_json(400, {"code": 40002, "message": "密码长度不能少于8位"})
        elif phone == "13800138000" and password == "Test123456":
            self._send_json(200, {"code": 0, "message": "登录成功", "data": {"token": "demo-token-123"}})
        else:
            self._send_json(401, {"code": 40101, "message": "手机号或密码错误"})

    def _read_json(self) -> dict[str, object]:
        """读取请求体并解析 JSON（Content-Length 是 str|None → 兜底 or "0"）。"""
        length_raw: str | None = self.headers.get("Content-Length")
        length: int = int(length_raw or "0")
        raw: bytes = self.rfile.read(length)
        try:
            data: object = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return {}
        return data if isinstance(data, dict) else {}

    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        """写 JSON 响应（显式 Content-Length + utf-8）。"""
        body: bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        """静音默认日志（避免测试刷屏）。"""
        return


# ═══════════════════════════════════════════════════════
# 服务启停（全局 server 变量 + 后台线程）
# ═══════════════════════════════════════════════════════

_server: HTTPServer | None = None


def start_mock_server(port: int = 8765) -> HTTPServer:
    """启动 mock 登录接口（后台线程），返回 server 实例。

    ⚠️ stop_mock_server() 必须从【外部线程】调用（不能放进 handler 里）——
    shutdown() 会等待 serve_forever 退出，在 handler 内调用会死锁。
    """
    global _server
    if _server is not None:
        return _server
    try:
        server: HTTPServer = HTTPServer(("127.0.0.1", port), MockLoginHandler)
    except OSError as exc:
        raise RuntimeError(f"端口 {port} 被占用，换一个端口重试（start_mock_server(port=...)）") from exc
    thread: threading.Thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _server = server
    print(f"✅ mock 登录 API 已启动: http://127.0.0.1:{port}/api/login")
    return server


def stop_mock_server() -> None:
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

def verify_mock() -> None:
    """手工验证 mock API 三分支（requests 直连，不经过 Agent）。"""
    print("=" * 60)
    print("实验：verify_mock —— 起服务 → 打 3 枪 → 关服务（零外网）")
    import requests  # noqa: PLC0415

    server = start_mock_server(8765)
    base: str = "http://127.0.0.1:8765/api/login"
    try:
        cases: list[tuple[str, dict[str, str], int]] = [
            ("正常登录", {"phone": "13800138000", "password": "Test123456"}, 200),
            ("短密码", {"phone": "13800138000", "password": "123"}, 400),
            ("错误凭据", {"phone": "13800138000", "password": "WrongPass1"}, 401),
        ]
        for name, body, expect_status in cases:
            resp = requests.post(base, json=body, timeout=5)
            ok: bool = resp.status_code == expect_status
            print(f"  {name}: status={resp.status_code} body={resp.json()}  → {'✅' if ok else '❌'}")
            assert ok, f"{name} 分支不符合预期（期望 {expect_status}）"
        print("✅ 三分支全部符合预期，mock API 可作 run_api_test 的靶场")
    finally:
        stop_mock_server()


def main() -> None:
    verify_mock()
    print("\n💡 要点回顾：")
    print("   http.server 起本地接口 = 零依赖的真实 HTTP 靶场")
    print("   三分支故意可测：正常 200 / 短密码 400 / 错误凭据 401")
    print("   shutdown() 必须外部线程调用（handler 内调用会死锁）")


if __name__ == "__main__":
    main()
