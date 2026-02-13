## ADDED Requirements

### Requirement: 系统 MUST 提供本地一键部署脚本
系统 MUST 提供 Linux/macOS 与 Windows 两套本地一键部署脚本，完成基础目录初始化与服务启动准备。

#### Scenario: Linux/macOS 一键部署
- **WHEN** 用户执行 `scripts/deploy_local.sh`
- **THEN** 脚本完成必要路径初始化与前置检查
- **AND** 输出明确的后续启动信息

#### Scenario: Windows 一键部署
- **WHEN** 用户执行 `scripts/deploy_local.ps1`
- **THEN** 脚本完成 Windows 本地路径初始化与前置检查
- **AND** 输出明确的后续启动信息

### Requirement: 部署脚本 MUST 统一使用运行时解析规则
部署脚本 MUST 与服务端运行时解析逻辑一致，避免脚本初始化路径与服务实际读取路径不一致。

#### Scenario: 脚本初始化后服务可直接读取
- **WHEN** 一键部署脚本执行完成
- **THEN** 服务启动后读取同一组 data/cache/agent_home 路径
- **AND** 不出现模式错配导致的权限错误

### Requirement: 部署脚本 MUST 输出可诊断错误
部署脚本 MUST 在依赖缺失或权限不足时输出可执行的修复指引。

#### Scenario: 缺少 Node/npm
- **WHEN** 运行环境缺少 Node 或 npm
- **THEN** 脚本停止并输出安装指引
- **AND** 不进入半初始化状态
