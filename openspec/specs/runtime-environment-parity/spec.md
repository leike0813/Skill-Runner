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

#### Scenario: 引擎默认配置资产可预测
- **WHEN** 系统在本地或容器模式启动并准备运行环境
- **THEN** 四引擎 `engine_default` 配置文件来源路径 MUST 固定在 `server/assets/configs/<engine>/default.*`
- **AND** 运行时行为在本地与容器模式保持一致

### Requirement: 系统 MUST 仅支持凭证白名单导入
系统 MUST 提供“仅导入鉴权凭证”机制，且不得导入 settings 等非认证配置。

#### Scenario: bootstrap 与运行时分层并存
- **WHEN** 凭证导入或 bootstrap 完成后发起执行
- **THEN** 认证相关初始化仍按既有 bootstrap 路径生效
- **AND** 运行时配置组装另行使用 `engine_default/skill/runtime/enforced` 分层
- **AND** 两者语义 MUST 明确分离且互不替代

### Requirement: 运行时环境 MUST 映射 XDG 目录到受管 agent_home
系统 MUST 在受管运行时中设置 XDG 目录环境变量，使 OpenCode 的配置与鉴权路径可预测并与容器挂载策略一致。

#### Scenario: 注入 XDG 路径
- **WHEN** 服务为引擎 CLI 构建子进程环境
- **THEN** 环境中包含：
  - `XDG_CONFIG_HOME=<agent_home>/.config`
  - `XDG_DATA_HOME=<agent_home>/.local/share`
  - `XDG_STATE_HOME=<agent_home>/.local/state`
  - `XDG_CACHE_HOME=<agent_home>/.cache`

### Requirement: 系统 MUST 支持 opencode 鉴权文件手工复制导入
系统 MUST 支持通过挂载目录手工复制 opencode 鉴权文件并导入受管路径。

#### Scenario: 导入 auth.json
- **WHEN** 用户将 `agent_config/opencode/auth.json` 放入导入源并执行导入
- **THEN** 文件被复制到 `<agent_home>/.local/share/opencode/auth.json`

#### Scenario: 导入 antigravity 账户文件
- **WHEN** 用户将 `agent_config/opencode/antigravity-accounts.json` 放入导入源并执行导入
- **THEN** 文件被复制到 `<agent_home>/.config/opencode/antigravity-accounts.json`

