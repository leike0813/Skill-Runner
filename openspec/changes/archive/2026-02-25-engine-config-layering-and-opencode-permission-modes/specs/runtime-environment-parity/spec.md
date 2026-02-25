## MODIFIED Requirements

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
