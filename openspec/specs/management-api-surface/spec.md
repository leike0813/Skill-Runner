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

