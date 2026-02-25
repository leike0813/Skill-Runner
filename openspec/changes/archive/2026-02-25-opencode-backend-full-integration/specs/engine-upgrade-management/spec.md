## ADDED Requirements

### Requirement: 系统 MUST 将 opencode 纳入受管引擎安装与升级流程
系统 MUST 将 `opencode` 作为受管引擎的一部分，纳入安装检测、版本检测与升级任务调度路径。

#### Scenario: 单引擎升级 opencode
- **WHEN** 客户端创建升级任务并指定 `mode=single` 且 `engine=opencode`
- **THEN** 系统接受请求并调度 opencode 升级子任务
- **AND** 升级结果包含该引擎的 stdout/stderr 诊断输出

#### Scenario: 全量升级包含 opencode
- **WHEN** 客户端创建 `mode=all` 升级任务
- **THEN** 系统按受管引擎列表执行升级
- **AND** 列表中包含 `opencode`

### Requirement: opencode 模型管理 MUST 采用动态探测缓存而非手工快照写入
系统 MUST 将 opencode 模型治理收敛到动态探测缓存路径，不通过手工 snapshot 写入维护模型列表。

#### Scenario: 查询 opencode manifest 兼容视图
- **WHEN** 客户端请求 `GET /v1/engines/opencode/models/manifest`
- **THEN** 系统返回基于动态缓存的兼容视图
- **AND** 包含最近刷新状态与可用模型列表

#### Scenario: opencode snapshots 写入被拒绝
- **WHEN** 客户端请求 `POST /v1/engines/opencode/models/snapshots`
- **THEN** 系统返回不支持手工快照写入的明确错误
