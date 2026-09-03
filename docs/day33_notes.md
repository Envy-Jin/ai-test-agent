# Day 33 学习笔记：第 5 周第五天 —— 回归测试分析 + 测试报告生成

## 日期
2026-09-03

## 今日成果
- [ ] 变更解析：git diff → ChangeInfo（文件/增删行/hunk/符号），纯正则零 API
- [ ] 用例注册表：.json → CaseEntry（5 用例 / 7 node），确定性直读（分派第三次落地）
- [ ] 回归计划：模型读 diff 原文 → RegressionPlan 四档（must/should/skip/need_add），reason 必填
- [ ] 规则基线对照：模型 vs 模块关键词规则，分界线实证（exp5 输出贴这里）
- [ ] JUnit XML 解析：xml.etree → TestCaseOutcome[]（7 条/3 failed）
- [ ] 报告生成：执行摘要 + 详细结果 + 缺陷列表 + 结论（统计归代码、结论规则模板）
- [ ] 端到端闭环：变更前基线 100% vs 变更后 3 缺陷 → 两份报告对比

## 核心概念
### 1. 回归 = 变更驱动的用例选择（风险驱动，跳过也要写理由）
# 不是全量重跑：分析变更影响面 → 必回归/建议回归圈出来跑，无关用例明确跳过
# can_skip 的 reason 必填——跳过不是偷懒，是写明的风险决策，计划可审计
# 今天实证：模型圈中的 TC003（错误凭据）/TC005（越权）在"变更后"真的挂了

### 2. 分界第五次落地（今天最完整：每个环节标了归属）
# 变更解析 → 代码（diff 确定性格式）；影响判断 → 模型（删校验→越权风险）
# 执行收集 → 代码（pytest --junitxml）；统计 → 代码（可追溯每一条 testcase）
# 结论 → 规则模板兜底。口诀：数字不许模型编，语义不许代码猜

### 3. JUnit XML = 执行结果的 CI 通用交换格式（Day 30 文本解析的升级）
# pytest --junitxml 内置；testsuites/testsuite/testcase/failure 结构稳定
# xml.etree 标准库解析，root.iter('testcase') 不依赖根节点名（兼容版本差异）
# 同一解析器以后可读 Jenkins/GitLab 的 CI 产物

### 4. 模型 vs 规则基线（exp5 实测输出贴这里）
# 规则：扫 diff 行关键词 → 命中模块的 P0 全 must（保守、零成本、可解释）
# 模型：能指出"删内联校验→越权风险"因果，理由可读
# 结论：规则做兜底基线（永不漏模块），模型做精修与展示

### 5. 基线对照 = 回归证据链
# 变更前 100% vs 变更后 3 缺陷：没有基线的失败只是失败，有基线的失败是"回归证据"

## 联网确认（2026-09-02）
- pytest --junitxml 内置、输出结构 testsuites/testcase/failure；默认 xunit2
- pytest 9.1.1 的 --deselect / parametrize node id 兼容（沿用实测）

## Pyright 避坑总结（新增 6 条）
- 坑1 ET.find() → Element|None，判空收窄再取属性
- 坑2 dict.get(key) 不传默认值才返回 V|None；XML time 用 (x or 0.0) 兜底
- 坑3 结构化输出 raw: object → isinstance 收窄链（沿用 Day 29 坑1）
- 坑4 模板塞代码/JSON 用 str.replace，.format 会被 {} 炸
- 坑5 subprocess stdout bytes|None → or b"" 再 decode
- 坑6 Literal 判定用显式 ==，别依赖 in (tuple) 窄化

## 还存在的问题 / 待办
- 报告结论模型化：只喂 stats+defects 文本让模型写结论（不许数数）→ Day 34-35 增强
- need_add 的新用例应自动"回写注册表"→ 资产回写闭环（Day 34-35 两段式评审门结合）
- 函数级变更定位：行级 diff 看不到函数边界 → 真实工程用 git diff -U / AST / 增量覆盖率
- Day 20-21 线程锁 + 增量导入 / Day 31 批量串行 → Day 40 asyncio 统一解决

