## ADDED Requirements

### Requirement: Docker Compose 模板 MUST 采用主服务默认启用 + 客户端可选启用结构
系统 MUST 在容器部署模板中默认启用主服务，并提供可选的 E2E 客户端服务块，避免默认部署拓扑被客户端耦合。

#### Scenario: 默认 compose 启动只包含主服务
- **WHEN** 用户按默认 compose 文件执行启动（不改注释块）
- **THEN** 主服务被启动
- **AND** E2E 客户端服务不会被启动

#### Scenario: 用户按提示启用可选客户端
- **WHEN** 用户按 compose 文件中的提示取消 E2E 客户端服务注释
- **THEN** compose 可以额外启动客户端服务
- **AND** 不影响主服务既有启动参数

### Requirement: Compose 中可选客户端服务 MUST 与主服务复用同一镜像
系统 MUST 让 compose 的可选客户端服务与主服务服务复用同一镜像，仅通过入口命令或入口脚本区分运行角色。

#### Scenario: 单镜像双角色启动
- **WHEN** compose 同时启用主服务与可选客户端服务
- **THEN** 两个服务使用同一镜像标签
- **AND** 分别执行各自角色对应的启动命令
