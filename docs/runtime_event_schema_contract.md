# Runtime Event Schema Contract

## Scope

本合同覆盖核心协议面：

- FCMP 事件（对外）
- canonical chat replay 事件（聊天气泡 SSOT）
- RASP 事件（审计）
- orchestrator 事件（内部审计）
- pending interaction
- pending auth
- interaction history entry
- interactive resume command
- current run projection
- run state envelope
- run dispatch envelope
- terminal run result

Schema 文件：

- `server/contracts/schemas/runtime_contract.schema.json`

## Validation Policy

1. 写入路径：硬校验
- 不满足 schema 的对象拒绝写入；
- 关键错误码：`PROTOCOL_SCHEMA_VIOLATION`。

2. 内部桥接：告警降级
- 记录 `diagnostic.warning`，`code=SCHEMA_INTERNAL_INVALID`；
- 回退最小安全载荷，尽量不中断主流程。
- phase 3A 预留的 `diagnostic.output_repair.*` 目前是 schema-reserved internal event surface；实现前不要求已有生产者。

3. 读取路径：读兼容
- 旧历史中不合规行被过滤；
- 其余合法行继续返回。

## Canonical Payload Notes

1. `conversation.state.changed`
- `from`, `to`, `trigger`, `updated_at`, `pending_interaction_id?`, `pending_auth_session_id?`
- terminal 时额外允许 `terminal.status`, `terminal.reason_code`, `terminal.error?`, `terminal.diagnostics[]`
- FCMP envelope `meta` 至少包含 `attempt`，可包含 `local_seq`（attempt 内局部序号）

2. `interaction.reply.accepted`
- `interaction_id`, `resolution_mode=user_reply`, `accepted_at`, `response_preview?`
- 该 FCMP 必须由 schema-backed orchestrator event `interaction.reply.accepted` 翻译得到，不允许由 reply endpoint 直接发布。

3. `auth.required` / `auth.challenge.updated`
- payload 复用 `pending_auth`
- 包含 challenge、provider、输入方式和 auth session 标识
- `auth.challenge.updated` 仅用于 challenge-active 的真实 challenge 更新或重投影；`auth.session.busy` 不得替代它

4. `auth.input.accepted`
- `auth_session_id`, `submission_kind`, `accepted_at`
- 不允许回显 raw secret

5. FCMP `auth.completed`
- 只表示 canonical auth completion，不得复用 `auth.challenge.updated`、`auth.session.busy` 或任何 readiness-like payload 的语义。
- `auth_session_id`, `completed_at`, `resume_attempt?`

6. FCMP `auth.failed`
- `auth_session_id`, `message?`, `code?`

7. orchestrator auth lifecycle events
- orchestrator audit 中的 canonical auth lifecycle type 为：
  - `auth.session.created`
  - `auth.method.selected`
  - `auth.session.busy`
  - `auth.input.accepted`
  - `auth.session.completed`
  - `auth.session.failed`
  - `auth.session.timed_out`
- `auth.input.accepted` 的 canonical payload 包含：
  - `auth_session_id`
  - `submission_kind`
  - `accepted_at`
- `auth.session.completed` 的 canonical payload 至少包含：
  - `auth_session_id`
  - `completed_at`
  - `resume_attempt?`
  - `source_attempt?`
  - `target_attempt?`
  - `resume_ticket_id?`
  - `ticket_consumed?`
- `auth.session.failed` / `auth.session.timed_out` 属于 orchestrator audit lifecycle；它们可以被翻译为 FCMP `auth.failed`，但不得与 FCMP event type 名称混淆

8. orchestrator output repair lifecycle events
- repair governance 的目标 orchestrator type 为：
  - `diagnostic.output_repair.started`
  - `diagnostic.output_repair.round.started`
  - `diagnostic.output_repair.round.completed`
  - `diagnostic.output_repair.converged`
  - `diagnostic.output_repair.exhausted`
  - `diagnostic.output_repair.skipped`
- 这些事件只属于 orchestrator audit / diagnostic 层，不得映射到 FCMP public event type
- canonical payload 至少包含：
  - `internal_round_index`
  - `repair_stage`
  - `candidate_source`
- `exhausted` / `skipped` 额外要求 `legacy_fallback_target`
- phase 3A 只定义 schema 合同；当前 runtime 可尚未产生这些事件

9. interactive completion compatibility path
- interactive formal contract remains:
  - final branch: `__SKILL_DONE__ = true`
  - pending branch: `__SKILL_DONE__ = false + message + ui_hints`
- current phase-5 runtime still preserves two compatibility paths after branch
  evaluation:
  - soft completion
  - default waiting fallback
- compatibility paths keep existing diagnostics such as
  `INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER`,
  `INTERACTIVE_OUTPUT_EXTRACTED_BUT_SCHEMA_INVALID`, and
  `INTERACTIVE_SOFT_COMPLETION_SCHEMA_TOO_PERMISSIVE`

10. orchestrator terminal lifecycle events
- `lifecycle.run.terminal` 的 `data` 在 `failed|canceled` 场景允许携带：
  - `code`（错误码摘要）
  - `message`（长度受控的错误摘要）
- FCMP terminal `conversation.state.changed.data.terminal.error` SHOULD 优先使用上述摘要字段。

11. `interaction.auto_decide.timeout`
- `interaction_id`, `resolution_mode=auto_decide_timeout`, `policy`, `accepted_at`, `timeout_sec?`

12. `current_run_projection`
- run 的唯一 current truth
- `status`, `current_attempt`, `pending_owner`, `resume_ticket_id?`, `resume_cause?`
- waiting/running/queued 只存在于 projection，不写 terminal result

13. `terminal_run_result`
- 仅允许 terminal status
- 当前合同兼容 `success|succeeded|failed|canceled`
- 非 terminal 状态必须通过 projection 读取，不得通过 `/result` 或 `result/result.json` 读取

14. `run_state_envelope`
- 对应 `.state/state.json`
- 是 current truth 的 canonical 文件 schema
- waiting payload 内嵌于 `pending.owner + pending.payload`

15. `run_dispatch_envelope`
- 对应 `.state/dispatch.json`
- 是 dispatch lifecycle 的 canonical 文件 schema
- 只允许 `created|admitted|dispatch_scheduled|worker_claimed|attempt_materializing`

16. `fcmp_event_envelope.correlation`
- 允许以 additive 方式承载 live publish 关联锚点
- 当前 canonical 用法为 `correlation.publish_id`

17. `rasp_event_envelope.correlation`
- live publish 下的 FCMP / RASP 关联同样通过 `correlation.publish_id` 表达
- 不改变 RASP 的 attempt-local `seq` 语义

18. lifecycle normalization
- FCMP conversation lifecycle 已收敛为单轨：只保留 `conversation.state.changed`
- `conversation.started`、`conversation.completed`、`conversation.failed` 不再是合法 FCMP 类型
- terminal success/failure/cancel 统一通过 `conversation.state.changed.data.terminal` 表达

19. `chat_replay_event_envelope`
- 聊天气泡的 canonical persisted truth
- `seq` 为 run-scoped 全局递增顺序
- `role` 只允许 `user|assistant|system`
- `kind` 只允许：
  - `interaction_reply`
  - `auth_submission`
  - `assistant_final`
  - `orchestration_notice`
- `text` 为最终可渲染文本
- `correlation` 允许包含 `interaction_id`、`auth_session_id`、`submission_kind`、`fcmp_seq`

20. `chat_replay_history_response`
- `/chat/history` 的 canonical 响应结构
- 包含：
  - `events`
  - `source`
  - `cursor_floor`
  - `cursor_ceiling`

## Live Truth Hierarchy

- FCMP 当前真相源：live publisher + `FcmpLiveJournal`
- canonical chat replay 当前真相源：live publisher + `ChatReplayLiveJournal`
- RASP 当前真相源：live publisher + `RaspLiveJournal`
- `.audit/fcmp_events.*.jsonl` / `.audit/events.*.jsonl`：append-only 审计镜像
- `.audit/chat_replay.jsonl`：聊天窗口的 append-only 审计镜像

新增约束：

- FCMP `seq` 在 publish 时分配，而不是在 audit 重建时分配
- RASP `seq` 在 attempt 内按 live emission 顺序分配
- SSE 不得依赖 audit 文件物化作为 active delivery 的前置条件

## Operational Guidance

1. 扩展事件字段时先改 schema，再改 factory 与测试。
2. 禁止业务层直接拼装核心 payload，统一使用 `protocol_factories`。
3. 历史兼容策略仅用于读取，不放宽写入规则。
