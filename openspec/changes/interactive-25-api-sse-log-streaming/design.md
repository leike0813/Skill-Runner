## Context

当前服务端已经在进程执行期间持续写入 `logs/stdout.txt` 与 `logs/stderr.txt`，  
但外部 API 客户端只能通过 `/logs` 拿到全量文本，不适合高频实时监控。

UI 路径已有 logs tail 轮询逻辑，可作为读取策略参考，但其接口形态是 HTML partial，不是通用 API 契约。

## Goals

1. 提供稳定的 SSE API，让客户端实时接收 stdout/stderr 增量与状态变化。
2. 支持断线重连后的增量恢复，避免每次重连重复拉取全量日志。
3. 明确 `waiting_user` 与终态的事件与连接行为。
4. 保持现有 `/logs` 与 UI tail 行为兼容。

## Non-Goals

1. 不替换 UI 的 HTMX 日志 tail 页面。
2. 不实现 WebSocket 双向输入通道（仅服务端单向事件流）。
3. 不在本 change 改动 adapter 的日志写入机制。

## Design

### 1) 新增 SSE 端点

- `GET /v1/jobs/{request_id}/events`
- `GET /v1/temp-skill-runs/{request_id}/events`

响应类型：`text/event-stream`。

### 2) 事件类型与载荷

统一事件格式（JSON）：
- `event: snapshot`
  - 初始状态快照
  - 字段：`status`, `stdout_offset`, `stderr_offset`, `pending_interaction_id?`
- `event: stdout`
  - stdout 增量块
  - 字段：`from`, `to`, `chunk`
- `event: stderr`
  - stderr 增量块
  - 字段：`from`, `to`, `chunk`
- `event: status`
  - 状态变化事件
  - 字段：`status`, `pending_interaction_id?`, `updated_at?`
- `event: heartbeat`
  - 保活事件
  - 字段：`ts`
- `event: end`
  - 服务端准备关闭连接
  - 字段：`reason`（`waiting_user`/`terminal`/`timeout`/`client_closed`）

### 3) 游标与重连

请求参数：
- `stdout_from`（默认 `0`）
- `stderr_from`（默认 `0`）

语义：
- 服务端从给定 offset 开始推送增量；
- 每个 `stdout/stderr` 事件都回传 `from/to`；
- 客户端断线重连时用上次 `to` 作为新的 `*_from`。

可选增强（实现时可二选一）：
- 支持 `Last-Event-ID`；或
- 仅支持 query offsets（最小实现）。

### 4) waiting_user 与终态行为

- 当 run 进入 `waiting_user`：
  - 发出 `status` 事件（`status=waiting_user`）；
  - 发出 `end` 事件（`reason=waiting_user`）；
  - 关闭连接（客户端在 reply 后重新建立流）。
- 当 run 进入终态（`succeeded/failed/canceled`）：
  - 发出最终 `status`；
  - 发出 `end`（`reason=terminal`）；
  - 关闭连接。

### 5) 复用与抽象策略

- 复用 `run_observability` 的状态读取与 tail 读取逻辑；
- 新增流式读取器（按 offset 增量读取，不走全量 read_text）；
- 不修改 adapter 写日志路径与格式，SSE 仅消费现有文件。

## Risks & Mitigations

1. **风险：SSE 连接长期占用造成资源压力**
   - 缓解：heartbeat 间隔固定、空闲超时、`waiting_user`/终态及时关闭连接。
2. **风险：日志高速增长导致单事件过大**
   - 缓解：服务端按最大 chunk 切片发送（例如 8KB）。
3. **风险：客户端重连重复消费**
   - 缓解：offset 明确单调递增，客户端按 `to` 续传。
4. **风险：UI 与 API 双路径实现漂移**
   - 缓解：共享 `run_observability` 核心读取函数，减少重复逻辑。
