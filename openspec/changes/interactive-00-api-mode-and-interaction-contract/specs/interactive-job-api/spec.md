## ADDED Requirements

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
