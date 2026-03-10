## ADDED Requirements

### Requirement: Run Detail timeline/protocol panels MUST remain stable across running-to-terminal transition
管理 UI 在 run 从 running 切换到 terminal 时，timeline 与 protocol 面板 MUST 不出现因观测口径切换导致的事件回退。

#### Scenario: user observes protocol panel across terminal transition
- **GIVEN** 用户在 Run Detail 页面持续观察同一 run
- **WHEN** run 状态从 running 变为 terminal
- **THEN** 面板数据源切换 MUST 保持事件集合稳定（除 limit 裁剪）
- **AND** MUST NOT 因 terminal 收敛而出现明显事件数量突降。
