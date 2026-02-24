# interactive-session-resume Specification

## Purpose
定义 interactive 会话在单一可恢复范式下的句柄提取、持久化与恢复语义。

## Requirements
### Requirement: 系统 MUST 使用单一可恢复会话配置
系统 MUST 在 interactive 执行前完成恢复能力探测，并收敛到单一可恢复配置，不再暴露双档位分支。

#### Scenario: probe 通过
- **WHEN** 创建 interactive run 且引擎恢复能力 probe 通过
- **THEN** 系统记录可恢复会话配置
- **AND** 后续等待/恢复统一走会话句柄路径

#### Scenario: probe 失败
- **WHEN** 创建 interactive run 且引擎恢复能力 probe 失败
- **THEN** 系统仍记录可恢复会话配置并允许 interactive 执行
- **AND** 不再切换到 sticky 专属流程

### Requirement: waiting_user 前 MUST 持久化会话句柄
系统 MUST 在进入 `waiting_user` 前保存 `EngineSessionHandle`。

#### Scenario: Codex 提取会话句柄
- **GIVEN** Codex 以 `exec --json` 运行
- **WHEN** 输出首条事件为 `{"type":"thread.started","thread_id":"<id>"}`
- **THEN** 系统将 `<id>` 持久化为 `EngineSessionHandle.handle_value`
- **AND** `handle_type=session_id`

#### Scenario: Gemini 提取会话句柄
- **GIVEN** Gemini 以 JSON 模式运行
- **WHEN** 返回体包含 `"session_id":"<id>"`
- **THEN** 系统将 `<id>` 持久化为 `EngineSessionHandle.handle_value`
- **AND** `handle_type=session_id`

#### Scenario: iFlow 提取会话句柄
- **GIVEN** iFlow 完成一轮执行
- **WHEN** `<Execution Info>` 包含 `"session-id":"<id>"`
- **THEN** 系统将 `<id>` 持久化为 `EngineSessionHandle.handle_value`
- **AND** `handle_type=session_id`

### Requirement: reply 后 MUST 通过统一 resume 路径继续执行
系统 MUST 在收到 reply 后统一切换到 `queued` 并调度下一回合恢复执行。

#### Scenario: reply 恢复执行
- **GIVEN** run 处于 `waiting_user`
- **AND** run 持久化了有效 session handle
- **WHEN** 客户端提交合法 reply
- **THEN** 系统更新 run 为 `queued`
- **AND** 由调度器恢复下一回合执行

### Requirement: 恢复失败 MUST 返回稳定错误码
系统 MUST 在句柄缺失或恢复失败时返回 `SESSION_RESUME_FAILED`。

#### Scenario: 缺失句柄
- **WHEN** interactive 回合需要恢复但找不到有效 session handle
- **THEN** run 进入 `failed`
- **AND** `error.code=SESSION_RESUME_FAILED`
