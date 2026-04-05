## ADDED Requirements

### Requirement: Qwen auth completion semantics MUST be governed by shared auth observability
系统 MUST 通过共享 auth observability capability 约束 Qwen 的 oauth_proxy 与 coding-plan 鉴权闭环，而不是依赖独立 qwen auth capability。

#### Scenario: qwen-oauth oauth_proxy exposes device authorization challenge
- **WHEN** 用户为 `provider_id=qwen-oauth` 启动 `transport=oauth_proxy` 会话
- **THEN** 会话快照 MUST 返回 `auth_url` 与 `user_code`
- **AND** 其等待与完成语义 MUST 复用共享 auth session 状态机

#### Scenario: qwen-oauth completion writes managed oauth credentials
- **WHEN** `qwen-oauth` 的 token polling 成功完成
- **THEN** 系统 MUST 写入 `.qwen/oauth_creds.json`
- **AND** 会话成功判定 MUST 以该标准闭环语义进入 `succeeded`

#### Scenario: qwen coding-plan completion writes managed settings
- **WHEN** `coding-plan-china` 或 `coding-plan-global` 鉴权成功
- **THEN** 系统 MUST 写入 `.qwen/settings.json`
- **AND** 写盘结果 MUST 作为共享 auth observability 的一部分可被后续状态判断消费
