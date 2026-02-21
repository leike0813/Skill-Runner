# interactive-job-api Specification

## Purpose
TBD - created by archiving change interactive-00-api-mode-and-interaction-contract. Update Purpose after archive.
## Requirements
### Requirement: 系统 MUST 支持任务执行模式选择
系统 MUST 支持 `auto` 与 `interactive` 两种执行模式，并保持默认向后兼容。

#### Scenario: 未显式提供执行模式
- **WHEN** 客户端调用 `POST /v1/jobs` 且未提供 `execution_mode`
- **THEN** 系统按 `auto` 模式执行
- **AND** 现有接口行为不变

#### Scenario: 显式请求 interactive 模式
- **WHEN** 客户端调用 `POST /v1/jobs` 且 `execution_mode=interactive`
- **THEN** 系统接受请求并按交互模式编排

### Requirement: 系统 MUST 提供待决交互查询接口
系统 MUST 暴露待决交互查询接口，供调用方获取当前需要用户回答的问题。

#### Scenario: 存在待决问题
- **GIVEN** run 处于 `waiting_user`
- **WHEN** 客户端调用 `GET /v1/jobs/{request_id}/interaction/pending`
- **THEN** 返回 `pending` 对象（包含 `interaction_id` 与问题约束）

#### Scenario: 当前无待决问题
- **WHEN** 客户端调用 `GET /v1/jobs/{request_id}/interaction/pending`
- **THEN** 返回 `pending: null`
- **AND** 返回当前 run 状态

### Requirement: 系统 MUST 提供交互回复接口
系统 MUST 允许客户端提交用户答复并触发后续执行。

#### Scenario: 正常回复待决问题
- **GIVEN** run 处于 `waiting_user`
- **AND** 请求中的 `interaction_id` 与当前待决 id 一致
- **WHEN** 客户端调用 `POST /v1/jobs/{request_id}/interaction/reply`
- **THEN** 系统接受答复并触发恢复执行

#### Scenario: 提交过期或错误 interaction_id
- **WHEN** 客户端提交的 `interaction_id` 非当前待决 id
- **THEN** 系统返回 409 冲突错误
- **AND** 不改变当前待决状态

### Requirement: 系统 MUST 校验请求执行模式是否被 Skill 允许
系统 MUST 在 run 创建阶段校验 `execution_mode` 是否属于 Skill 声明的 `execution_modes`。

#### Scenario: 请求模式被 Skill 允许
- **GIVEN** Skill 声明 `execution_modes` 包含请求模式
- **WHEN** 客户端提交创建 run 请求
- **THEN** 系统接受请求并进入后续执行流程

#### Scenario: 请求模式不被 Skill 允许
- **GIVEN** Skill 声明 `execution_modes` 不包含请求模式
- **WHEN** 客户端提交创建 run 请求
- **THEN** 系统返回 `400`
- **AND** 错误码为 `SKILL_EXECUTION_MODE_UNSUPPORTED`

### Requirement: 系统 MUST 支持 interactive 严格回复开关
系统 MUST 提供 `interactive_require_user_reply` 开关控制交互回合是否必须等待用户回复。

#### Scenario: 未显式提供开关
- **WHEN** 客户端创建 interactive run 且未提供开关
- **THEN** 系统使用默认值 `interactive_require_user_reply=true`

#### Scenario: 显式关闭严格回复
- **WHEN** 客户端创建 interactive run 且 `interactive_require_user_reply=false`
- **THEN** 系统接受并按“允许超时自动决策”语义执行

### Requirement: reply 接口 MUST 支持自由文本回复
系统 MUST 允许客户端提交自由文本作为用户答复，不要求固定 JSON 回复结构。

#### Scenario: 提交自由文本回复
- **WHEN** 客户端调用 reply 接口提交文本答复
- **THEN** 系统接受该答复
- **AND** 不要求按 `kind` 提供固定字段对象

### Requirement: 系统 MUST 记录交互回复来源
系统 MUST 区分并持久化“用户回复”和“系统自动决策回复”。

#### Scenario: 用户主动回复
- **WHEN** 客户端调用 reply 接口提交合法回复
- **THEN** 交互历史记录 `resolution_mode=user_reply`

#### Scenario: 超时自动决策
- **WHEN** strict=false 且等待超过超时阈值
- **THEN** 系统生成自动回复并记录 `resolution_mode=auto_decide_timeout`

### Requirement: 系统 MUST 校验请求引擎是否被 Skill 允许
系统 MUST 在 run 创建阶段基于 Skill 的 `effective_engines` 校验请求引擎是否允许执行。

#### Scenario: 请求引擎在有效集合内
- **GIVEN** Skill 的 `effective_engines` 包含请求引擎
- **WHEN** 客户端提交创建 run 请求
- **THEN** 系统接受请求并进入后续执行流程

#### Scenario: 请求命中显式不支持引擎
- **GIVEN** Skill 在 `runner.json.unsupported_engines` 中声明了请求引擎
- **WHEN** 客户端提交创建 run 请求
- **THEN** 系统返回 `400`
- **AND** 错误码为 `SKILL_ENGINE_UNSUPPORTED`

#### Scenario: 请求引擎不在允许集合
- **GIVEN** Skill 显式声明 `runner.json.engines` 且请求引擎不在该集合（或被排除后不在 `effective_engines`）
- **WHEN** 客户端提交创建 run 请求
- **THEN** 系统返回 `400`
- **AND** 错误码为 `SKILL_ENGINE_UNSUPPORTED`

