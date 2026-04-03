## MODIFIED Requirements
### Requirement: 系统 MUST 提供引擎升级任务创建接口
系统 MUST 在创建升级任务前基于 managed prefix 判定引擎安装状态，不得被全局 PATH 可执行项误判短路。

#### Scenario: single task installs when managed engine missing
- **WHEN** 客户端创建 `mode=single` 的 engine 任务且目标 engine 在 managed prefix 下不存在
- **THEN** 系统执行 single-engine ensure/install
- **AND** 任务结果显式标记 `action=install`

#### Scenario: single task upgrades when managed engine exists
- **WHEN** 客户端创建 `mode=single` 的 engine 任务且目标 engine 已在 managed prefix 下存在
- **THEN** 系统执行现有 single-engine upgrade
- **AND** 任务结果显式标记 `action=upgrade`

### Requirement: 升级结果 MUST 包含 per-engine stdout/stderr
系统 MUST 在路径跑偏或安装失败时输出可诊断信息，帮助定位 managed/global 冲突。

#### Scenario: single-engine task result distinguishes action type
- **WHEN** 客户端查询单 engine 任务结果
- **THEN** per-engine 结果除 `status/stdout/stderr/error` 外还包含 `action`
- **AND** `action` 值为 `install` 或 `upgrade`
