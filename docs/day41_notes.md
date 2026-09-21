# Day 41 学习笔记：项目收尾（一）· 端到端 + 修复 + 调优

## 1. 今天改了什么
| 文件 | 改动 | 为什么 |
|------|------|--------|
| day35_scenario.py | 命名空间 / kind 派生 / 契约校验 / 注册表 | 让"第二个场景"在路径层面就和第一个不打架 |
| day34_flow_map.py | StageSpec +mock_port / mock_scenario | 靶场进契约 |
| day30_mock_api.py | make_handler(bug_mode, scenario) | 靶场按场景分派 |
| day32_run_pipeline.py | exp6_pipeline 参数化 | 去掉写死的 users/orders |
| day34_orchestrator.py | 端口/靶场/路径从 spec 读 + 报告标题 | 声明与执行同源 |
| day40_llm_cache.py | 白名单 + closing | 接线才暴露的两处真缺陷 |
| cli.py | 注册表 / 契约 / --no-cache / 落盘 | 入口层跟上 |
| 资产 4 份 + test_day41_e2e.py(26) | register 端到端 + 钉住 | 收尾 |

## 2. 三类"静默接缝"与它们的契约
（写清"静默覆盖 / 静默错配 / 静默绕过"各自长什么样，以及今天用什么函数断言）

## 3. 今天最有价值的一条：硬编码的"对"是运气
（举 register 报告标题写着 login 的例子；解释为什么单测抓不到）

## 4. 两处"接线才暴露"的缺陷
- chat 载荷白名单：父类放行 ≠ 子类放行（id 精确匹配）
- `with sqlite3.connect()` 是事务不是关闭 → 句柄泄漏 → 清理静默失败

## 5. 偶发失败的处理纪律
（"单文件必过、全量偶发" → 定位到端口共享 + Windows SO_REUSEADDR；
  修法是隔离不是重试；连跑两轮是最低成本反证）

## 6. 兼容层与收口条件
（LEGACY_FLAT_SCENARIO=login 是有意保留；收口条件：第二场景稳定后统一迁命名空间）

## 7. 遗留待办
- 执行层第 6 态 skipped_missing_input（必须与 P0 系列同批）
- 第二批分层迁移（src/tools、src/rag、src/config.py）
- day35_pyright_pitfalls.py 归档