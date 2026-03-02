# engine-auth-observability Specification

## MODIFIED Requirements

### Requirement: 鉴权会话日志持久化 MUST 默认关闭且仅允许显式启用
系统 MUST 在默认配置下禁用 `data/engine_auth_sessions/**` 的文件持久化写入，以降低敏感信息落盘风险。

#### Scenario: 默认配置下启动鉴权会话
- **WHEN** 创建 `oauth_proxy` 或 `cli_delegate` 鉴权会话
- **AND** 未显式开启鉴权日志持久化
- **THEN** 系统不得创建 `data/engine_auth_sessions/<transport>/<session_id>/`
- **AND** 会话状态机与 API 快照字段语义保持不变

#### Scenario: 显式开启鉴权日志持久化
- **WHEN** 配置显式启用鉴权日志持久化
- **THEN** 系统按既有目录结构写入日志
- **AND** `oauth_proxy` 至少包含 `events.jsonl` 与 `http_trace.log`
- **AND** `cli_delegate` 至少包含 `events.jsonl`、`pty.log`、`stdin.log`

### Requirement: 鉴权事件可观测语义 MUST 与落盘策略解耦
系统 MUST 保持鉴权会话状态和审计字段可观测，不得以“是否落盘日志”作为会话推进或成功判定前置条件。

#### Scenario: 落盘关闭时查询会话快照
- **WHEN** 客户端查询鉴权会话状态
- **THEN** 会话状态推进、错误码、`auth_url/user_code` 等字段语义不变
- **AND** 不要求 `log_root` 指向已创建目录

