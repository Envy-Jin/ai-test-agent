"""
Day 21 练习 5：Pyright 避坑实战 —— CLI / 对话 / 持久化场景

Day 21 引入的新类型陷阱。本练习不调用 API，纯演示
「❌ 错误写法 vs ✅ 正确写法」。

⚠️ 所有标注 ❌ 的代码都在注释里说明原因，✅ 的可以放心照抄。

用法：直接运行，全部是演示性质，不含 API 调用。
"""

import argparse
import json
import os
import sys

# Windows 下控制台/重定向输出统一 UTF-8，防止 emoji/中文打印报 UnicodeEncodeError
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
from typing import Optional


# ═══════════════════════════════════════════════════════
# 坑 1：argparse Namespace 属性是 Any
# ═══════════════════════════════════════════════════════

def pitfall1_argparse_namespace() -> None:
    """坑 1：args.xxx 是 Any，直接传业务函数会丢失类型检查"""

    parser = argparse.ArgumentParser()
    parser.add_argument("--k", type=int, default=3)

    # ❌ 错误：args.k 是 Any，传给 def f(k: int) 不报错但也没检查
    #    运行时可能是 None（未提供且无默认）→ 下游 int() 报错
    # def f(k: int) -> None: ...
    # f(args.k)

    # ✅ 正确：str()/int() 显式转换后再传
    k: int = int(parser.parse_args(["--k", "5"]).k)
    assert k == 5
    print(f"✅ argparse 值显式转换: k={k}")
    print("  记忆口诀：Namespace 属性是 Any → str()/int() 显式转换再进业务函数")


# ═══════════════════════════════════════════════════════
# 坑 2：Optional[str] 判空收窄（truthiness）
# ═══════════════════════════════════════════════════════

def pitfall2_optional_str() -> None:
    """坑 2：persist_directory: Optional[str] 使用前必须判空"""

    def load(persist_directory: Optional[str]) -> str:
        # ✅ 正确：truthiness 同时排除 None 和 ""（Pyright 对 str 的 truthiness 收窄有效）
        if not persist_directory:
            return "内存模式"
        # 此处 persist_directory 已被收窄为 str，可以安全拼接
        return f"磁盘模式: {persist_directory}"

    print(f"✅ {load(None)} / {load('chroma_db')}")
    print("  记忆口诀：Optional[str] → if not x: 分支处理，else 分支已收窄")


# ═══════════════════════════════════════════════════════
# 坑 3：Chroma 构造参数名 —— embedding_function vs embedding
# ═══════════════════════════════════════════════════════

def pitfall3_chroma_param_name() -> None:
    """坑 3：from_documents 用 embedding=，直接构造加载用 embedding_function=（参数名不同！）"""

    # ❌ 错误：加载已有索引时照抄 from_documents 的参数名 → Pyright 报错
    #     "No parameter named 'embedding'"
    # vs = Chroma(persist_directory="chroma_db", embedding=embeddings)

    # ✅ 正确：langchain-chroma __init__ 的参数名是 embedding_function
    # vs = Chroma(
    #     persist_directory="chroma_db",
    #     embedding_function=embeddings,
    #     collection_name="knowledge_base",
    # )
    print("✅ 参数名对照：from_documents(embedding=...) vs Chroma(embedding_function=...)")
    print("  记忆口诀：同一个向量库，两种入口参数名不同 —— 先查签名再写")


# ═══════════════════════════════════════════════════════
# 坑 4：json.load 返回 Any —— isinstance 校验
# ═══════════════════════════════════════════════════════

def pitfall4_json_any() -> None:
    """坑 4：json.load 返回 Any，直接当 dict 用有运行时风险"""

    # ❌ 错误：文件内容可能不是 dict（如 "[1,2]" 或 "null"）
    # with open("sessions.json", encoding="utf-8") as f:
    #     sessions = json.load(f)   # Any
    # print(sessions["s01"])        # ❌ 运行时可能 TypeError / KeyError

    # ✅ 正确：isinstance 校验后逐层转换
    def parse(raw: object) -> dict[str, list[dict[str, str]]]:
        if not isinstance(raw, dict):
            return {}
        result: dict[str, list[dict[str, str]]] = {}
        for sid, records in raw.items():
            if isinstance(records, list):
                cleaned: list[dict[str, str]] = [
                    {"role": str(r.get("role", "user")), "content": str(r.get("content", ""))}
                    for r in records
                    if isinstance(r, dict)
                ]
                result[str(sid)] = cleaned
        return result

    assert parse({"s01": [{"role": "user", "content": "hi"}]})["s01"][0]["role"] == "user"
    assert parse("[1,2]") == {}
    print("✅ json 反序列化：isinstance 逐层校验 + str() 转换")
    print("  记忆口诀：json.load 是 Any → 校验类型再解包，值用 str()/int() 转换")


# ═══════════════════════════════════════════════════════
# 坑 5：要么 raise 要么 return None（二选一，不混用）
# ═══════════════════════════════════════════════════════

def pitfall5_raise_or_none() -> None:
    """坑 5：探测类函数只 return None/空值，不混用 raise（避免 T | None 双通道污染）"""

    # ❌ 错误：同一函数既 raise 又 return None → 调用方要同时处理异常和 None
    # def load(path: str) -> int:
    #     if not os.path.isdir(path):
    #         raise FileNotFoundError(path)
    #     count = ...
    #     if count == 0:
    #         return None      # ❌ 类型污染：int | None + raise 双通道

    
