## ADDED Requirements

### Requirement: FCMP event surface remains stable without assistant turn markers
FCMP 对外事件集合 MUST 保持稳定，不新增 `assistant.turn_*` 事件类型。

#### Scenario: rasp turn markers present
- **GIVEN** RASP 流中存在 `agent.turn_start` / `agent.turn_complete`
- **WHEN** 系统映射并发布 FCMP 事件
- **THEN** FCMP MUST NOT 发布任何 `assistant.turn_*` 事件
- **AND** 现有 `assistant.reasoning/tool_call/command_execution/promoted/final` 语义保持不变

### Requirement: Session handle persistence SHOULD prefer live run-handle events
运行链路在具备事件化 run-handle 时 MUST 优先即时持久化，不依赖 waiting 阶段的延迟提取。

#### Scenario: eventized engine publishes run handle during running
- **GIVEN** 运行中的 attempt 发布 `lifecycle.run_handle`
- **WHEN** run lifecycle 消费该事件
- **THEN** 系统 MUST 立即持久化 engine session handle
- **AND** 后续 resume 读取 SHOULD 可直接获取该 handle

#### Scenario: non-eventized engine fallback remains available
- **GIVEN** 引擎当前不发布 `lifecycle.run_handle`
- **WHEN** run 进入 waiting interaction 持久化阶段
- **THEN** 系统 MAY 使用 `extract_session_handle(...)` 回退提取
- **AND** 回退路径 MUST 保持向后兼容
