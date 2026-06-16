## MODIFIED Requirements

### Requirement: 部署脚本 MUST 统一使用运行时解析规则
部署脚本 MUST 与服务端运行时解析逻辑一致，避免脚本初始化路径与服务实际读取路径不一致。部署/bootstrap 还 MUST 让 managed plugin CLI 使用同一 agent cache、agent home 与 managed prefix。

#### Scenario: 脚本初始化后服务可直接读取
- **WHEN** 一键部署脚本执行完成
- **THEN** 服务启动后读取同一组 data/cache/agent_home 路径
- **AND** 不出现模式错配导致的权限错误

#### Scenario: Zotero Bridge uses the deployment managed prefix
- **WHEN** 本地或 Docker bootstrap 初始化 managed layout
- **THEN** Zotero Bridge CLI 被安装到当前 `SKILL_RUNNER_NPM_PREFIX` 对应的 bin 目录
- **AND** wrapper skill 被安装到当前 `SKILL_RUNNER_AGENT_HOME` 下的各 agent 全局 skill 目录
- **AND** managed profile 被安装到当前 `SKILL_RUNNER_AGENT_CACHE_DIR`
