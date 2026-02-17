# interactive-job-cancel-api Specification

## Purpose
TBD - created by archiving change interactive-26-job-termination-api-and-frontend-control. Update Purpose after archive.
## Requirements
### Requirement: 系统 MUST 提供前端可调用的 Job 终止接口
系统 MUST 暴露标准 cancel 接口，使客户端可主动终止指定运行任务。

#### Scenario: 终止常规 job
- **WHEN** 客户端调用 `POST /v1/jobs/{request_id}/cancel`
- **AND** `request_id` 对应活跃 run（`queued/running/waiting_user`）
- **THEN** 系统返回成功响应
- **AND** 响应包含 `request_id/run_id/status/accepted/message`

#### Scenario: 终止临时 skill run
- **WHEN** 客户端调用 `POST /v1/temp-skill-runs/{request_id}/cancel`
- **AND** `request_id` 对应活跃 run
- **THEN** 系统返回成功响应
- **AND** 语义与常规 job 终止一致

### Requirement: 终止接口 MUST 具备幂等语义
系统 MUST 对重复 cancel 请求返回幂等结果，不重复执行破坏性动作。

#### Scenario: 已终态再次取消
- **GIVEN** run 已为 `succeeded/failed/canceled`
- **WHEN** 客户端再次调用 cancel
- **THEN** 系统返回 `200`
- **AND** `accepted=false`
- **AND** 不改变原终态

### Requirement: 取消成功后 MUST 标准化终态错误信息
系统 MUST 在取消终态写入统一错误码与消息，供前端稳定识别。

#### Scenario: 用户取消落库
- **WHEN** 活跃 run 被成功取消
- **THEN** 最终状态为 `canceled`
- **AND** `error.code = CANCELED_BY_USER`
- **AND** `error.message` 明确为用户取消语义

