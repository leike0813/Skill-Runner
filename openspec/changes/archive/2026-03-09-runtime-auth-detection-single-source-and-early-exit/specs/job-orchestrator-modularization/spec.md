## ADDED Requirements

### Requirement: Runtime auth detection MUST use adapter profile as single source
运行时鉴权判定规则 MUST 由引擎 adapter profile 声明，并由 runtime 按 profile 加载；不得再依赖独立 rule-pack 目录作为并行来源。

#### Scenario: auth detection rules are loaded from adapter profile
- **GIVEN** 引擎 adapter profile 中定义 `auth_detection.rules`
- **WHEN** runtime 加载鉴权判定规则
- **THEN** 规则 MUST 仅从 adapter profile 加载
- **AND** 规则优先级 MUST 按 `priority` 生效

### Requirement: Runtime adapter MUST early-exit blocked auth-required runs
当 run 读流阶段命中高置信 `auth_required` 且进程进入空闲阻塞，adapter MUST 提前终止该进程并返回 `AUTH_REQUIRED`，交由 orchestrator 进入 `waiting_auth`。

#### Scenario: high-confidence auth-required with blocking idle
- **GIVEN** 运行中进程输出命中 `auth_required/high`
- **AND** 进程在阈值窗口内无新输出且仍存活
- **WHEN** adapter 监控循环触发 early-exit
- **THEN** adapter MUST 终止当前进程并返回 `failure_reason=AUTH_REQUIRED`
- **AND** orchestrator MUST 进入既有 `waiting_auth` 流程
