# engine-hard-timeout-policy Specification

## Purpose
TBD - created by archiving change run-observability-streaming-and-timeout. Update Purpose after archive.
## Requirements
### Requirement: 系统 MUST 提供可配置的引擎硬超时策略
系统 MUST 为引擎执行提供硬超时，并允许通过环境变量覆盖默认值。

#### Scenario: 使用默认超时
- **WHEN** 未设置 `SKILL_RUNNER_ENGINE_HARD_TIMEOUT_SECONDS`
- **THEN** 系统默认硬超时为 `1200` 秒

#### Scenario: 环境变量覆盖
- **WHEN** 设置了 `SKILL_RUNNER_ENGINE_HARD_TIMEOUT_SECONDS`
- **THEN** 系统使用该值作为默认硬超时
- **AND** 运行时显式传入 `hard_timeout_seconds` 仍可进一步覆盖

