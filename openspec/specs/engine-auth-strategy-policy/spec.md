# engine-auth-strategy-policy Specification

## Purpose
TBD - created by archiving change centralize-engine-auth-strategy-policy. Update Purpose after archive.
## Requirements
### Requirement: Engine auth capability matrix MUST be strategy-file driven

系统 MUST 使用单一策略文件定义 engine/provider 在不同 transport 下的鉴权能力矩阵，并提供统一查询接口供 UI、编排与启动校验复用。

#### Scenario: provider-aware engines share one strategy contract

- **WHEN** 策略文件声明 `opencode` 或 `qwen` provider
- **THEN** UI、driver 注册和运行时编排 MUST 从同一策略文件解析 provider-scoped transport/method 能力
- **AND** 系统 MUST NOT 通过 engine 名称硬编码默认 provider 矩阵

### Requirement: Strategy service MUST expose normalized capability queries

策略服务 MUST 对会话 transport 与 runtime transport 共享同一方法语义，并允许会话侧消费 transport session behavior。

#### Scenario: conversation methods use auth_code_or_url canonical value

- **WHEN** 策略文件声明会话内人工 OAuth 返回内容输入
- **THEN** 会话 methods MUST 使用 `auth_code_or_url`
- **AND** 不得继续输出历史值 `authorization_code`

#### Scenario: waiting_auth reads session behavior from strategy

- **WHEN** 会话编排请求 engine/provider 的会话 transport 行为
- **THEN** 策略服务 MUST 返回该 transport 的 `session_behavior`
- **AND** 编排层 MUST 复用此结果生成 pending auth 读模型

### Requirement: OpenCode provider policy MUST be explicit

OpenCode provider 能力 MUST 在策略文件中显式列举，不得由代码硬编码推导默认矩阵。

#### Scenario: undeclared opencode provider
- **WHEN** provider 未在策略文件声明
- **THEN** 策略服务 MUST 将其视为不支持

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

