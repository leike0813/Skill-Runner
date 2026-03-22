## MODIFIED Requirements

### Requirement: runtime auth-required判定 MUST 以 parser signal 为唯一主语义
run 执行链路中的鉴权判定 MUST 直接消费 parser 产出的 `auth_signal`，不得再依赖独立规则层做二次文本匹配。terminal `AUTH_REQUIRED` 归因同样 MUST 以高置信度 `auth_signal` 为前提，不得仅凭低置信度审计信号或裸 `failure_reason` 强制升级。

#### Scenario: high-confidence auth signal triggers waiting_auth path
- **GIVEN** parser 在运行流中产出 `auth_signal.required=true` 且 `confidence=high`
- **AND** 进程输出进入 idle 阻塞并超过全局 grace
- **WHEN** runtime 触发 early-exit
- **THEN** run MUST 以 `AUTH_REQUIRED` 进入鉴权编排路径
- **AND** lifecycle MUST 将状态推进到 `waiting_auth`（在策略允许时）

#### Scenario: low confidence signal is audited but not forced as waiting_auth or auth-required terminal
- **GIVEN** parser 产出 `auth_signal.required=true` 且 `confidence=low`
- **WHEN** run 进入终态归一化
- **THEN** 审计中 MUST 记录该鉴权信号
- **AND** MUST NOT 仅凭该信号强制触发 `waiting_auth`
- **AND** MUST NOT 仅凭该信号将 terminal failure reason 改写为 `AUTH_REQUIRED`
