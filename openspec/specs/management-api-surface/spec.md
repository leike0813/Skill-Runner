# management-api-surface Specification

## Purpose
TBD - created by archiving change interactive-27-unified-management-api-surface. Update Purpose after archive.
## Requirements
### Requirement: 系统 MUST 提供统一管理 API 面
系统 MUST 提供前端无关的管理 API，覆盖 Skill 管理、Engine 管理、Run 管理三类资源。

#### Scenario: 管理 API 资源分组
- **WHEN** 客户端查询管理能力
- **THEN** 可在统一命名空间访问 Skill / Engine / Run 管理资源
- **AND** 返回稳定 JSON 字段，不依赖 HTML 结构

### Requirement: Run 管理 MUST 支持对话窗口所需动作
系统 MUST 提供 Run 对话窗口最小动作集合：状态、文件浏览、实时输出、交互回复。

#### Scenario: 查询 Run 会话状态
- **WHEN** 客户端调用 Run 管理状态接口
- **THEN** 响应包含 `status`
- **AND** 包含 `pending_interaction_id`（可空）
- **AND** 包含交互计数字段（如 `interaction_count`）

#### Scenario: 读取 Run 文件树与预览
- **WHEN** 客户端请求 Run 文件树与文件预览
- **THEN** 系统返回可用于对话窗口侧边栏展示的结构化数据
- **AND** 路径越界请求被拒绝

#### Scenario: 消费 Run 实时输出
- **WHEN** 客户端连接 Run 管理实时输出接口
- **THEN** 系统提供 stdout/stderr 增量事件流
- **AND** 支持断线后续传

#### Scenario: 处理 pending/reply
- **WHEN** Run 进入 `waiting_user`
- **THEN** 客户端可通过管理 API 获取 pending 内容并提交 reply
- **AND** 回复后 Run 可继续推进到下一状态

#### Scenario: 主动终止 Run
- **WHEN** 客户端调用 Run 管理取消动作
- **THEN** 系统执行与执行域一致的 cancel 语义
- **AND** 对活跃 run 返回可观测终态（`canceled`）
- **AND** 对终态 run 保持幂等响应

### Requirement: Skill 管理 MUST 暴露可用于动态表单构建的 schema 内容
系统 MUST 提供 management API 能力，让客户端可读取某个 Skill 的 input/parameter/output schema 内容，以支持动态执行表单和前置校验。

#### Scenario: 读取 Skill schema 集合
- **WHEN** 客户端请求指定 Skill 的 schema 信息
- **THEN** 系统返回该 Skill 的 input/parameter/output schema 内容（若存在）
- **AND** 响应结构可被前端直接用于动态表单渲染与校验

#### Scenario: Skill 不存在
- **WHEN** 客户端请求不存在的 skill_id 的 schema 信息
- **THEN** 系统返回 `404`
- **AND** 不暴露文件系统内部路径细节

### Requirement: Skill 管理接口 MUST 返回可枚举的有效引擎集合
系统 MUST 在 Skill 管理相关接口中返回可供前端直接枚举的 `effective_engines`，并保留声明字段用于解释来源。

#### Scenario: 显式 allow-list 与 deny-list
- **WHEN** Skill 同时声明 `engines` 与 `unsupported_engines`
- **THEN** 管理接口返回计算后的 `effective_engines`
- **AND** 返回原始声明字段（`engines`、`unsupported_engines`）供前端展示

#### Scenario: 缺失 engines 的默认枚举
- **WHEN** Skill 未声明 `engines`
- **THEN** 管理接口将系统支持引擎减去 `unsupported_engines` 后作为 `effective_engines` 返回
- **AND** 前端无需自行推断默认引擎集合

### Requirement: Run 管理 MUST 支持协议审计历史读取
系统 MUST 提供可按协议流查询 run 历史事件的管理接口，支持审计和排障场景。

#### Scenario: 读取协议历史
- **WHEN** 客户端调用 `GET /v1/management/runs/{request_id}/protocol/history`
- **AND** 提供 `stream=fcmp|rasp|orchestrator`
- **THEN** 响应包含 `request_id`、`stream`、`attempt`、`available_attempts`、`count`、`events`
- **AND** `events` 仅包含对应协议流记录

#### Scenario: 应用历史过滤参数
- **WHEN** 客户端提供 `from_seq/to_seq/from_ts/to_ts`
- **THEN** 接口按过滤条件返回事件子集

#### Scenario: 按 attempt 切换审计历史
- **WHEN** 客户端调用 `GET /v1/management/runs/{request_id}/protocol/history` 并提供 `attempt`
- **THEN** 系统返回该轮次事件
- **AND** 返回 `available_attempts` 供前端翻页
- **AND** 对 `stream=fcmp`，`events[].seq` 使用全局序号，attempt 本地序号位于 `events[].meta.local_seq`
- **AND** 对 `stream=rasp|orchestrator`，`events[].seq` 仍表示该 attempt 内本地序号

#### Scenario: orchestrator 旧数据缺失 seq 仍可读取
- **WHEN** 旧审计文件中的 orchestrator 事件缺失 `seq`
- **THEN** 系统按文件顺序回填序号后返回
- **AND** 不因缺失 `seq` 导致事件被静默过滤

#### Scenario: 非法 stream 参数被拒绝
- **WHEN** `stream` 参数不在 `fcmp|rasp|orchestrator` 中
- **THEN** 接口返回 `400`

### Requirement: 管理日志区间读取 MUST 支持按 attempt 定位
系统 MUST 在 `GET /v1/management/runs/{request_id}/logs/range` 支持 `attempt` 参数，以保障 raw_ref 回跳和轮次审计一致。

#### Scenario: 指定 attempt 读取日志片段
- **WHEN** 客户端调用 `logs/range` 并提供 `attempt`
- **THEN** 系统从 `.audit/*.{attempt}.log` 读取并返回区间内容

### Requirement: Engine 模型接口 MUST 支持 provider 维度元数据并保持兼容
系统 MUST 在现有模型列表接口中提供 provider 维度元数据，同时保持 `models[].id` 的既有语义与兼容性。

#### Scenario: opencode 模型列表返回 provider/model
- **WHEN** 客户端请求 `GET /v1/engines/opencode/models`
- **THEN** 返回的模型项中 `id` 保持 `provider/model`
- **AND** 每个模型项额外包含 `provider` 与 `model` 字段

#### Scenario: 非 opencode 引擎兼容
- **WHEN** 客户端请求其他引擎模型列表
- **THEN** 原有字段语义保持不变
- **AND** 旧客户端仅读取 `models[].id` 不受影响

