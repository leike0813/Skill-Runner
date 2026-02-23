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
The pending payload minimum viability MUST be guaranteed by backend-owned generation and MUST NOT depend on agent-structured ask_user output.

#### Scenario: waiting_user 下总能返回可回复 pending
- **GIVEN** run 状态为 `waiting_user`
- **WHEN** 客户端调用 pending 接口
- **THEN** 返回可用于 reply 的 `interaction_id` 与 `prompt`
- **AND** 其来源可以是后端基线生成，而非 ask_user 原样透传

### Requirement: 系统 MUST 提供交互回复接口
The reply protocol MUST remain `interaction_id + response` driven and MUST NOT introduce semantic coupling to `kind`.

#### Scenario: kind 仅兼容展示
- **WHEN** pending 载荷包含 `kind`
- **THEN** 客户端可用于展示
- **AND** 后端不依赖该字段做语义理解或强约束验证

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

### Requirement: waiting_user 进入条件 MUST 独立于 ask_user 结构体
系统 MUST 允许在缺少或损坏 ask_user 结构时，仍通过 interactive gate 进入等待态。

#### Scenario: 缺失 ask_user 仍可等待用户
- **GIVEN** run 处于 `interactive` 模式
- **WHEN** 当前回合未检测到 done marker
- **THEN** run 可进入 `waiting_user`
- **AND** pending/reply 闭环保持可用

### Requirement: API 状态与诊断 MUST 反映双轨完成与回合上限策略
系统 MUST 向客户端公开稳定、可消费的完成告警与失败原因。

#### Scenario: 软条件完成返回稳定 warning
- **WHEN** interactive 回合未检测到 done marker 但输出通过 schema 校验并完成
- **THEN** API 响应中的诊断/告警包含 `INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER`

#### Scenario: 超轮次失败返回稳定错误码
- **WHEN** interactive 回合达到 `max_attempt` 且本回合无完成证据
- **THEN** API 返回 `failed`
- **AND** 失败原因包含 `INTERACTIVE_MAX_ATTEMPT_EXCEEDED`

