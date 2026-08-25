"""
Day 27 避坑实战：http.server + 端到端场景的 Pyright / 运行时陷阱

坑 1：http.server handler——do_POST 覆盖父类方法；Content-Length 是 str|None 要兜底
坑 2：json.loads 返回 object → isinstance(dict) 收窄再 .get
坑 3：全局 server 变量必须显式标注 HTTPServer | None + global 声明
坑 4：端口占用 OSError → 捕获并转成带提示的 RuntimeError
坑 5：复用口诀——build 函数返回注解别写 object（25）、structured_response 收窄（14）
坑 6：shutdown() 必须从外部线程调用（handler 内调用会死锁）

用法：python day27_pyright_pitfalls.py（纯本地逻辑，无 API）
"""
import json
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]


# ── 坑 1 + 坑 2：handler 内 JSON 解析 ────────────────────

class DemoHandler(BaseHTTPRequestHandler):
    """演示 handler：读 body、解析 JSON、按收窄后的字段回复。"""

    def do_POST(self) -> None:
        data: dict[str, object] = self._read_json()
        # 坑 2：.get() 返回 object → 先取临时变量再 isinstance 收窄成 str 才能 len()
        name_raw: object = data.get("name", "")
        name: str = name_raw if isinstance(name_raw, str) else ""
        # 坑 1：headers.get 返回 str|None → or "0" 兜底再 int()
        length_raw: str | None = self.headers.get("Content-Length")
        _length: int = int(length_raw or "0")
        self._send(200, {"echo": name, "length": _length})

    def _read_json(self) -> dict[str, object]:
        raw: bytes = self.rfile.read(int(self.headers.get("Content-Length") or "0"))
        try:
            parsed: object = json.loads(raw or b"{}")
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _send(self, status: int, payload: dict[str, object]) -> None:
        body: bytes = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


# ── 坑 3 + 坑 4：全局 server + 端口占用 ──────────────────

_demo_server: HTTPServer | None = None  # 坑 3：显式标注可空类型


def start_demo() -> HTTPServer:
    """启动演示服务（坑 4：端口占用 OSError → 转 RuntimeError 带提示）。"""
    global _demo_server  # 坑 3：函数内修改全局必须 global 声明
    if _demo_server is not None:
        return _demo_server
    try:
        server: HTTPServer = HTTPServer(("127.0.0.1", 8765), DemoHandler)
    except OSError as exc:
        raise RuntimeError(f"端口 8765 被占用: {exc}") from exc
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _demo_server = server
    return server


def stop_demo() -> None:
    """坑 6：shutdown() 只能在 handler 线程之外调用（此处是主线程，安全）。"""
    global _demo_server
    if _demo_server is not None:
        _demo_server.shutdown()
        _demo_server.server_close()
        _demo_server = None


# ── 坑 5：构建函数返回注解（口诀 25 复用） ────────────────

def demo_build_return_annotation() -> None:
    """坑 5：包装 create_agent 的构建函数【不要】写 -> object。"""
    # ❌ def build_agent() -> object: return create_agent(...)
    #    → 调用方 agent.invoke(...) 报 "Attribute 'invoke' is unknown"
    # ✅ 留空注解让 pyright 推断 CompiledStateGraph；或用真实类型注解
    def build_agent():
        from langchain.agents import create_agent  # noqa: PLC0415
        from langchain_core.language_models.fake_chat_models import FakeChatModel  # noqa: PLC0415

        return create_agent(model=FakeChatModel())

    agent = build_agent()
    # pyright 能推断出 .invoke 存在 → 下面这行不报错（运行时 FakeChatModel 也能 invoke）
    print(f"✅ 构建函数返回类型推断成功: {type(agent).__name__}，.invoke 可访问")


# ── 坑 5b：structured_response 收窄（口诀 14 复用） ───────

def demo_extract_report(result: dict[str, object]) -> str | None:
    """坑 5b：result 容器取值 → isinstance 收窄到具体类型再访问属性。"""
    sr: object = result.get("structured_response")
    if isinstance(sr, str):  # 这里用 str 演示（真实场景换成 TestReport）
        return sr
    return None


def main() -> None:
    demo_build_return_annotation()
    out: str | None = demo_extract_report({"structured_response": "ok"})
    print(f"✅ 收窄演示: {out}")
    server = start_demo()
    print(f"✅ 全局 server 类型标注 + 端口处理 ok（{server.server_address}）")
    stop_demo()
    print("\n💡 坑位回顾：")
    print("   1. Content-Length 是 str|None → or '0' 兜底；do_POST 覆盖父类无注解方法")
    print("   2. json.loads → object → isinstance(dict) 收窄再 .get")
    print("   3. 全局 server 标注 HTTPServer | None + global 声明")
    print("   4. 端口占用 OSError → 转 RuntimeError 带换端口提示")
    print("   5. 构建函数返回注解别写 object；structured_response 必须收窄")
    print("   6. shutdown() 外部线程调用（handler 内调用死锁）")


if __name__ == "__main__":
    main()
