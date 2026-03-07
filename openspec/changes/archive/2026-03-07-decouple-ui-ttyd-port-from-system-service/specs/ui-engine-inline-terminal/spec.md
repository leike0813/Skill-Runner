## ADDED Requirements

### Requirement: 内嵌终端默认端口 MUST 使用高位默认值
系统 MUST 将 `UI_SHELL_TTYD_PORT` 默认值设置为高位端口，降低与宿主机系统 ttyd 服务冲突概率。

#### Scenario: 未配置环境变量
- **WHEN** 运行环境未设置 `UI_SHELL_TTYD_PORT`
- **THEN** 内嵌终端默认端口为 `17681`

#### Scenario: 显式覆盖端口
- **WHEN** 用户设置 `UI_SHELL_TTYD_PORT=<custom_port>`
- **THEN** 系统使用该端口
- **AND** 仍执行现有端口可用性校验逻辑
