# interactive-job-api Specification

## Purpose
定义任务执行模式选择、待决交互查询和交互回复提交的 API 约束。

## MODIFIED Requirements

### Requirement: 系统 MUST 支持任务执行模式选择
系统 MUST 支持 `auto` 与 `interactive` 两种执行模式，并保持默认向后兼容。

#### Scenario: 未显式提供执行模式
- **WHEN** 客户端调用 `POST /v1/jobs` 且未提供 `execution_mode`
- **THEN** 系统按 `auto` 模式执行
- **AND** 现有接口行为不变

#### Scenario: 显式请求 interactive 模式
- **WHEN** 客户端调用 `POST /v1/jobs` 且 `execution_mode=interactive`
- **THEN** 系统接受请求并按交互模式编排
