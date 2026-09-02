# 数据模型：用户表（users）

用户信息表，用于登录注册场景。

字段规则：
- id: int，主键，自增，必填
- phone: varchar(11)，手机号，必填，格式：1[3-9] 开头共 11 位数字
- email: varchar(100)，邮箱，可选
- age: int，年龄，必填，范围 1-150
- username: varchar(50)，用户名，必填，只允许字母数字下划线，长度 3-20
- gender: enum('男','女','未知')，可选，默认 '未知'
- created_at: datetime，可选，默认当前时间
