"""
src/agent/logger_config.py —— 项目级日志配置

Day 12 新知识：Python logging 模块
统一日志格式、输出位置、级别控制
"""

import logging
import os


def setup_logger(
    name: str = "ai_test_agent",
    level: int = logging.DEBUG,
    log_file: str | None = None,
) -> logging.Logger:
    """
    创建并配置一个 logger

    Args:
        name: logger 名称（命名空间）
        level: 日志级别（DEBUG/INFO/WARNING/ERROR/CRITICAL）
        log_file: 日志文件路径（None 则只输出到终端）

    Returns:
        配置好的 Logger 对象

    Examples:
        >>> logger = setup_logger("ai_test_agent", level=logging.DEBUG)
        >>> logger.info("调用 Gemini API")
        >>> logger.warning("重试第 2 次")
        >>> logger.error("JSON 解析失败")
    """
    logger = logging.getLogger(name)

    # 防止重复添加 handler（模块被多次导入时）
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # 日志格式：时间 | 级别 | 模块 | 消息
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # 终端输出（StreamHandler）
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件输出（FileHandler）—— 可选
    if log_file:
        os.makedirs(os.path.dirname(log_file) if os.path.dirname(log_file) else ".", exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger

# 日志级别速查
"""
logging.DEBUG     → 详细调试信息（开发阶段用）
logging.INFO      → 一般运行信息（API 调用开始/结束）
logging.WARNING   → 警告（重试、降级、非致命错误）
logging.ERROR     → 错误（JSON 解析失败、Schema 不匹配）
logging.CRITICAL  → 严重错误（API Key 无效、系统级故障）
"""

# ============================================================
# 自检：日志级别演示
# ============================================================

def test_logger():
    """测试 logger 配置"""
    print("=" * 60)
    print("🧪 测试 Logger 配置")
    print("=" * 60)

    # 创建 logger（同时输出到终端和文件）
    logger = setup_logger(
        "ai_test_agent",
        level=logging.DEBUG,
        log_file="logs/day12_test.log",
    )

    logger.debug("这是 DEBUG 级别——详细的调试信息")
    logger.info("这是 INFO 级别——API 调用开始")
    logger.warning("这是 WARNING 级别——重试第 2 次")
    logger.error("这是 ERROR 级别——JSON 解析失败")
    logger.critical("这是 CRITICAL 级别——API Key 无效")

    print(f"\n✅ 日志文件已创建: logs/day12_test.log")
    print("   打开文件确认日志格式正确")

    # 演示：日志中的异常追踪
    print("\n--- 异常追踪演示 ---")
    try:
        json.loads("{invalid json}")
    except json.JSONDecodeError as e:
        logger.error(f"JSON 解析失败: {e}", exc_info=True)
        # exc_info=True 会自动附加完整的异常堆栈

    print("   exc_info=True 会记录完整的异常堆栈信息")
    print("   这是排查生产环境问题的关键信息")


if __name__ == "__main__":
    import json  # noqa: E402（测试用，放后面也行）
    test_logger()