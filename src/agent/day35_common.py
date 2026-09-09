"""Day 35 公共底座（day35_common.py）—— Day 36 重构后：物理并入 utils.py，本文件降级为薄包装。

背景：
  Day 35 抽取的公共工具（ROOT/read_text/write_text/schema_doc_path/output_dir）已按 Day 36
  计划并入 src/agent/utils.py。本文件只做 re-export，让仍写
  `from day35_common import ROOT, output_dir` 的历史脚本（day35_scenario / day35_review_gate）
  零改动继续工作 —— 重构期间「旧 import 不炸」= 随时可回归。
  原 exp1_equivalence（等价性回归实验）使命已于 Day 35 完成，随重构退役；
  回归义务转交 utils 函数冒烟 + day36 系列 import 冒烟。
"""
from __future__ import annotations

from utils import ROOT, output_dir, read_text, schema_doc_path, write_text

__all__ = ["ROOT", "read_text", "write_text", "schema_doc_path", "write_text"]
