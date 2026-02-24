# Runtime Event Schema Contract

## Scope

本合同覆盖核心协议面：

- FCMP 事件（对外）
- RASP 事件（审计）
- orchestrator 事件（内部审计）
- pending interaction
- interaction history entry
- interactive resume command

Schema 文件：

- `server/assets/schemas/protocol/runtime_contract.schema.json`

## Validation Policy

1. 写入路径：硬校验
- 不满足 schema 的对象拒绝写入；
- 关键错误码：`PROTOCOL_SCHEMA_VIOLATION`。

2. 内部桥接：告警降级
- 记录 `diagnostic.warning`，`code=SCHEMA_INTERNAL_INVALID`；
- 回退最小安全载荷，尽量不中断主流程。

3. 读取路径：读兼容
- 旧历史中不合规行被过滤；
- 其余合法行继续返回。

## Canonical Payload Notes

1. `conversation.state.changed`
- `from`, `to`, `trigger`, `updated_at`, `pending_interaction_id?`
- FCMP envelope `meta` 至少包含 `attempt`，可包含 `local_seq`（attempt 内局部序号）

2. `interaction.reply.accepted`
- `interaction_id`, `resolution_mode=user_reply`, `accepted_at`, `response_preview?`

3. `interaction.auto_decide.timeout`
- `interaction_id`, `resolution_mode=auto_decide_timeout`, `policy`, `accepted_at`, `timeout_sec?`

## Operational Guidance

1. 扩展事件字段时先改 schema，再改 factory 与测试。
2. 禁止业务层直接拼装核心 payload，统一使用 `protocol_factories`。
3. 历史兼容策略仅用于读取，不放宽写入规则。
