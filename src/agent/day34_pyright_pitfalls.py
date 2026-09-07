"""Day 34 练习 4：Pyright 避坑演示 + 今日模块零 API 自检。

坑清单（详情与正确写法在本文件各函数注释里）：
  坑 1  subprocess.run 不传 text=True → stdout 是 bytes|None，直接当 str 用会报错
        （print 出 b'...'、str.join/切片全是类型错）→ text=True+encoding+errors
  坑 2  CompletedProcess 泛型：pyright 不会因为 text=True 推断出 str 变体
        → 显式注解 proc: subprocess.CompletedProcess[str]
  坑 3  hashlib.update 只收 bytes：文本模式 open().read() 返回 str 会报类型错
        → 用 rb 二进制读 + 分块循环（见 day34_orchestrator._sha12）
  坑 4  argparse.Namespace 属性是 Any/未知 → 拼错 flag 名 pyright 不报错、
        运行时才炸 → 教学脚本手写 _parse_flags 返回显式 bool 三元组
  坑 5  Literal 状态判定用显式 == 展开（沿用 Day 33 坑 6）
  坑 6  "产物存在" ≠ "产物有效"：空文件=失败产物；exists 判断与 open 之间有
        时序窗口（文件可能消失）→ getsize>0 双检 + 读取用 try/except OSError

实验（cd src/agent）：
  python -c "from day34_pyright_pitfalls import exp4_self_check_zero_api; exp4_self_check_zero_api()"
  python day34_pyright_pitfalls.py
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

# 假 key：编排器模块级会构建 day33 回归链，构造期只校验 key、零 API（冒烟规范）
os.environ.setdefault("GEMINI_API_KEY", "smoke-fake-key")

import day34_flow_map as fm  # noqa: E402
import day34_orchestrator as oc  # noqa: E402


# ── 坑 1/2 现场（正确写法，pyright 0 errors）──
#   proc = subprocess.run(argv, capture_output=True)          # ❌ stdout: bytes|None
#   text = proc.stdout.splitlines()[-1]                        # ❌ None 可能 + bytes 元素
#   proc: subprocess.CompletedProcess[str] = subprocess.run(   # ✅ 显式泛型
#       argv, capture_output=True, text=True,
#       encoding="utf-8", errors="replace",
#   )
#   tail = (proc.stdout or "").strip().splitlines()[-1]        # ✅ str | None → or "" 收窄
#   见 oc._run_cmd / oc._run_mock_pytest

# ── 坑 3 现场 ──
#   with open(path, "r", encoding="utf-8") as f:               # ❌ read() 返回 str
#       digest.update(f.read())                                # ❌ update 只收 bytes
#   digest = hashlib.sha256()                                  # ✅ rb + 分块
#   with open(path, "rb") as f:
#       while chunk := f.read(8192): digest.update(chunk)      # ✅ chunk: bytes
#   见 oc._sha12

# ── 坑 4 现场 ──
#   args = parser.parse_args()          # Namespace 属性对 pyright 是未知/Any
#   if args.with_llm:                   # 拼成 args.wth_llm 也不报错，运行时才炸
#   with_llm, force, fail_fast = oc._parse_flags(sys.argv[1:])  # ✅ 显式 bool
#   见 oc._parse_flags

# ── 坑 5/6 现场 ──
#   if r.status in ("run_failed",):      # ❌ in(tuple) 对 Literal 窄化不可靠
#   if r.status == "run_failed":         # ✅ 显式展开
#   os.path.isfile(p)                    # ❌ 空文件也 isfile → 误判"产物在"
#   os.path.isfile(p) and os.path.getsize(p) > 0   # ✅ 双检（见 fm._exists_nonempty）


def exp4_self_check_zero_api() -> None:
    """零 API 自检：今日模块 import + 六坑的正确姿势逐个跑（不依赖项目产物）。"""
    # 坑 1/2：text=True 子进程，stdout 是纯 str
    proc: subprocess.CompletedProcess[str] = subprocess.run(
        [sys.executable, "-c", "print('hi')"],
        capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    out: str = (proc.stdout or "").strip()
    assert out == "hi", "text=True 模式 stdout 应是纯 str"
    print(f"✅ 坑1/2: text=True → stdout 纯 str（{out!r}），显式 CompletedProcess[str]")

    # 坑 3：hashlib 收 bytes（不碰文件系统：直接对字节演示前缀）
    digest: str = hashlib.sha256(b"abc").hexdigest()[:12]
    assert digest == "ba7816bf8f01", "sha256(b'abc') 前 12 位应是 ba7816bf8f01"
    print(f"✅ 坑3: sha256(b'abc')[:12] = {digest}（update 只收 bytes，文件读用 rb）")

    # 坑 4：手写 flag 解析（编排器 main 用的就是它）
    with_llm, force, fail_fast = oc._parse_flags(["--with-llm", "--force"])
    assert (with_llm, force, fail_fast) == (True, True, False)
    print(f"✅ 坑4: _parse_flags → with_llm={with_llm} force={force} fail_fast={fail_fast}（显式 bool）")

    # 坑 5：Literal 显式 == 判定
    status: fm.ScanStatus = "reused"
    is_reused: bool = status == "reused"
    is_failed: bool = status == "run_failed"
    assert is_reused and not is_failed
    print(f"✅ 坑5: Literal 判定显式展开：status=={status!r} → reused={is_reused}")

    # 坑 6：存在 ≠ 非空 双检（对蓝图自身输出契约抽查，缺文件也不崩）
    probe_rel: str = "outputs/flow/flow_map.md"
    probe_abs: str = fm._abs(probe_rel)
    valid: bool = os.path.isfile(probe_abs) and os.path.getsize(probe_abs) > 0
    print(f"✅ 坑6: 双检（exists & size>0）：{probe_rel} 有效={valid}（空文件=失败产物不算数）")
    try:
        with open(probe_abs, "r", encoding="utf-8") as f:
            head: str = f.read(60)
        print(f"    flow_map.md 头 60 字符: {head.splitlines()[0] if head else '(空)'}")
    except OSError:
        print("    flow_map.md 暂不存在（先跑练习 1），跳过内容读取——双检逻辑已演示")

    # 蓝图/执行器 import 链 + 纯函数探针
    assert len(fm.BLUEPRINT) == 9, "蓝图应是 9 段"
    print(f"✅ 蓝图 {len(fm.BLUEPRINT)} 段 import 就绪（S1→S9），编排器模块零 API 可加载")
    print("=" * 56)
    print("零 API 自检全绿：day34_flow_map + day34_orchestrator import + 六坑正确姿势可用")


def main() -> None:
    exp4_self_check_zero_api()


if __name__ == "__main__":
    main()
