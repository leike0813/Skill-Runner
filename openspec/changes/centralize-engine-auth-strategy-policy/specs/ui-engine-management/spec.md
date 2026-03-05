## ADDED Requirements

### Requirement: 鉴权菜单能力矩阵 MUST 来源于统一策略文件

系统 MUST 使用后端统一策略文件生成 `/ui/engines` 的鉴权菜单能力矩阵，不得在 UI router 或模板中硬编码引擎/transport/provider 组合。

#### Scenario: render auth menu capabilities from strategy service
- **WHEN** 用户访问 `/ui/engines`
- **THEN** 后端注入的 `auth_ui_capabilities` MUST 来源于统一策略服务
- **AND** 菜单可用项 MUST 与后端启动校验能力保持一致

### Requirement: OpenCode provider 菜单 MUST 使用策略文件声明能力

系统 MUST 以策略文件中显式列举的 provider 组合作为 OpenCode 鉴权方式可用性的判定依据。

#### Scenario: provider not declared in strategy is unavailable
- **WHEN** OpenCode provider 未在策略文件声明对应 transport+methods
- **THEN** UI MUST NOT 展示该 provider 的对应鉴权方式入口
