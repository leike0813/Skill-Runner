## ADDED Requirements

### Requirement: Runtime option hard-cut MUST NOT alter auth session observability semantics
The runtime option hard-cut MUST NOT change auth session state-machine or observability semantics.

#### Scenario: Auth session status progression after runtime option hard-cut
- **WHEN** 用户在管理 UI 发起任意鉴权会话（oauth_proxy 或 cli_delegate）
- **THEN** 鉴权状态推进与事件可见性保持既有语义
- **AND** runtime options 键名调整不会影响 auth session observability
