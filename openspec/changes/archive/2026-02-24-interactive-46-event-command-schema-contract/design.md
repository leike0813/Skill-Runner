## Overview

本变更将“协议对象（事件/命令）”从隐式约定升级为显式 JSON Schema 合同，目标是：

1. Schema 文件成为核心协议面 SSOT；
2. 写入路径严格、读取路径兼容；
3. 统一工厂构造，减少散落 `Dict[str, Any]`。

## Decisions

### Decision 1: JSON Schema 为 SSOT

- 使用单文件聚合 `$defs`：`runtime_contract.schema.json`。
- 覆盖：`fcmp_event_envelope`、`rasp_event_envelope`、`orchestrator_event`、`interaction_history_entry`、`pending_interaction`、`interactive_resume_command`。

### Decision 2: 校验策略分层

- 外部输出与持久化：硬校验失败即拒绝。
- 内部桥接：记录 `diagnostic.warning(code=SCHEMA_INTERNAL_INVALID)` 并回退最小安全载荷。
- 历史读取：过滤脏数据，不阻断整体。

### Decision 3: 工厂 + registry 双轨收敛

- `protocol_factories`：统一构造关键 payload。
- `protocol_schema_registry`：统一校验入口与错误模型（`ProtocolSchemaViolation`）。

## Data Flow

1. 运行时构造事件/命令 -> factory。
2. 序列化后调用 registry 校验。
3. 校验通过才写入 `.audit/*.jsonl` 或 sqlite。
4. 读取历史时再次校验，不合规记录 warning 并跳过。

## Failure Semantics

- `PROTOCOL_SCHEMA_VIOLATION`：用于“应当满足合同的写入对象不合法”。
- 内部桥接错误降级时：写入 `orchestrator_events.jsonl` 的 `diagnostic.warning` 事件。

## Compatibility

- 不改 SSE/history API path 与事件名称。
- 不改 FCMP 单流语义。
- 对旧历史采取读兼容策略，避免升级后无法重放。
