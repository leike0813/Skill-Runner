## ADDED Requirements

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
