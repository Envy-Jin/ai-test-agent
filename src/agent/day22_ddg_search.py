"""
Day 22 练习 2：DuckDuckGo 搜索工具 —— ddgs 包的 @tool 封装

替代学习计划中已失效的 DuckDuckGoSearchRun（langchain_community + 旧包冻结）。
两个实战要点：
  1. 代理必配：国内直连 DuckDuckGo 不通 → DDGS(proxy="http://127.0.0.1:7890")
  2. 限流容错：RatelimitException（HTTP 202 软限流）→ 转成友好文本返回，
     不让异常炸掉 Agent 循环

⚠️ Pyright 注意事项：
  - DDGS(proxy=...) 是 Pydantic/动态类，Pyright 看不到具名参数时走默认 env
    无碍；proxy 参数是官方文档签名，直接传即可
  - ddgs.text() 返回 list[dict[str, str]]（联网确认），标注后正常遍历
  - 工具函数统一返回 str（给 LLM 看的都是文本），类型最稳

用法：
  python day22_ddg_search.py           # 跑实验 1/2（真实联网，需代理开着）
"""

import sys
from typing import Optional

# Windows 下控制台/重定向输出统一 UTF-8，防止 emoji/中文打印报 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]

from dotenv import load_dotenv

load_dotenv()

from ddgs import DDGS
from langchain_core.tools import tool

# # FlClash 混合代理端口（与项目其他脚本的 GEMINI 代理约定一致）
# PROXY: str = "http://127.0.0.1:7890"

@tool
def duckduckgo_search(query: str, max_results: int = 5) -> str:
    """联网搜索最新信息。当问题涉及训练数据之后的知识（新版本发布、最新新闻、
    近期数据）或需要事实核实时使用。query 是搜索关键词（中英文均可），
    max_results 是返回结果条数（默认 5）。返回搜索结果的标题和摘要文本。"""
    try:
        # with DDGS(proxy=PROXY) as ddgs: #使用代理的写法
        with DDGS() as ddgs: #不使用代理的写法
            results: list[dict[str, str]] = ddgs.text(query, max_results=max_results)
    except Exception as exc:  # RatelimitException / 超时 / 代理断开等
        return f"搜索失败（{type(exc).__name__}），请稍后重试或换个关键词"

    if not results:
        return "搜索完成但没有找到相关结果，建议换个关键词"

    # 瘦身：只保留 标题 + 摘要（截断），省 token
    lines: list[str] = []
    for r in results:
        title: str = str(r.get("title", "")).strip()
        if not title:                      # 过滤广告/追踪条目（title 为空/纯空白）
            continue                       # 编号用 len(lines)+1 → 跳过广告后 [1][2][3] 依然连续
        body: str = str(r.get("body", "")).strip()[:150]
        lines.append(f"[{len(lines) + 1}] {title}\n    {body}")

    if not lines:                          # 过滤后为空 → 触发真正兜底
        return "搜索完成但没有找到相关结果，建议换个关键词"

    return "\n".join(lines)

# ═══════════════════════════════════════════════════════
# 实验 1：单独测试搜索工具（真实联网）
# ═══════════════════════════════════════════════════════

def exp1_search_directly() -> None:
    """实验 1：直接调用搜索工具，验证代理/限流/结果格式"""
    print("=" * 60)
    print("实验 1：DuckDuckGo 搜索工具直连测试")
    print("=" * 60)

    print("🔍 搜索: pytest 9 new features\n")
    output: object = duckduckgo_search.invoke(
        {"query": "pytest 9 new features", "max_results": 3}
    )
    result_text: str = output if isinstance(output, str) else str(output)
    print(result_text)

    print("\n💡 如果输出『搜索失败』：先检查 FlClash 是否开着（7890 端口）")


# ═══════════════════════════════════════════════════════
# 实验 2：容错验证 —— 关键词无结果时的行为
# ═══════════════════════════════════════════════════════

def exp2_no_result_fallback() -> None:
    """实验 2：无结果关键词 → 返回友好文本而不是空串/异常"""
    print("\n" + "=" * 60)
    print("实验 2：无结果兜底")
    print("=" * 60)

    output: object = duckduckgo_search.invoke(
        {"query": "ucnvqaujklfsdhfbvbgadf", "max_results": 3}
    )
    result_text: str = output if isinstance(output, str) else str(output)
    print(f"输出: {result_text[:100]}")
    assert len(result_text) > 0, "工具必须返回非空文本（Agent 循环依赖 Observation）"
    print("✅ 无论成功/失败/无结果，工具都返回非空 str —— 这就是给 Agent 的 Observation")


# ═══════════════════════════════════════════════════════
# main：按需注释掉不想跑的实验
# ═══════════════════════════════════════════════════════
if __name__ == "__main__":
    # exp1_search_directly()
    exp2_no_result_fallback()

    print("\n✅ 搜索工具就绪！")
    print("   duckduckgo_search = DuckDuckGoSearchRun 的现代替代（ddgs + @tool）")
    print("   下一步：把它交给 Agent（练习 3）")
