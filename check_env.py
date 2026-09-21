"""环境检查脚本：验证 Python 运行环境与项目依赖是否就绪。"""

import io
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def _configure_stdout() -> None:
    # sys.stdout 静态类型是 TextIO，reconfigure 只在 TextIOWrapper 上；
    # hasattr 不能用于类型收窄 → 必须 isinstance
    if isinstance(sys.stdout, io.TextIOWrapper):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass


def _get_venv_path() -> str | None:
    venv_path = os.environ.get("VIRTUAL_ENV")
    if venv_path:
        return venv_path
    if hasattr(sys, "base_prefix") and sys.prefix != sys.base_prefix:
        return sys.prefix
    return None


def main() -> None:
    _configure_stdout()
    checks_passed = True

    print(f"Python 版本: {sys.version}")

    venv_path = _get_venv_path()
    if venv_path:
        print(f"虚拟环境路径: {venv_path}")
    else:
        print("虚拟环境路径: 未检测到（当前可能未激活虚拟环境）")
        checks_passed = False

    env_file = PROJECT_ROOT / ".env"
    if env_file.exists():
        print(".env 文件: 存在")
    else:
        print(".env 文件: 不存在")
        checks_passed = False

    requirements_file = PROJECT_ROOT / "requirements.txt"
    if requirements_file.exists():
        print("requirements.txt: 存在")
    else:
        print("requirements.txt: 不存在")
        checks_passed = False

    try:
        import requests  # noqa: F401

        print("import requests: 成功")
    except ImportError as exc:
        print(f"import requests: 失败 ({exc})")
        checks_passed = False

    try:
        import dotenv  # noqa: F401

        print("import dotenv: 成功")
    except ImportError as exc:
        print(f"import dotenv: 失败 ({exc})")
        checks_passed = False

    if checks_passed:
        print("✅ 环境检查通过！")
    else:
        print("环境检查未通过，请根据上述提示修复后重试。")
        sys.exit(1)


if __name__ == "__main__":
    main()
