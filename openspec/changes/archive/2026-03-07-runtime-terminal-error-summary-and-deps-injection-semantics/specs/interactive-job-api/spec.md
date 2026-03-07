## MODIFIED Requirements

### Requirement: runtime.dependencies MUST be attempted before agent command execution
系统 MUST 在 agent 命令执行前尝试根据 skill manifest `runtime.dependencies` 注入运行时依赖。

#### Scenario: dependency injection probe succeeds
- **GIVEN** skill manifest 声明了 `runtime.dependencies`
- **WHEN** backend 开始执行该 turn
- **THEN** backend MUST 先完成依赖注入探测
- **AND** probe 成功后 MUST 以注入后的命令执行 agent

#### Scenario: dependency injection probe fails with best-effort fallback
- **GIVEN** skill manifest 声明了 `runtime.dependencies`
- **WHEN** backend 依赖注入探测失败
- **THEN** backend MUST 写入可观测 warning
- **AND** backend MUST 回退执行原始 agent 命令（best-effort）
