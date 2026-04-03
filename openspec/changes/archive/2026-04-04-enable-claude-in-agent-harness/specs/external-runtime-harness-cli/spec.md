## MODIFIED Requirements

### Requirement: Harness CLI MUST 接受 Claude 作为合法引擎
系统 MUST 支持 `claude` 作为 harness CLI 的合法 engine 标识，适用于 `start` 子命令与直接引擎语法。

#### Scenario: start claude is accepted
- **WHEN** 用户执行 `agent_harness start claude ...`
- **THEN** harness MUST 将其视为合法引擎
- **AND** MUST NOT 返回 `ENGINE_UNSUPPORTED`

#### Scenario: direct claude syntax is accepted
- **WHEN** 用户执行 `agent_harness claude ...`
- **THEN** harness MUST 将其视为合法引擎
- **AND** MUST 继续进入共享 runtime start 路径
