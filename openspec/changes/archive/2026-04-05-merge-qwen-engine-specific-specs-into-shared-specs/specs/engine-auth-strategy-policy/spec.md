## ADDED Requirements

### Requirement: Qwen provider-aware auth policy MUST be defined in the shared strategy contract
系统 MUST 通过共享 `engine-auth-strategy-policy` capability 定义 Qwen 的 provider-aware 鉴权能力矩阵，而不是依赖独立的 qwen auth capability。

#### Scenario: qwen providers are declared explicitly in shared strategy
- **WHEN** 策略文件定义 `qwen`
- **THEN** `qwen-oauth`、`coding-plan-china`、`coding-plan-global` MUST 作为显式 provider 条目出现
- **AND** 未声明 provider MUST 视为不支持

#### Scenario: qwen transport and method matrix is strategy-driven
- **WHEN** 策略服务解析 `qwen` provider 的 transport 配置
- **THEN** `qwen-oauth` MUST 声明 `oauth_proxy` 与 `cli_delegate`
- **AND** `coding-plan-china` 与 `coding-plan-global` MUST 声明 `oauth_proxy` 与 `cli_delegate`
- **AND** method 能力 MUST 来自共享策略文件，而不是独立 capability 或 engine 名称硬编码
