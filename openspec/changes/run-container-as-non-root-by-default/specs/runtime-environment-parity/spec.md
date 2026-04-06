## MODIFIED Requirements

### Requirement: 系统 MUST 统一解析运行时配置
系统 MUST 通过统一解析逻辑确定运行模式、平台和默认路径，供服务与脚本共同使用。

#### Scenario: container runtime defaults do not assume root execution
- **WHEN** 服务运行在容器环境
- **THEN** 解析与部署默认值 MUST 兼容非 root 容器用户
- **AND** 受支持的默认容器姿态 MUST 不依赖 root/sudo 身份

### Requirement: 系统 MUST 使用 Managed Prefix 管理 Engine CLI
系统 MUST 将 Agent CLI 的安装、升级、检测与调用绑定到受管前缀，避免依赖系统全局 `npm -g`。

#### Scenario: container mode does not require root-owned runtime paths
- **WHEN** 服务在容器模式下执行引擎检测、bootstrap 或运行时调用
- **THEN** 受管前缀与运行时目录 MUST 可由默认非 root 用户访问
- **AND** 系统 MUST 不要求 root 写入系统级 npm、agent home 或 data 路径
