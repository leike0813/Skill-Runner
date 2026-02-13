## MODIFIED Requirements

### Requirement: 系统 MUST 提供引擎升级任务创建接口
系统 MUST 在创建升级任务前基于 managed prefix 判定引擎安装状态，不得被全局 PATH 可执行项误判短路。

#### Scenario: global 可执行但 managed 缺失
- **WHEN** 某 engine 在全局 PATH 可执行但 managed prefix 下缺失
- **THEN** `ensure/upgrade` 逻辑仍按 managed 缺失处理
- **AND** 安装目标为 managed prefix

### Requirement: 升级结果 MUST 包含 per-engine stdout/stderr
系统 MUST 在路径跑偏或安装失败时输出可诊断信息，帮助定位 managed/global 冲突。

#### Scenario: managed 安装失败
- **WHEN** 某 engine 安装到 managed prefix 失败
- **THEN** 返回该 engine 的 `status=failed`
- **AND** `stderr` 中包含安装失败上下文
