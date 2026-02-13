## Why

当前服务在容器模式与本地模式下存在运行时分歧，尤其是 Engine 升级脚本默认落到 `/data`，会在本地触发权限错误（如 `mkdir: cannot create directory '/data': Permission denied`）。这会导致“本地可用性”不稳定，也破坏了双模式一致性目标。

## What Changes

- 引入统一运行时解析层：自动判定 `container/local` 与 OS，并统一导出默认目录与环境变量。
- 引入 Managed Prefix 安装与执行策略：Agent CLI 在受管前缀内安装/升级/调用，不依赖系统全局 `npm -g`。
- 引入 Agent 配置隔离策略：服务默认使用独立 Agent Home，避免与用户默认 CLI 配置互相污染。
- 增加“仅导入鉴权凭证”能力：允许将既有登录凭证导入隔离环境，不导入 settings。
- 统一所有脚本默认路径策略，移除散落的硬编码路径（如 `/data` 兜底）。
- 提供 Linux/Windows 本地一键部署脚本，保证本地完整可用（含 Windows）。

## Capabilities

### New Capabilities
- `runtime-environment-parity`: 统一容器/本地运行时默认路径、环境变量和执行上下文，确保 Engine 管理行为一致。
- `local-deploy-bootstrap`: 提供 Linux/Windows 一键本地部署脚本，完成路径初始化、依赖检查和服务启动准备。

### Modified Capabilities
- `engine-upgrade-management`: 升级任务执行上下文改为运行时解析结果，不再依赖容器特定目录假设；升级过程与状态采集在双模式下保持一致。

## Impact

- 受影响代码：
  - `scripts/agent_manager.sh`、`scripts/entrypoint.sh`、`scripts/upgrade_agents.sh`
  - `server/services/engine_upgrade_manager.py`
  - 新增/改造运行时路径解析与凭证导入模块
- 受影响文档：
  - 本地部署文档、容器化文档、Engine 管理相关文档
- 受影响测试：
  - Engine 升级相关单元测试
  - 脚本路径与运行时解析测试（含 Windows 路径分支）
