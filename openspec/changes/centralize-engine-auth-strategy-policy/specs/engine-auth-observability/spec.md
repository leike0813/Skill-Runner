## ADDED Requirements

### Requirement: Engine auth 启动校验能力 MUST 与 UI 能力同源

系统 MUST 使用同一策略文件驱动 driver registry 能力校验与 UI 菜单能力展示，避免出现“可见但不可启动”组合。

#### Scenario: strategy-supported combination is startable
- **WHEN** 某 transport+engine(+provider)+auth_method 组合在策略文件中声明支持
- **THEN** driver registry MUST 支持该组合

#### Scenario: strategy-unsupported combination is rejected
- **WHEN** 某组合未在策略文件声明
- **THEN** driver registry MUST 拒绝该组合
- **AND** 返回错误应明确指出不支持的组合信息
