## ADDED Requirements

### Requirement: 管理界面 MUST 支持基础鉴权并可由环境变量初始化
系统 MUST 支持通过配置启用 HTTP Basic Auth，且配置项 MUST 支持环境变量覆盖。

#### Scenario: 环境变量启用鉴权
- **WHEN** `UI_BASIC_AUTH_ENABLED=true`
- **THEN** 系统按 `UI_BASIC_AUTH_USERNAME` / `UI_BASIC_AUTH_PASSWORD` 进行认证

### Requirement: 鉴权开启时管理入口 MUST 被保护
当基础鉴权启用时，系统 MUST 保护 `/ui/*` 路由与技能包安装管理接口。

#### Scenario: 未认证访问管理页
- **WHEN** 未携带合法 Basic Auth 凭据访问 `/ui`
- **THEN** 系统返回 `401`

#### Scenario: 未认证调用安装接口
- **WHEN** 未携带合法 Basic Auth 凭据访问 `/v1/skill-packages/install`
- **THEN** 系统返回 `401`

### Requirement: 鉴权配置非法时系统 MUST fail fast
当鉴权启用但用户名或密码缺失时，系统 MUST 在启动阶段报错并拒绝启动。

#### Scenario: 启用但凭据缺失
- **WHEN** `UI_BASIC_AUTH_ENABLED=true` 且用户名/密码为空
- **THEN** 系统启动失败并输出明确错误信息
