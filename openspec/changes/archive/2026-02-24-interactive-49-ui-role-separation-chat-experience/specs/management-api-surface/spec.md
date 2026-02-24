## MODIFIED Requirements

### Requirement: Run 管理 MUST 支持审计导向协议历史读取
系统 MUST 提供按协议流读取 run 历史事件的管理接口，用于前端审计与排障。

#### Scenario: 按协议流读取历史
- **WHEN** 客户端调用 `GET /v1/management/runs/{request_id}/protocol/history?stream=fcmp|rasp|orchestrator`
- **THEN** 响应包含 `request_id`、`stream`、`count`、`events`
- **AND** `events` 仅返回对应协议流的数据

#### Scenario: 历史过滤参数
- **WHEN** 客户端提供 `from_seq/to_seq/from_ts/to_ts`
- **THEN** 接口按过滤条件返回事件子集

#### Scenario: 非法 stream 参数
- **WHEN** `stream` 不在 `fcmp|rasp|orchestrator`
- **THEN** 接口返回 `400`

### Requirement: 管理 API Run 详情动作 MUST 支持运维控制但不内置用户回复
管理 API 对应 UI 能力 MUST 保持运维导向，不要求在管理详情页内嵌 reply 交互。

#### Scenario: waiting_user 运维观测
- **WHEN** run 状态为 `waiting_user`
- **THEN** 管理 API 继续提供状态、pending、事件流与 cancel 能力
- **AND** 管理详情页可仅消费观测接口进行展示
