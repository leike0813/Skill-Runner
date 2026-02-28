## ADDED Requirements

### Requirement: Auth runtime observability MUST be rooted under runtime/auth
鉴权会话的状态与日志管理 MUST 由 `server/runtime/auth` 提供统一实现（session store、log writer、callback router）。

#### Scenario: Session log paths are initialized
- **WHEN** 鉴权会话启动
- **THEN** 日志路径由 `runtime/auth/log_writer.py` 生成
- **AND** 路径按 transport + session 维度组织

### Requirement: Callback handling MUST use shared callback router
OAuth callback 输入解析与页面响应 MUST 复用 `runtime/auth/callback_router.py`，避免各路由重复拼接逻辑。

#### Scenario: OpenAI callback reaches router
- **WHEN** callback 命中 `/auth/callback` 相关端点
- **THEN** 路由使用 callback router 解析并执行 manager handler
- **AND** 错误页面语义保持一致

## MODIFIED Requirements

### Requirement: Legacy auth_runtime services path is retired
phase2 后，`server/services/auth_runtime/*` MUST 不再作为运行实现路径。

#### Scenario: Runtime auth import resolution
- **WHEN** 模块导入 auth runtime 能力
- **THEN** 来源为 `server/runtime/auth/*`
- **AND** 旧 `server/services/auth_runtime/*` 文件已移除
