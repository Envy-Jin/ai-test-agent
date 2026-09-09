# Day 35 学习笔记：第 5 周周末综合实战（下）—— 流程工程化收口：共享底座 + 场景工厂 + 两段式评审门

## 日期
2026-09-07

## 今日成果
- [ ] rule of three 收口：day31/day32 六处重复（_read_text×3/_schema_path×2/_out_dir）→ day35_common 叶子模块 + 等价性回归（同输入同输出）
- [ ] 蓝图工厂：ScenarioConfig(login/register) + build_blueprint(sc)；LOGIN 蓝图与 Day 34 BLUEPRINT 契约全等（断言证明）
- [ ] 盘点工厂化：scan_blueprint 豁免集从传入蓝图派生；register 缺资产 → missing_input 精确到文件名
- [ ] 执行器回归：工厂 LOGIN 蓝图喂 Day 34 执行器，S4 --force 重生成指纹稳定且与既有同指纹
- [ ] register 缺口报告：outputs/flow/register_fill_plan.md（补齐清单自动生成）
- [ ] 两段式评审门：generate_seed → approve_seed(盖章 reviewed_by/at) → upsert 硬门禁 raise；dry_run 预演（零 API 全链）
- [ ] 原则落地：入库对象=评审对象（payload 不可变）/ 评审门硬阻断 / 审计可追溯（created_at/reviewed_by/reviewed_at）

## 核心概念
### 1. 先审后入库（质量门，不是流程摆设）
# Day 31 reviewed=False 只是 print（软提示，可绕过）→ Day 35 raise ReviewGateError（硬门禁）
# 门禁检查在构造入库链路之前 → raise 路径零 API 可测（能进 CI）
# 模型产物非确定性 → 知识库只收"人审过的那一份"（payload 不可变，错了重新生成而不是偷改信封）

### 2. 场景即参数（蓝图是数据）
# ScenarioConfig = 资产路径 + mock 端口；build_blueprint = 模板实例化
# 黑盒契约断言边界：stage_id/kind/runner/inputs/outputs/mock_bug（title/note/cmd 不进断言）
# 换场景 ≠ 重写蓝图 = 换配置 + 补资产；多场景真并行的下一障碍 = 产物路径无场景维度

### 3. 重复即抽取（rule of three + 安全网）
# 触发规则：一次内联/二次考虑/三次抽取——第三份出现就是抽取信号
# 公共底座 = 叶子模块（无框架依赖）；路径锚 __file__；等价回归 = 抽取的安全网
# 路径等价断言比 normpath（语义）不比字面（os.path.join 不折叠 '..'）

### 4. 本日踩坑记录
# pydantic v2 实测：model_dump() 深拷贝输出不共享；model_copy(deep=False) 浅拷贝共享嵌套容器
# datetime 字段 model_dump() 后 json.dumps 直接 TypeError → 存 ISO 文本或 mode="json"
# dict[str, object] 取值是 object → isinstance 收窄或交给 model_validate；json.loads 是 Any → 显式收窄立边界
# ValidationError → 异常链 raise ... from exc（__cause__ 保留根因）

## 还存在的问题 / 待办
- register 资产补齐（schemas/register.json + bugs/register_bugs.md）→ 真跑通 register 全链（步骤 4.4 延伸）
- 多场景并行需要产物目录加场景维度 outputs/<scenario>/…（S4/S6/S7/S8 共享路径冲突）
- 评审门扩展 doc_type="requirement"（S1 需求/用例产物入库，扩展点见 5.5 第 4 点）
- day35_common 物理并入 src/agent/utils.py + 旧脚本薄包装 → Day 36 项目架构重构
- 第 5 周脚本归档（archive/week5，含 day29-35）→ 建议 Day 36 重构前做，需先做 import 传递闭包分析
