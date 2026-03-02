# interactive-run-observability Specification

## Purpose
定义 waiting_user 的可观测状态暴露和日志轮询建议区分策略。

## MODIFIED Requirements

### Requirement: 系统 MUST 暴露 waiting_user 的可观测状态
系统 MUST 在状态接口中明确体现 run 是否处于等待用户输入阶段。

#### Scenario: 查询 waiting_user 状态
- **GIVEN** run 当前在等待用户输入
- **WHEN** 客户端调用 `GET /v1/jobs/{request_id}`
- **THEN** 响应 `status=waiting_user`
- **AND** 包含当前待决交互标识（如 `pending_interaction_id`）
