# interactive-job-cancel-api Specification

## Purpose
定义前端可调用的 Job 终止接口及其幂等语义。

## MODIFIED Requirements

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
