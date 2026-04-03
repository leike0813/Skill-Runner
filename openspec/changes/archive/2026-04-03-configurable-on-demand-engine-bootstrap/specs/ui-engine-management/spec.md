## MODIFIED Requirements
### Requirement: UI MUST provide engine lifecycle controls from the engines table
系统 MUST 在 `/ui/engines` 表格中提供单 engine 生命周期入口。

#### Scenario: upgrade button is reused as install for missing engine
- **WHEN** 某 engine 在 managed prefix 下未安装
- **THEN** 表格中的现有单 engine 升级按钮文案显示为“安装”
- **AND** 点击后复用现有任务通道执行单 engine install

#### Scenario: installed engine keeps upgrade action
- **WHEN** 某 engine 已在 managed prefix 下安装
- **THEN** 同一按钮文案显示为“升级”
- **AND** 点击后执行现有 single-engine upgrade

#### Scenario: task status panel shows actual action type
- **WHEN** UI 展示单 engine 任务状态
- **THEN** 状态面板显示该 engine 本次动作是 `install` 或 `upgrade`
- **AND** 不得把 install 误标为 upgrade
