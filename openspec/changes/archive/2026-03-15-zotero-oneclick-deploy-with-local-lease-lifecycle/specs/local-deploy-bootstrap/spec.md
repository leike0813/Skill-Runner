## MODIFIED Requirements

### Requirement: 系统 MUST 提供本地一键部署脚本
系统 MUST 保留 `deploy_local.sh/.ps1` 作为本地部署底层入口，但插件集成 SHOULD 调用稳定控制命令而非直接耦合脚本。

#### Scenario: Linux/macOS 一键部署
- **WHEN** 用户执行 `scripts/deploy_local.sh`
- **THEN** 脚本完成必要路径初始化与前置检查
- **AND** 输出明确的后续启动信息

#### Scenario: Windows 一键部署
- **WHEN** 用户执行 `scripts/deploy_local.ps1`
- **THEN** 脚本完成 Windows 本地路径初始化与前置检查
- **AND** 输出明确的后续启动信息

#### Scenario: local deploy binds loopback by default
- **WHEN** 用户执行本地部署脚本
- **THEN** 服务默认绑定 `127.0.0.1`
- **AND** 可通过环境变量显式覆盖 bind host

#### Scenario: optional ttyd dependency does not block core service startup
- **WHEN** 运行环境缺失 `ttyd`
- **THEN** 脚本输出可操作提示
- **AND** 核心 API 服务仍可启动
- 
#### Scenario: supported scripts remain in scripts directory
- **WHEN** 用户查看项目根目录 `scripts/`
- **THEN** 其中仅包含当前正式支持的部署/启动/运维入口
- **AND** 历史兼容或一次性脚本不再与正式入口混放

#### Scenario: deprecated or forensic scripts are relocated
- **WHEN** 用户需要访问历史兼容或排障脚本
- **THEN** 可以分别在 `deprecated/scripts/` 或 `artifacts/scripts/` 找到
- **AND** README 与容器化文档不会再把它们列为正式入口

## ADDED Requirements

### Requirement: 系统 MUST 提供插件友好的宿主机控制入口
系统 MUST 提供稳定的宿主机控制命令用于插件调用，覆盖 install/up/down/status/doctor。

#### Scenario: plugin calls control CLI for local lifecycle
- **WHEN** 插件调用 `skill-runnerctl up --mode local`
- **THEN** 系统启动本地服务并返回机器可读状态
- **AND** 插件可通过 `status/down` 完成生命周期控制

### Requirement: 系统 MUST 提供 release 固定版本安装器并校验完整性
系统 MUST 提供跨平台安装器脚本并对下载资产执行 SHA256 校验。

#### Scenario: installer rejects checksum mismatch
- **WHEN** 下载资产哈希与发布校验值不一致
- **THEN** 安装器拒绝继续执行
- **AND** 返回明确错误信息

#### Scenario: tag release publishes installer source package assets
- **WHEN** CI 处理 `v*` tag 发布
- **THEN** Release 资产包含 `skill-runner-<version>.tar.gz` 与对应 `.sha256`
- **AND** 该源码包包含 `skills/*` 子模块内容