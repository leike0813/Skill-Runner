## ADDED Requirements

### Requirement: waiting_auth challenge 编排 MUST 受策略能力约束

系统 MUST 仅在策略文件声明支持的组合下进入 waiting_auth challenge 编排路径。

#### Scenario: unsupported combination does not create pending auth
- **GIVEN** auth detection 命中 `auth_required/high`
- **AND** 当前 engine/provider 在策略文件中无会话可用方式
- **WHEN** 编排器尝试创建 pending auth
- **THEN** 系统 MUST NOT 创建 pending auth challenge

#### Scenario: single supported method directly starts challenge
- **GIVEN** 当前 engine/provider 在策略文件中仅有一个会话可用方式
- **WHEN** run 进入 waiting_auth
- **THEN** 系统 MAY 直接创建 challenge_active
- **AND** challenge 的 `auth_method` MUST 与策略结果一致
