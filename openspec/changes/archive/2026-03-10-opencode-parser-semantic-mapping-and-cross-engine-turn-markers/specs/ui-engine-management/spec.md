## ADDED Requirements

### Requirement: Management protocol history MUST expose RASP turn markers
管理端协议历史查询在 `stream=rasp` 时 MUST 可见 turn marker 审计事件。

#### Scenario: query rasp history after attempt execution
- **GIVEN** 某次 attempt 已产生回合开始与结束
- **WHEN** 调用 `GET /v1/management/runs/{request_id}/protocol/history?stream=rasp`
- **THEN** 返回事件中 MUST 包含 `agent.turn_start` 与 `agent.turn_complete`
- **AND** 事件顺序 MUST 满足 `agent.turn_start` 在 `agent.turn_complete` 之前
