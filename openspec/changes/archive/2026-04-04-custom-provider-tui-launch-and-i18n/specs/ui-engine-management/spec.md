## MODIFIED Requirements

### Requirement: Engine Management UI

引擎管理页 MUST 在 custom provider 区支持 provider-row 级 TUI 启动。

#### Scenario: Launch TUI from provider row

- **WHEN** 用户在 custom provider 表格的某个 provider 行点击 `启动TUI`
- **THEN** 系统 MUST 在当前已选 engine 上弹出模型选择层
- **AND** 用户确认后 MUST 以严格 `provider/model` 形式启动该 engine 的 TUI

#### Scenario: Unsupported engine hides provider-backed TUI

- **WHEN** 当前已选 engine 不支持 provider-backed TUI
- **THEN** provider 行 MUST NOT 显示 `启动TUI`

