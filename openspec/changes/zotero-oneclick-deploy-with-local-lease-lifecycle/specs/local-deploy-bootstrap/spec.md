## MODIFIED Requirements

### Requirement: 系统 MUST 提供本地一键部署脚本
系统 MUST 保留 `deploy_local.sh/.ps1` 作为本地部署底层入口，但插件集成 SHOULD 调用稳定控制命令而非直接耦合脚本。

#### Scenario: deploy script binds localhost by default
- **WHEN** 用户执行本地部署脚本
- **THEN** 服务默认绑定 `127.0.0.1`
- **AND** 可通过环境变量显式覆盖

#### Scenario: optional ttyd dependency does not block core service startup
- **WHEN** 运行环境缺失 `ttyd`
- **THEN** 脚本输出可操作提示
- **AND** 核心 API 服务仍可启动

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
