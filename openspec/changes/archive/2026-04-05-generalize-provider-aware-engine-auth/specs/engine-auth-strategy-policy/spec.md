## MODIFIED Requirements

### Requirement: Engine auth capability matrix MUST be strategy-file driven

系统 MUST 使用单一策略文件定义 engine/provider 在不同 transport 下的鉴权能力矩阵，并提供统一查询接口供 UI、编排与启动校验复用。

#### Scenario: provider-aware engines share one strategy contract

- **WHEN** 策略文件声明 `opencode` 或 `qwen` provider
- **THEN** UI、driver 注册和运行时编排 MUST 从同一策略文件解析 provider-scoped transport/method 能力
- **AND** 系统 MUST NOT 通过 engine 名称硬编码默认 provider 矩阵

## ADDED Requirements

### Requirement: Provider-aware engine provider policy MUST be explicit

provider-aware engine 的 provider 能力 MUST 在策略文件中显式列举，不得由代码推导默认 provider 集合。

#### Scenario: undeclared provider for provider-aware engine

- **WHEN** provider 未在 `opencode` 或 `qwen` 的策略块中声明
- **THEN** 策略服务 MUST 将其视为不支持

#### Scenario: qwen providers are declared explicitly

- **WHEN** 策略文件定义 `qwen`
- **THEN** `qwen-oauth`、`coding-plan-china`、`coding-plan-global` MUST 作为显式 provider 条目出现
