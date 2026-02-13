# runtime-environment-parity Specification

## Purpose
TBD - created by archiving change runtime-parity-local-container. Update Purpose after archive.
## Requirements
### Requirement: 系统 MUST 统一解析运行时配置
系统 MUST 通过统一解析逻辑确定运行模式、平台和默认路径，供服务与脚本共同使用。

#### Scenario: 自动识别容器模式
- **WHEN** 服务运行在容器环境
- **THEN** 解析结果为 `runtime_mode=container`
- **AND** 导出容器默认目录集合

#### Scenario: 自动识别本地 Windows 模式
- **WHEN** 服务运行在 Windows 本地环境
- **THEN** 解析结果为 `runtime_mode=local` 且 `platform=windows`
- **AND** 使用 Windows 本地默认路径

### Requirement: 系统 MUST 使用 Managed Prefix 管理 Engine CLI
系统 MUST 将 Agent CLI 的安装、升级、检测与调用绑定到受管前缀，避免依赖系统全局 `npm -g`。

#### Scenario: 本地模式升级不需要写系统目录
- **WHEN** 服务执行引擎升级
- **THEN** 升级命令使用受管前缀路径
- **AND** 不要求 sudo/root 写权限到系统级 npm 目录

### Requirement: 系统 MUST 隔离 Agent 配置目录
系统 MUST 默认使用独立的 Agent Home，避免与宿主用户默认 CLI 配置互相影响。

#### Scenario: 启动后读取隔离配置
- **WHEN** 服务启动并执行任意引擎调用
- **THEN** 引擎进程读取隔离 Agent Home 下的配置
- **AND** 不自动读取宿主 `~/.codex`、`~/.gemini`、`~/.iflow`

### Requirement: 系统 MUST 仅支持凭证白名单导入
系统 MUST 提供“仅导入鉴权凭证”机制，且不得导入 settings 等非认证配置。

#### Scenario: 导入凭证成功
- **WHEN** 运维执行凭证导入并提供合法来源目录
- **THEN** 仅复制白名单认证文件
- **AND** 目标目录的 settings 文件保持不变

#### Scenario: 非白名单文件被忽略
- **WHEN** 来源目录包含 `settings.json` 或其他非白名单文件
- **THEN** 系统不导入这些文件
- **AND** 记录可追踪日志

