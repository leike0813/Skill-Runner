## Context

交互执行的目标架构是“回合执行 -> 等待用户 -> 回复后继续回合”。  
是否能在等待时释放并发槽位，取决于引擎是否支持 resume：
- `resumable`：等待时结束进程并释放槽位，回复后新进程恢复；
- `sticky_process`：不结束进程，保持进程驻留等待回复。

已知现状：
1. Codex CLI 提供 `codex exec resume ... --json`，且在 `codex exec --json` 输出中可稳定获得 `thread.started.thread_id`。
2. Gemini CLI 提供 `--resume` 与 `--list-sessions`，且在 JSON 模式首轮返回体中可稳定获得 `session_id`。
3. iFlow CLI 提供 `--continue` / `--resume`，且在 `<Execution Info>` 中可稳定获得 `session-id`。

但三者的会话标识来源、恢复命令组合、非交互兼容性都不一致。

## Goals

1. 定义跨引擎统一的 `EngineSessionHandle` 协议。
2. 定义跨引擎统一的 `EngineInteractiveProfile`（`resumable|sticky_process`）。
3. 明确三引擎“如何生成 handle、如何恢复”的最小可行路径。
4. 在无 resume 能力时提供可执行的驻留等待与超时回收策略。
5. 将恢复失败与等待超时转换为稳定错误码，避免 silent failure。

## Non-Goals

1. 不追求三引擎恢复参数完全同构。
2. 不在本 change 设计 token 级流式恢复。
3. 不修改 UI TUI 会话管理路径。
4. 不在无 resume 路径上实现服务重启后的会话接管（该路径以进程驻留为前提）。

## Design

### 1) 会话句柄与能力分层

新增统一结构（逻辑层）：
- `EngineSessionHandle`
  - `engine`: `codex|gemini|iflow`
  - `handle_type`: `session_id|session_file|opaque`
  - `handle_value`: `string`（opaque）
  - `created_at_turn`: `int`
- `EngineInteractiveProfile`
  - `kind: resumable|sticky_process`
  - `reason: string`
  - `session_timeout_sec: int`（会话级 hard timeout；05 仅消费该归一化值，键名/兼容规则由 `interactive-11` 收敛）

约束：
- 业务层不解析 `handle_value` 内部语义；
- 仅对应引擎适配器可解释并使用该值执行 resume；
- `sticky_process` 路径可不产生 `EngineSessionHandle`，但必须产生 `session_timeout_sec`。

### 2) 能力探测与分层策略

新增 `EngineResumeCapability`：
- `supported: bool`
- `probe_method: command|api|filesystem`
- `detail: string`

策略：
1. 服务启动时收集静态能力（CLI 参数可用性）。
2. interactive run 首回合前执行一次动态 probe（低成本命令或文件路径校验）。
3. probe 通过 -> `EngineInteractiveProfile.kind=resumable`。
4. probe 失败 -> `EngineInteractiveProfile.kind=sticky_process`（不拒绝 interactive）。

### 3) 引擎恢复策略（最小可行）

1. **Codex (`resumable`)**
   - 首回合执行 `codex exec --json ...` 时，必须从首条事件中提取：
     - `{"type":"thread.started","thread_id":"<THREAD_ID>"}`
   - `thread_id` 作为 handle（`handle_type=session_id`）持久化。
   - 恢复回合命令模板：
     - `codex exec resume <same_options> "<THREAD_ID>" "<PROMPT>"`
   - 约束：
     - `<THREAD_ID>` 必须作为**位置参数**置于 `<PROMPT>` 前。
     - 不使用 `--thread-id` 等命名参数形式。

2. **Gemini (`resumable`)**
   - 首回合在 JSON 模式执行时，必须从返回体提取 `session_id`。
   - `session_id` 作为 handle（`handle_type=session_id`）持久化。
   - 恢复回合命令模板：
     - `gemini <same_options> --resume "<SESSION_ID>" ...`
   - 约束：
     - 优先使用返回体中的 `session_id`，不得仅依赖 `--list-sessions` 的排序索引。

3. **iFlow（按 probe 结果选择）**
   - 若当前环境 probe 通过，按 `resumable` 处理：
     - 从 `<Execution Info>` 提取 `session-id` 并持久化；
     - 恢复回合追加 `--resume "<session-id>"`。
   - 若当前环境 probe 失败，按 `sticky_process` 处理：
     - 不执行跨进程恢复；
     - 进入 `waiting_user` 时保持进程驻留并等待用户回复。

### 4) 持久化与一致性

进入 `waiting_user` 前必须写入：
- `interactive_profile.kind`
- `turn_index`
- `pending_interaction_id`

`resumable` 路径额外要求：
- 持久化 `engine_session_handle`；
- resume 时必须校验 run 仍处于 `waiting_user`、`interaction_id` 匹配、handle 可读。

`sticky_process` 路径额外要求：
- 持久化 `wait_deadline_at`；
- 持久化进程绑定信息（如 `pid` / `exec_session_id`）用于后续 reply 路由。

### 5) 等待超时与进程回收（`sticky_process`）

- 当 run 进入 `waiting_user` 且 `kind=sticky_process` 时，启动等待超时计时。
- 若在 `session_timeout_sec`（默认 1200 秒）内收到合法 reply，则将 reply 投递到原进程继续执行。
- 若超时未收到 reply，则终止该进程并将 run 标记 `failed`，`error.code=INTERACTION_WAIT_TIMEOUT`。
- 若等待期间进程已意外退出，则 run 进入 `failed`，`error.code=INTERACTION_PROCESS_LOST`。

### 6) 错误模型

1. `SESSION_RESUME_FAILED`
   - 仅 `resumable` 路径：具备能力但恢复命令执行失败或句柄失效。
2. `INTERACTION_WAIT_TIMEOUT`
   - 仅 `sticky_process` 路径：等待用户回复超时，进程被终止。
3. `INTERACTION_PROCESS_LOST`
   - 仅 `sticky_process` 路径：等待期间进程意外退出。

状态规则：
- 以上错误均进入 `failed`，并在 `error.code` 返回。

## Risks & Mitigations

1. **风险：Gemini/iFlow 句柄格式在升级后变化**
   - 缓解：句柄保持 opaque + 版本化 probe + 回归测试。
2. **风险：恢复命令行为受 cwd/配置影响**
   - 缓解：将 cwd、profile、关键配置写入 run 级恢复上下文并复用。
3. **风险：`sticky_process` 长时间占用执行资源**
   - 缓解：统一使用 `session_timeout_sec`（默认 1200 秒）+ 在 `interactive-10` 中约束其并发占用策略。
4. **风险：Codex 输出首事件异常或缺失 `thread_id`**
   - 缓解：该回合直接判定为 `SESSION_RESUME_FAILED`，不得进入 `waiting_user`。
5. **风险：Gemini JSON 返回缺失 `session_id`**
   - 缓解：该回合直接判定为 `SESSION_RESUME_FAILED`，不得进入 `waiting_user`。
6. **风险：`sticky_process` 路径下服务重启导致进程句柄丢失**
   - 缓解：重启恢复时将该 run 标记失败并返回 `INTERACTION_PROCESS_LOST`，避免僵尸等待。
