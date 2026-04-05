# interactive-run-observability Specification

## Purpose
定义 waiting_user 的可观测状态暴露和日志轮询建议区分策略。
## Requirements
### Requirement: 系统 MUST 暴露 waiting_user 的可观测状态
系统 MUST 在状态接口中明确体现 run 是否处于等待用户输入阶段。

#### Scenario: 查询 waiting_user 状态
- **GIVEN** run 当前在等待用户输入
- **WHEN** 客户端调用 `GET /v1/jobs/{request_id}`
- **THEN** 响应 `status=waiting_user`
- **AND** 包含当前待决交互标识（如 `pending_interaction_id`）

### Requirement: 日志轮询建议 MUST 区分 waiting_user 与 running
系统 MUST 在等待用户阶段关闭“继续轮询日志”的建议标志。

#### Scenario: waiting_user 的日志 tail
- **WHEN** 客户端调用 logs tail 接口且 run 状态为 `waiting_user`
- **THEN** 响应中的 `poll`/`poll_logs` 为 `false`

#### Scenario: running 的日志 tail
- **WHEN** run 状态为 `running`
- **THEN** 响应中的 `poll`/`poll_logs` 为 `true`

### Requirement: 文档 MUST 定义交互模式 API 时序
系统文档 MUST 提供 interactive 模式的 API 时序和错误处理建议。

#### Scenario: 文档覆盖 pending/reply 流程
- **WHEN** 开发者查阅 API 文档
- **THEN** 可获得 create -> pending -> reply -> resume -> terminal 的完整流程
- **AND** 文档明确说明本阶段仅支持 API 交互，不提供 UI 交互入口

### Requirement: 运行时观测协议层 MUST 通过 Adapter 提供引擎解析结果
系统 MUST 在构建 RASP/FCMP 事件时通过对应引擎 Adapter 获取 runtime 解析结果，而不是在通用协议层维护引擎分支解析逻辑。

#### Scenario: 观测服务构建事件时委托 Adapter 解析
- **WHEN** 观测服务为某 run attempt 构建 RASP 事件
- **THEN** 系统调用对应引擎 Adapter 的 runtime 解析接口获取标准解析结构

### Requirement: 通用协议层 MUST 保持引擎无关
系统 MUST 使通用协议层仅负责事件组装、通用去重和度量计算，不包含 codex/gemini/iflow/opencode 的专用解析分支。

#### Scenario: 协议层无引擎解析分支
- **WHEN** 审查通用协议层实现
- **THEN** 不存在按引擎名称分支的专用解析函数实现

### Requirement: 观测层落盘 MUST 进行协议 Schema 校验
系统 MUST 在写入 `events.jsonl` 与 `fcmp_events.jsonl` 前执行 schema 校验。

#### Scenario: FCMP 落盘校验
- **WHEN** 观测层写入 FCMP 事件
- **THEN** 每条事件通过 `fcmp_event_envelope` 校验

### Requirement: 历史读取 MUST 采用“读兼容”策略
系统 MUST 在读取历史时过滤旧不合规行并记录诊断日志。

#### Scenario: 旧历史兼容
- **WHEN** 历史文件中存在不合规行
- **THEN** 该行被跳过
- **AND** 合规行继续对外返回

### Requirement: Gemini parser MUST prefer batch JSON parse for runtime streams
Gemini runtime parser MUST 先尝试将当前 stdout/stderr 批次作为整段 JSON 解析，再回退到行级/fenced JSON 路径。

#### Scenario: stdout batch JSON detected
- **WHEN** stdout 包含可解析 JSON 文档
- **THEN** parser MUST 提取 `session_id` 与 `response`（若存在）
- **AND** parser MUST 产出结构化 payload 供 RASP `parsed.json` 事件使用

### Requirement: Gemini raw rows MUST be coalesced before RASP emission
Gemini parser 输出的 raw 行 MUST 在进入 RASP 构建前执行归并，避免逐行爆炸。

#### Scenario: large stderr burst
- **GIVEN** Gemini stderr 在单次 attempt 中产生大量连续文本行
- **WHEN** parser 输出 raw 行
- **THEN** raw 行 MUST 被归并为有限数量的块
- **AND** 行归并后的上下文顺序 MUST 保持稳定

### Requirement: FCMP/RASP protocol history MUST NOT trigger query-time rematerialization
`protocol/history` 的 FCMP/RASP 查询 MUST 不再在查询路径重建并覆盖审计事件文件。

#### Scenario: fetch protocol history for running run
- **GIVEN** run 正在运行
- **WHEN** 客户端请求 `protocol/history`（`stream=fcmp|rasp`）
- **THEN** 服务 MUST 仅消费 live journal 与已有 audit 镜像
- **AND** MUST NOT 在该查询路径调用 stdout/stderr 重算写盘。

### Requirement: terminal FCMP/RASP history MUST flush mirror before audit-only read
run 进入 terminal 后，服务 MUST 在读取 audit-only 历史前完成 live mirror drain。

#### Scenario: terminal transition with pending mirror writes
- **GIVEN** run 已进入 terminal，且镜像落盘任务仍在进行
- **WHEN** 客户端请求 `protocol/history`（`stream=fcmp|rasp`）
- **THEN** 服务 MUST 先等待 mirror flush 完成
- **AND** 再返回 audit-only 结果。

### Requirement: RASP raw rows MUST be coalesced for high-volume stderr bursts
在高频错误输出场景中，RASP raw 行 MUST 进行分块归并以降低事件数量与聚合成本。

#### Scenario: repeated stderr stack traces
- **GIVEN** 同 attempt 的 stderr 连续输出大量行
- **WHEN** 生成 RASP 事件
- **THEN** 服务端 MUST 将连续行归并为有限数量 `raw.stderr` 事件块
- **AND** 事件顺序 MUST 保持稳定

### Requirement: timeline aggregation MUST reuse cache when audit files are unchanged
`timeline/history` MUST 在审计文件未变更时复用已聚合结果，避免重复全量解析与排序。

#### Scenario: repeated polling without file changes
- **WHEN** 客户端在短周期内重复调用 `timeline/history`
- **AND** run 审计文件签名未变化
- **THEN** 服务端 MUST 复用缓存聚合结果

### Requirement: terminal protocol history MUST converge to audit-only source
在 run 进入 terminal 后，RASP/FCMP 历史查询 MUST 以审计文件为唯一来源，避免 live 增量残留造成终态漂移。

#### Scenario: terminal run protocol history
- **GIVEN** run 状态已是 `succeeded|failed|canceled`
- **WHEN** 客户端查询 `protocol/history`（`stream=rasp|fcmp`）
- **THEN** 返回 MUST NOT 混合 live journal 事件
- **AND** `source` MUST 为 `audit`

### Requirement: Protocol rebuild MUST be manual-only operation
协议重构 MUST 仅由人工触发，不得在页面访问或常规历史查询时自动执行。

#### Scenario: regular run detail load
- **WHEN** 用户仅打开 run detail 页面并读取协议历史
- **THEN** 系统 MUST 直接回放现有审计文件
- **AND** MUST NOT 自动触发重构

### Requirement: Rebuild engine MUST run in strict replay single-path
手动重构时，系统 MUST 仅按 strict replay 单路径执行，不允许 best-effort 回退路径。

#### Scenario: strict replay evidence complete
- **WHEN** attempt 存在有效 `io_chunks.<N>.jsonl`、`orchestrator_events.<N>.jsonl`、`meta.<N>.json`
- **THEN** 重构 MUST 使用这些证据按真实 live 链路回放

#### Scenario: strict replay evidence missing
- **WHEN** 任一关键证据缺失或损坏
- **THEN** 该 attempt MUST 失败
- **AND** MUST NOT 覆写该 attempt 审计文件

### Requirement: Rebuild MUST run in strict_replay mode
手动重构 MUST 固定为 strict_replay 口径，不允许 canonical / forensic best-effort 分支。

#### Scenario: rebuild request accepted
- **WHEN** 调用重构接口成功触发
- **THEN** 系统 MUST 以 strict replay 口径重建 RASP/FCMP
- **AND** 返回结果中 MUST 显示 `mode=strict_replay`

### Requirement: Rebuild MUST NOT inject compensation events
重构期间系统 MUST NOT 注入补偿事件；系统 MUST 仅写入真实回放链路自然产出的事件。

#### Scenario: waiting-user without replay evidence
- **WHEN** 回放未自然产出 `interaction.user_input.required`
- **THEN** 系统 MUST 保持缺失
- **AND** MUST NOT 通过 meta 注入该事件

### Requirement: RASP MUST provide engine-agnostic process event types
RASP 审计层 MUST 使用通用 `agent.*` 过程事件类型表达真正的推理、工具调用与命令执行，并使用独立消息语义表达非终态 agent 文本；不得引入 engine-specific 顶层事件名。

#### Scenario: parser emits process semantics and non-final agent text
- **GIVEN** parser 同时识别到推理、工具调用、命令执行和面向用户的非终态 agent 文本
- **WHEN** RASP 事件发布
- **THEN** 系统 MUST 使用 `agent.reasoning` / `agent.tool_call` / `agent.command_execution` 表达真正过程语义
- **AND** 对非终态 agent 文本 MUST 使用 `agent.message.intermediate`
- **AND** MUST NOT 使用引擎专属 type 名称进入 runtime contract

### Requirement: promoted MUST precede final for same message_id
The system MUST publish `agent.message.promoted` before `agent.message.final` for the same `message_id`，且 promoted/final 只表达收敛边界，不重新定义中间消息的原始语义。

#### Scenario: intermediate message converges to final answer
- **GIVEN** 已存在一条 `agent.message.intermediate(message_id=X)`
- **WHEN** 系统发布最终收敛事件
- **THEN** `agent.message.promoted(message_id=X)` MUST precede `agent.message.final(message_id=X)`
- **AND** `agent.message.intermediate` MUST NOT 被重新归类为 `agent.reasoning`

### Requirement: RASP turn-complete event MUST carry structured turn stats
`agent.turn_complete` 事件 MUST 承载结构化统计信息，且数据 MUST 直接位于 `data` 顶层对象。

#### Scenario: gemini turn complete carries stats
- **GIVEN** Gemini 结构化输出包含 `stats`
- **WHEN** parser 产出回合结束语义并发布 RASP
- **THEN** `agent.turn_complete.data` MUST 直接包含 `stats` 对象内容
- **AND** 不得再嵌套 `data.details`

#### Scenario: codex/opencode turn complete carries normalized metrics
- **GIVEN** Codex `turn.completed` 含 `usage` 或 OpenCode `step_finish.part` 含 `cost/tokens`
- **WHEN** parser 产出回合结束语义并发布 RASP
- **THEN** `agent.turn_complete.data` MUST 直接承载对应结构化字段
- **AND** 事件类型与 RASP/FCMP 命名边界保持不变

### Requirement: Eventized run handle MUST be emitted for Gemini and iFlow
Gemini 与 iFlow 在可识别会话句柄时 MUST 发布 `lifecycle.run_handle`，用于即时持久化恢复句柄。

#### Scenario: gemini structured response includes session_id
- **GIVEN** Gemini 运行期批次 JSON 含 `session_id`
- **WHEN** parser 完成语义提取
- **THEN** 系统 MUST 发布 `lifecycle.run_handle` 且 `data.handle_id = session_id`

#### Scenario: iflow execution info includes session-id
- **GIVEN** iFlow 输出存在 `<Execution Info>` 且内层 JSON 含 `session-id`
- **WHEN** parser 提取 execution info
- **THEN** 系统 MUST 发布 `lifecycle.run_handle` 且 `data.handle_id = session-id`

### Requirement: RASP MUST support cross-engine turn markers
RASP 审计流 MUST 支持通用回合标记事件 `agent.turn_start` 与 `agent.turn_complete`，并保持引擎无关语义。

#### Scenario: codex/opencode explicit markers
- **GIVEN** Codex 或 OpenCode 解析到显式 turn 边界事件
- **WHEN** 事件进入 live publisher
- **THEN** 系统 MUST 发布 `agent.turn_start` 与 `agent.turn_complete`
- **AND** 事件 SHOULD 继承对应源行 `raw_ref`

#### Scenario: gemini/iflow implicit turn start
- **GIVEN** Gemini 或 iFlow attempt 子进程已启动
- **WHEN** live publisher 收到 process started 信号
- **THEN** 系统 MUST 立即发布一次 `agent.turn_start`
- **AND** 不得依赖首条 stdout/stderr 输出

### Requirement: Semantic-hit rows MUST suppress duplicated raw rows
当 parser 已提取语义事件且具备 `raw_ref` 时，重叠区间的 raw 行 MUST 被抑制。

#### Scenario: opencode tool_use mapped to process_event
- **GIVEN** OpenCode NDJSON 行命中 `tool_use` 语义映射
- **WHEN** live pipeline 同时处理 raw 行与 process_event
- **THEN** 对应 `raw_ref` 区间的 `raw.stdout/raw.stderr` MUST NOT 再次发布

### Requirement: RASP MUST expose lifecycle run handle for eventized engines
当引擎输出中包含可识别的 run/session 句柄时，RASP MUST 发布 `lifecycle.run_handle` 事件并携带 `data.handle_id`。

#### Scenario: codex thread started emits run handle
- **GIVEN** Codex 输出 `thread.started` 且包含 `thread_id`
- **WHEN** parser 处理该行并进入 live publisher
- **THEN** 系统 MUST 发布 `lifecycle.run_handle`
- **AND** 事件 `data.handle_id` MUST 等于该 `thread_id`

#### Scenario: opencode step start emits run handle
- **GIVEN** OpenCode 输出 `step_start` 且包含 `sessionID`
- **WHEN** parser 处理该行并进入 live publisher
- **THEN** 系统 MUST 发布 `lifecycle.run_handle`
- **AND** 同一源行 MAY 同时发布 `agent.turn_start`

### Requirement: run handle change MUST be observable
当同一 run 的 handle 发生变更时，系统 MUST 覆盖存储并发布可观测诊断告警。

#### Scenario: handle changed during later attempt
- **GIVEN** run 已持久化 handle `A`
- **WHEN** live publisher 再次发布 `lifecycle.run_handle` 且值为 `B`（`B != A`）
- **THEN** 系统 MUST 将 run handle 更新为 `B`
- **AND** MUST 发布 `diagnostic.warning`，`data.code = RUN_HANDLE_CHANGED`

### Requirement: Qwen live observability MUST use shared run-handle and process-event semantics
Qwen 的 live observability 要求 MUST 归入共享 `interactive-run-observability` capability，而不是通过独立 qwen parser capability 单独维护。

#### Scenario: qwen init event emits run handle
- **GIVEN** Qwen 输出 `system/subtype=init` 且包含 `session_id`
- **WHEN** live parser 与 publisher 处理该事件
- **THEN** 系统 MUST 发布 `lifecycle.run_handle`
- **AND** `data.handle_id` MUST 等于该 `session_id`

#### Scenario: qwen process semantics use shared agent event types
- **GIVEN** Qwen 解析到 `thinking`、`tool_use` 或 `tool_result`
- **WHEN** 这些语义进入 RASP/FCMP 可观测链路
- **THEN** `thinking` MUST 使用共享 `agent.reasoning`
- **AND** `run_shell_command` MUST 使用共享 `agent.command_execution`
- **AND** 其它 Qwen tools MUST 使用共享 `agent.tool_call`

