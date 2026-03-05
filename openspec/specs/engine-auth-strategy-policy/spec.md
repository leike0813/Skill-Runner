# engine-auth-strategy-policy Specification

## Purpose
TBD - created by archiving change centralize-engine-auth-strategy-policy. Update Purpose after archive.
## Requirements
### Requirement: Engine auth capability matrix MUST be strategy-file driven

系统 MUST 使用单一策略文件定义 engine/provider 在不同 transport 下的鉴权能力矩阵，并提供统一查询接口供 UI、编排与启动校验复用。

#### Scenario: load and validate strategy file at startup
- **WHEN** 服务启动并初始化鉴权策略服务
- **THEN** 系统 MUST 加载策略文件并通过 schema 校验
- **AND** 校验失败 MUST 触发明确错误，不得 silent fallback

### Requirement: Strategy service MUST expose normalized capability queries

策略服务 MUST 暴露统一查询，支持 UI 能力矩阵、driver 注册组合与会话编排查询。

#### Scenario: list ui capabilities
- **WHEN** UI 请求鉴权能力矩阵
- **THEN** 策略服务 MUST 返回 `transport -> engine -> methods/provider-methods` 的规范化结果

#### Scenario: resolve in-conversation methods
- **WHEN** 会话编排请求 engine/provider 的会话内鉴权方式
- **THEN** 策略服务 MUST 返回 in-conversation transport 下的会话方法集合

### Requirement: OpenCode provider policy MUST be explicit

OpenCode provider 能力 MUST 在策略文件中显式列举，不得由代码硬编码推导默认矩阵。

#### Scenario: undeclared opencode provider
- **WHEN** provider 未在策略文件声明
- **THEN** 策略服务 MUST 将其视为不支持

