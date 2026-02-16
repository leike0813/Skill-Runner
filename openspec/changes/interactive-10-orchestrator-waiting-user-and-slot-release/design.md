## Context

现有 `run_job` 在开始时 `acquire_slot()`，结束时 `release_slot()`，中途没有暂停点。  
交互模式下，这会让 run 在等待用户时持续占用槽位，不可接受。

## Goals

1. 建立可暂停/恢复的 run 状态机。
2. 在 `resumable` 与 `sticky_process` 两种档位下分别保证正确的槽位语义。
3. 保证异常、超时、取消路径下的槽位与状态一致性。
4. 为后续多引擎交互回合执行提供统一编排骨架。

## Non-Goals

1. 不在本 change 引入 UI 推送机制。
2. 不引入跨 run 的事务调度器。
3. 不实现 failover 到其他引擎。

## Prerequisite

- 必须先完成 `interactive-05-engine-session-resume-compatibility` 中的能力探测、执行档位协议与恢复错误模型。
- `interactive-10` 不自行定义引擎恢复细节，只消费 `interactive-05` 产出的 `interactive_profile` 与会话句柄。

## Design

### 1) 状态机

状态转换：
- `queued -> running`
- `running -> waiting_user`（收到 ask_user）
- `waiting_user -> queued`（`resumable` 收到合法 reply，等待调度）
- `queued -> running`（`resumable` 恢复回合）
- `waiting_user -> running`（`sticky_process` 收到合法 reply，回注入同一进程）
- `running -> succeeded|failed|canceled`
- `waiting_user -> failed`（`sticky_process` 超时或进程丢失）

### 2) 槽位生命周期

`resumable`：
1. 进入执行回合前申请 slot。
2. 回合结束：
   - 若终态：释放 slot；
   - 若进入 `waiting_user`：先持久化状态，再释放 slot。
3. 收到 reply 后重新入队，由后台任务再申请 slot 执行恢复回合。

`sticky_process`：
1. 进入执行回合前申请 slot，并保持进程存活。
2. 回合进入 `waiting_user` 时不释放 slot，保持进程驻留等待。
3. 收到 reply 后在同一进程继续执行；仅在终态/失败/取消时释放 slot。
4. 超时未收到 reply 时终止进程并释放 slot。

### 3) 持久化结构

建议在 `run_store` 增加：
- `run_interactions`：交互历史（interaction_id、kind、prompt、response、timestamps）。
- `run_runtime_state`：当前待决 id、interactive_profile、resume token、最后回合序号等。

并在 run_dir 增加文件镜像（便于排障）：
- `interactions/pending.json`
- `interactions/history.jsonl`
- `interactions/runtime_state.json`

### 4) 一致性与容错

- 任何异常路径都必须通过 `finally` 释放已持有 slot。
- `waiting_user` 与 `running` 之间切换要保证幂等，避免重复 resume 或重复注入 reply。
- `resumable`：服务重启后可基于 `run_runtime_state` 继续等待与恢复。
- `sticky_process`：服务重启后因无法接管原进程，应将 run 标记为 `failed`（`INTERACTION_PROCESS_LOST`）。
- `sticky_process`：进入 `waiting_user` 必须按统一会话超时 `session_timeout_sec`（默认 1200 秒）设置 `wait_deadline_at`，超时后强制终止进程并结束 run。

## Risks & Mitigations

1. **风险：状态竞争（重复 reply）**
   - 缓解：基于 `interaction_id` + 原子状态更新（waiting_user -> queued）。
2. **风险：槽位泄漏**
   - 缓解：统一封装“回合执行上下文”，在单处处理 acquire/release。
3. **风险：sticky_process 长时间占用槽位影响吞吐**
   - 缓解：复用统一 `session_timeout_sec`（默认 1200 秒）做 hard timeout 回收 + 并发池指标监控。
4. **风险：持久化迁移影响旧库**
   - 缓解：采用 `CREATE TABLE IF NOT EXISTS` + 向后兼容列补齐策略。
