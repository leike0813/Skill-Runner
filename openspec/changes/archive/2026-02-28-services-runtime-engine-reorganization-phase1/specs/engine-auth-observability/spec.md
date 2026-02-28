## ADDED Requirements

### Requirement: OpenAI shared auth protocol MUST be engines/common SSOT
OpenAI 共享鉴权协议实现 MUST 位于 `server/engines/common/openai_auth/*`，并作为 codex/opencode 共用单一来源。

#### Scenario: OpenAI auth import path
- **WHEN** codex 或 opencode 需要 OpenAI OAuth/device 协议能力
- **THEN** 通过 `server/engines/common/openai_auth/*` 导入
- **AND** 不再依赖 `server/services/oauth_openai_proxy_common.py` 或 `server/services/openai_device_proxy_flow.py`

### Requirement: Auth session behavior MUST remain stable during reorganization
目录重组期间，鉴权会话状态推进与终态行为 MUST 保持兼容。

#### Scenario: Existing auth flows
- **WHEN** 执行现有 oauth_proxy/cli_delegate 鉴权流程
- **THEN** 状态机语义与终态行为不回归
