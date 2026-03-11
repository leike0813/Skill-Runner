## MODIFIED Requirements

### Requirement: 系统 MUST 提供可配置的引擎硬超时策略
系统 MUST 为引擎执行提供硬超时，并允许通过环境变量或运行时参数覆盖默认值；超时错误信息必须反映本次实际生效值。

#### Scenario: `/v1/jobs` runtime_options 可显式传入 hard timeout
- **WHEN** 客户端调用 `POST /v1/jobs`
- **AND** 请求体包含 `runtime_options.hard_timeout_seconds`
- **THEN** 系统接受该键并作为本次执行硬超时覆盖值
- **AND** 该值优先于全局默认与环境变量

#### Scenario: hard timeout 参数非法
- **WHEN** 客户端传入非正整数的 `runtime_options.hard_timeout_seconds`
- **THEN** 系统返回 `400`
- **AND** 错误信息明确该键必须为正整数
