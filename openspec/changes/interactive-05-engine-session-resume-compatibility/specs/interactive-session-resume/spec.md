## ADDED Requirements

### Requirement: 系统 MUST 基于恢复能力选择 interactive 执行档位
系统 MUST 在 interactive 执行前验证目标引擎的恢复能力，并选择 `resumable` 或 `sticky_process` 档位。

#### Scenario: 恢复能力探测通过
- **WHEN** 创建 interactive run 且目标引擎 probe 通过
- **THEN** 系统将 run 标记为 `interactive_profile.kind=resumable`
- **AND** run 允许在 `waiting_user` 后跨进程恢复

#### Scenario: 恢复能力探测失败
- **WHEN** 创建 interactive run 且目标引擎 probe 失败
- **THEN** 系统将 run 标记为 `interactive_profile.kind=sticky_process`
- **AND** 系统仍允许进入交互执行流程

### Requirement: resumable 档位 MUST 在 waiting_user 前持久化会话句柄
系统 MUST 在 `resumable` 档位进入 `waiting_user` 前保存引擎会话句柄。

#### Scenario: 持久化引擎会话句柄
- **GIVEN** run 为 `interactive_profile.kind=resumable`
- **WHEN** 运行回合产出 `ask_user`
- **THEN** 系统持久化 `EngineSessionHandle`
- **AND** 后续 resume 必须使用同一 handle

#### Scenario: Codex 从 `thread.started` 提取会话句柄
- **GIVEN** Codex 以 `exec --json` 运行
- **WHEN** 输出首条事件为 `{"type":"thread.started","thread_id":"<id>"}`
- **THEN** 系统将 `<id>` 持久化为 Codex 的 `EngineSessionHandle.handle_value`
- **AND** `handle_type` 为 `session_id`

#### Scenario: Gemini 从 JSON 返回提取会话句柄
- **GIVEN** Gemini 以 JSON 模式运行
- **WHEN** 首轮返回体包含 `"session_id":"<id>"`
- **THEN** 系统将 `<id>` 持久化为 Gemini 的 `EngineSessionHandle.handle_value`
- **AND** `handle_type` 为 `session_id`

#### Scenario: iFlow 从 `<Execution Info>` 提取会话句柄
- **GIVEN** iFlow 处于 resumable 档位并完成一轮执行
- **WHEN** `<Execution Info>` 包含 `"session-id":"<id>"`
- **THEN** 系统将 `<id>` 持久化为 iFlow 的 `EngineSessionHandle.handle_value`
- **AND** `handle_type` 为 `session_id`

### Requirement: resumable 档位 MUST 通过新进程恢复会话并继续执行
系统 MUST 在 `resumable` 档位收到 reply 后启动新进程，通过已持久化句柄恢复会话再继续执行。

#### Scenario: reply 后恢复执行
- **GIVEN** run 处于 `waiting_user` 且 `interactive_profile.kind=resumable`
- **AND** run 存在有效 session handle
- **WHEN** 客户端提交合法 reply
- **THEN** 系统启动新进程并执行 resume
- **AND** 运行进入下一回合

#### Scenario: Codex resume 参数顺序
- **GIVEN** 系统使用 Codex 恢复会话
- **WHEN** 构造 `codex exec resume` 命令
- **THEN** 系统将 `thread_id` 作为位置参数传入
- **AND** `thread_id` 出现在 prompt 参数之前
- **AND** 不使用命名参数传递 `thread_id`

#### Scenario: Gemini resume 参数传递
- **GIVEN** 系统使用 Gemini 恢复会话
- **WHEN** 构造 Gemini 恢复命令
- **THEN** 系统以 `--resume "<session_id>"` 传递会话凭证
- **AND** `session_id` 来自上一回合 JSON 返回体
- **AND** 不依赖 `--list-sessions` 的排序索引

#### Scenario: iFlow resume 参数传递
- **GIVEN** 系统以 iFlow resumable 档位恢复会话
- **WHEN** 构造 iFlow 恢复命令
- **THEN** 系统以 `--resume "<session-id>"` 传递会话凭证
- **AND** `session-id` 来自上一回合 `<Execution Info>`
- **AND** 不依赖交互式 session 选择器

### Requirement: sticky_process 档位 MUST 使用驻留进程并执行等待超时回收
系统 MUST 在 `sticky_process` 档位保持原进程驻留等待，并在超时后终止进程。

#### Scenario: sticky_process 等待用户回复
- **GIVEN** run 处于 `interactive_profile.kind=sticky_process`
- **WHEN** 回合产出 `ask_user`
- **THEN** 系统保持原执行进程驻留
- **AND** 系统按 `session_timeout_sec`（默认 1200 秒）写入 `wait_deadline_at`

#### Scenario: sticky_process 回复在时限内到达
- **GIVEN** run 处于 `waiting_user` 且 `interactive_profile.kind=sticky_process`
- **WHEN** 客户端在 `wait_deadline_at` 前提交合法 reply
- **THEN** 系统将 reply 路由到原进程继续执行

#### Scenario: sticky_process 超时
- **GIVEN** run 处于 `waiting_user` 且 `interactive_profile.kind=sticky_process`
- **WHEN** 到达基于 `session_timeout_sec`（默认 1200 秒）计算的 `wait_deadline_at` 且仍未收到 reply
- **THEN** 系统终止原进程
- **AND** run 进入 `failed`
- **AND** `error.code=INTERACTION_WAIT_TIMEOUT`

### Requirement: 失败路径 MUST 映射为确定性错误码
系统 MUST 在恢复失败或驻留进程异常时返回稳定错误码，避免不透明失败。

#### Scenario: 句柄失效或恢复命令失败
- **GIVEN** run 处于 `interactive_profile.kind=resumable`
- **WHEN** resume 执行失败
- **THEN** run 进入 `failed`
- **AND** `error.code=SESSION_RESUME_FAILED`

#### Scenario: Codex 缺失 thread_id
- **WHEN** Codex 回合输出缺少可提取的 `thread.started.thread_id`
- **THEN** 系统不得进入 `waiting_user`
- **AND** run 进入 `failed`
- **AND** `error.code=SESSION_RESUME_FAILED`

#### Scenario: Gemini 缺失 session_id
- **WHEN** Gemini 回合 JSON 返回缺少可提取的 `session_id`
- **THEN** 系统不得进入 `waiting_user`
- **AND** run 进入 `failed`
- **AND** `error.code=SESSION_RESUME_FAILED`

#### Scenario: iFlow 缺失 session-id
- **GIVEN** run 处于 iFlow resumable 档位
- **WHEN** iFlow 回合 `<Execution Info>` 缺少可提取的 `session-id`
- **THEN** 系统不得进入 `waiting_user`
- **AND** run 进入 `failed`
- **AND** `error.code=SESSION_RESUME_FAILED`

#### Scenario: sticky_process 等待期间进程丢失
- **GIVEN** run 处于 `waiting_user` 且 `interactive_profile.kind=sticky_process`
- **WHEN** 系统检测到驻留进程已退出
- **THEN** run 进入 `failed`
- **AND** `error.code=INTERACTION_PROCESS_LOST`
