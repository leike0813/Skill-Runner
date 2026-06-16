## MODIFIED Requirements

### Requirement: 系统 MUST 使用 Managed Prefix 管理 Engine CLI
系统 MUST 将 Agent CLI 的安装、升级、检测与调用绑定到受管前缀，避免依赖系统全局 `npm -g`。系统还 MUST 支持将受管插件 CLI 注册到同一 managed prefix bin，使 agent 子进程通过同一 PATH 解析规则调用。

#### Scenario: container mode does not require root-owned runtime paths
- **WHEN** 服务在容器模式下执行引擎检测、bootstrap 或运行时调用
- **THEN** 受管前缀与运行时目录 MUST 可由默认非 root 用户访问
- **AND** 系统 MUST 不要求 root 写入系统级 npm、agent home 或 data 路径

#### Scenario: managed plugin CLI is available on agent PATH
- **WHEN** managed layout/bootstrap installs a plugin CLI into `<SKILL_RUNNER_NPM_PREFIX>/bin`
- **THEN** agent subprocess environment MUST prepend the managed bin directory to PATH
- **AND** the plugin CLI MUST be invocable by command name without a run-local shim
