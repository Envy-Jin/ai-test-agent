# 回归测试计划

**变更摘要**: 将分散的鉴权与 token 签发逻辑收口至 auth_common.py，并将固定 token 改为按手机号后四位动态派生。
**影响模块**: login, orders

## 必回归（must_regression）
- TC001 [login] 登录逻辑改用 verify_credentials 和 issue_token，token 生成规则已变更，必须回归
- TC003 [login] 凭据校验迁移至 auth_common.verify_credentials，需回归错误凭据拦截逻辑
- TC004 [orders] 订单查询鉴权改用 require_auth 函数，需验证有效 token 访问逻辑
- TC005 [orders] 无或错 token 校验改用 require_auth，需回归越权拦截逻辑

## 建议回归（should_regression）

## 可跳过（can_skip）
- TC002 [login] 参数缺失校验逻辑位于请求参数提取层，未受本次鉴权函数重构影响

## 需新增（need_add）
- [login] 验证 token 按手机号后四位动态派生 —— 覆盖点: 检查登录成功后返回的 token 是否正确包含手机号后四位（如 13800138000 对应 demo-token-8000）