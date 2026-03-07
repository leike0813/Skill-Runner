## ADDED Requirements

### Requirement: Engine 管理页内嵌终端入口 MUST 与统一 ttyd 端口策略一致
系统 MUST 保证 Engine 管理页的内嵌终端入口与统一 `UI_SHELL_TTYD_PORT` 策略一致，不依赖固定 `7681` 常量。

#### Scenario: 默认部署访问内嵌终端
- **WHEN** 用户通过默认部署进入 `/ui/engines`
- **THEN** 内嵌终端链接使用会话返回的 `ttyd_port`
- **AND** 默认端口为 `17681`

#### Scenario: 自定义端口访问内嵌终端
- **WHEN** 用户通过环境变量修改 `UI_SHELL_TTYD_PORT`
- **THEN** 页面使用后端返回的会话端口访问 ttyd
- **AND** 不要求前端改写固定端口常量
