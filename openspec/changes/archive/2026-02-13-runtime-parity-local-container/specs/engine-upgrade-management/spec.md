## MODIFIED Requirements

### Requirement: 系统 MUST 提供引擎升级任务创建接口
系统 MUST 在容器模式与本地模式下都能创建并执行升级任务，不依赖容器专属目录假设。

#### Scenario: 本地模式创建升级任务
- **WHEN** 服务在本地模式运行且客户端提交升级请求
- **THEN** 系统创建任务并进入执行队列
- **AND** 不会因写入 `/data` 失败而中断

### Requirement: 升级结果 MUST 包含 per-engine stdout/stderr
系统 MUST 在两种运行模式下保持相同的 per-engine 结果结构，并完整返回 stdout/stderr。

#### Scenario: 本地模式单引擎升级失败
- **WHEN** 某引擎升级命令失败
- **THEN** 返回该引擎 `status=failed`
- **AND** 返回该引擎的 `stdout` 与 `stderr`

### Requirement: 系统 MUST 提供 Engine Model Manifest 查询接口
系统 MUST 在容器模式与本地模式下使用同一运行时环境解析策略完成版本检测与 manifest 查询。

#### Scenario: 本地模式查询 manifest
- **WHEN** 客户端请求 `GET /v1/engines/{engine}/models/manifest`
- **THEN** 返回 `cli_version_detected` 与 manifest 视图
- **AND** 检测路径来自受管运行时配置（非硬编码容器路径）
