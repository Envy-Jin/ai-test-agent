# Day 42 学习笔记：项目复盘 · 完整验收 + 第三场景演示

## 1. 今天改了什么
| 文件 | 改动 | 为什么 |
|------|------|--------|
| day42_review_probe.py（新） | 复盘清单 → 可断言（A/B/C 三块） | 清单不能断言的部分 = 没检查 |
| refund 资产 5 份（新） | 需求/接口/数据模型/Bug/注册表 | 第三个场景，全新技术域 |
| day35_scenario.py | REFUND_SCENARIO + 注册表 1 行 | 加场景的资产层代价 |
| day30_mock_api.py | make_handler 分派 + 4 分支 + 埋 Bug | 新接口域的唯一真卡点 |
| day41_seam_probe.py | SCENARIOS 改为注册表派生 + 文案扫全 | 照妖镜 1/3：假绿 |
| ui/app.py | _SCENARIOS 改为注册表派生；产物浏览读侧改按场景派生（5.2a） | 照妖镜 2/3：UI 少一项；5.2 验收发现"选 register 却列 login 的报告" |
| tests/test_day37_app.py | 断言改为注册表派生 | 照妖镜 3/3：唯一会喊的那个 |
| tests/test_day42_third_scenario.py（新，20 条） | 第三场景契约 + 同源；5.2a 追加 2 条断言（不新开用例，保计数） | 把上面全钉住 |

## 2. 加一个新模块到底要动什么（今天量出来了）
- 资产 5 份（缺一份 → 对应段 missing_input）
- 代码点 3 个：场景配置 + 注册表 1 行 + 靶场分派 1 行（**新接口域必需**）
- **同源收口 3 处**（今天才知道）：探测覆盖清单 / UI 场景清单 / UI 测试断言
- 不动：build_blueprint / run_flow / cli.py / 生成器 —— 「框架无白名单」得到实证

## 3. 今天最贵的一条：清单不完整比 bug 更难发现
三处"第二份场景清单"里，**只有测试会喊**。只改会喊的那个，就形成"每次加场景手改测试"
的惯例，而两个不喊的会一直漏下去：
- 探测少看一个 → **假绿**（实测：端口改错它仍报 0）
- UI 少一项 → 没人报错
- **读侧没跟场景** → **看错场景**（5.2a 实测：侧边栏选 register，产物浏览列的是 login 的报告；
  页面全绿、产物文件也真在 —— 而且**光看文件名分不出来**，得点开看正文首行才认得出）

## 4. 假绿与假红
- 假绿：探测"少看一个场景"却报"全部归零"（要**负向 sanity** 才照得出来）
- 假红：文本级写法检查被**自己的注释**命中（今天真踩；标记要取足上下文 + 丢注释行）
- 结论：**检查的对象要写死，检查的范围要从注册表派生** —— 恰好是反的才安全

## 5. "练过" ≠ "能处理"
第 5 类能力（对话问答/RAG）缺的是**入口**：检索实现已在 src/agent/day24_case_agent.py
（kb_search），多轮会话层在 archive/week3/，但生产链里没有调用入口。写成"待接线"最准。
复盘清单问的是"这个项目能处理什么"，判据只能是"生产链里有没有入口"。

## 6. 遗留待办
- 执行层第 6 态 skipped_missing_input（要连 ExecStatus Literal + 渲染 + 断言一起改）
- **`cli.py` 的 `--scenario` 帮助文案**（第 4 处清单）：抽静态常量 + 让 `check_single_source`
  **反向校验**（**派生不了** —— 它会破坏 Day 38 的 `--help` 零副作用，详见 4.2）
- login 兼容层收口条件：**现在有三个场景了**，收口收益已经大于改动面 ⇒ 可以排期了
- outputs/ 曾被跟踪（若有）→ 是否清理，另作决定
- 第 5 类能力迁移前置条件（**加一个入口** + 承认它必须真出网，故进不了零 API 验收）；
  **不是**"引 chroma 依赖"（仍在 requirements.txt 且已装），向量库「写」侧早已在 S9 链路上
- 第二批分层迁移（src/tools、src/rag）；day35_pyright_pitfalls.py 归档
- 是否固化关掉 Streamlit 的 watcher（见第 7 条）：属**运行配置**，不算代码债
- **UI 的「执行」按钮不落 `flow_report`**（5.2a 顺带发现）：`cli.py run` 会落
  （`persist_flow_report(report, output_namespace(sc))`），UI 只调了 `run_flow` ⇒
  从 UI 跑完，产物浏览里看不到新的 `flow_report.md`。收口 = 在 `ui/app.py` 的执行分支补一行，
  但它属"UI 与 CLI 行为对齐"的另一件事，**今天不改**
- 把 5.2a 那条**读侧派生**固化成探针断言：`_SINGLE_SOURCE_MARKERS` 加第 4 条
  （`("ui/app.py", "output_namespace(sc)", "_load_report_markdowns()")`）。**等下次重跑全套时一起做** ——
  它会让 §2.3 的「阻塞项 5 → 2 → 0」在 5.2a 之前多红 2 条，得连带重测探针输出

## 7. 环境噪音 ≠ 真缺陷：Streamlit 页面上那一片 torchvision 报错
**现象**：在 Streamlit 页面跑 llm 段（如 refund S1），日志刷一片
`ModuleNotFoundError: No module named 'torchvision'`（前缀是 `Examining the path of … raised:`），
但**产物正常落地、退出码 0**；同一条命令走 CLI 却复现不了。
**判读顺序**：先看产物 → 再看退出码 → 最后才看日志。三者不一致时，**日志说了不算**：
这条错误发生在 watcher 的后台线程，且被 Streamlit 自己 `except` 吞掉，到不了脚本线程，
所以它和"跑没跑成"没有因果关系。

**链路**（四步，已实测复现）：
1. llm 段 → `langchain_google_genai` → 拖入 `transformers`（+`torch`）；光 `import transformers` 就 **26.5s**
2. `transformers._create_module_alias()` 为 `models/*/image_processing_*.py` 造 **209 个空壳 module**
   塞进 `sys.modules`，每个挂的 `__getattr__` 会把**任意属性访问转发成一次真导入**
   （它只设了 `__file__ = None` 去挡 `inspect` 的探测，**没挡 `__path__`**）
3. Streamlit 的 `LocalSourcesWatcher` 在 `sys.modules` 一变就对**每个模块**探 `hasattr(m, "__path__")`
   → 命中空壳的 `__getattr__` → 真导入图像处理模块 → 缺 torchvision → 抛
4. `hasattr` 只吞 `AttributeError`，**不吞** `ModuleNotFoundError`；Streamlit 外层
   `except Exception` + `logger.warning(..., exc_info=True)` ⇒ 打全栈，但**不中断**

**量级**：扫一遍 **95 条**（209 个空壳里 108 个真 import torchvision），95 个模块名互不相同；
而且**每次 `sys.modules` 变化都重扫** ⇒ 这就是"很多"的来源。

**处置**：启动加 `--server.fileWatcherType=none`；要一劳永逸就在 `.streamlit/config.toml` 里写
`[server]` 段 + `fileWatcherType = "none"`（**段头必须写** —— 省掉它会直接 `AttributeError` 崩在配置解析）；
**不要**为此装 torchvision（项目零视觉依赖，装了纯属替上游背锅）。

**教训**：**无关噪声会训练出"忽略日志"的习惯**，比真 bug 更贵 —— 要么关掉它，
要么在 notes 里写清"这条可忽略、以及为什么可忽略"。