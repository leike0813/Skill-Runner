## Overview

本变更将运行时事件面统一为 FCMP 单流。RASP 继续保留作为审计证据层，但不再是客户端业务消费接口。

核心目标：

1. 客户端只消费 `chat_event`。
2. FCMP 显式覆盖状态迁移与交互恢复语义。
3. cursor/history 单一化到 FCMP `seq`。

## Decisions

### Decision 1: SSE 只保留 FCMP 业务事件

- 保留：`snapshot`, `chat_event`, `heartbeat`
- 移除业务语义：`run_event`, `status`, `stdout`, `stderr`, `end`

### Decision 2: FCMP 最小补充事件集

新增 3 个事件，覆盖原先侧带/推断语义：

- `conversation.state.changed`
- `interaction.reply.accepted`
- `interaction.auto_decide.timeout`

### Decision 3: FCMP cursor/history 统一

- `cursor` 按 `chat_event.seq` 续传。
- `/events/history` 返回 FCMP 序列，不再返回 RASP 历史。

### Decision 4: 状态机映射以 canonical event 为锚点

FCMP 事件由状态机 canonical event 触发，避免从 RASP lifecycle 二次推断终态。

## Data Flow

1. Orchestrator 产生日志/状态/交互事实。
2. `runtime_event_protocol` 组装 RASP（审计）并输出 FCMP（对外）。
3. `run_observability` 将 FCMP 写入 `.audit/fcmp_events.jsonl`，SSE/history 只读该序列。
4. UI/e2e 页面只监听 `chat_event` 驱动状态与会话渲染。

## Sequence Diagram SSOT

新增文档：`docs/session_event_flow_sequence_fcmp.md`，覆盖：

1. 主执行流
2. 回复恢复流
3. 超时自动决策流
4. 重启恢复流

每条图均标注 FCMP 事件名、状态迁移、触发方。

## Risks & Mitigations

1. 风险：旧客户端依赖 `status/end/stdout/stderr`。
- 缓解：管理页与 e2e 示例客户端同步切到 FCMP 单流。

2. 风险：状态迁移事件漏发。
- 缓解：新增协议对齐测试，强校验 canonical transition -> FCMP 映射。

3. 风险：历史重放行为变化。
- 缓解：新增 FCMP cursor/history 单测，覆盖断线重连路径。
