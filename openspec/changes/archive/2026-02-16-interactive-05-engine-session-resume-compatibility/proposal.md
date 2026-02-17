## Why

交互执行需要支持“中途 ask_user -> 用户回复 -> 继续执行”的闭环。  
其中存在两类引擎能力：
1. 支持 resume：可以在 `waiting_user` 结束当前进程，收到 `reply` 后再启动新进程恢复会话。
2. 不支持 resume：仍可交互，但必须保持原进程驻留等待用户回复。

目前这件事对三引擎的“可实现细节”仍有不确定性：
1. 三个 CLI 的 resume 参数与会话标识形态不一致。
2. 我们尚未定义统一的会话句柄持久化协议与能力分层输出。
3. 对“无 resume 能力”的等待超时、进程回收、错误语义缺少统一规范。

因此需要在 `interactive-10` / `interactive-20` 之前插入一个兼容性 change，先把“会话恢复能力与回退路径”做成可验证、可落地的合同。

## What Changes

1. 新增“引擎会话恢复兼容层”能力定义：
   - 统一 `EngineSessionHandle` 抽象（opaque handle，不暴露内部结构）。
   - 统一 `EngineInteractiveProfile` 抽象（`resumable|sticky_process`）。
   - 统一 resume 入口契约（orchestrator 调用而非直接拼命令）。

2. 增加三引擎恢复能力探测与版本分层：
   - Codex / Gemini / iFlow 分别定义最小可行 resume 探测流程。
   - probe 通过：标记 `resumable`，允许 `waiting_user` 释放槽位并跨进程恢复。
   - probe 失败：标记 `sticky_process`，仍允许 interactive，但等待阶段不释放槽位。

3. 定义会话句柄持久化协议：
   - `resumable` 路径进入 `waiting_user` 时必须持久化 `session_handle`。
   - `resumable` 路径 resume 时必须读取同一 handle 并进行一致性校验。
   - `sticky_process` 路径持久化 `wait_deadline_at` 与进程绑定信息。

4. 固化 Codex 已确认恢复路径（作为确定性基线）：
   - 在 `codex exec --json` 回合中，首条事件 `type=thread.started` 的 `thread_id` 作为 resume 凭证。
   - 下一回合使用 `codex exec resume`，将 `thread_id` 以**位置参数**形式放在 prompt 之前（不是命名参数）。

5. 固化 Gemini 已确认恢复路径（作为确定性基线）：
   - 在 Gemini 的 JSON 模式首轮返回体中，`session_id` 作为 resume 凭证。
   - 下一回合保持原执行参数，并追加 `--resume "<session_id>"` 即可恢复会话。

6. 固化 iFlow 已确认恢复路径（作为确定性基线）：
   - 在 iFlow 回合的 `<Execution Info>` 中，`session-id` 作为 resume 凭证。
   - 下一回合保持原执行参数，并追加 `--resume "<session-id>"` 即可恢复会话。

7. 定义等待超时与失败语义：
   - 不新增 interactive 专用超时配置；05 仅消费“会话级 hard timeout”语义；
   - `session_timeout_sec` 的命名统一、兼容映射与消费收口由 `interactive-11` 负责；
   - 05 仅要求 sticky_process 等待超时逻辑消费归一化会话超时值（默认语义为 `1200` 秒）。
   - `SESSION_RESUME_FAILED`（`resumable` 路径下恢复失败）
   - `INTERACTION_WAIT_TIMEOUT`（`sticky_process` 等待用户回复超时，进程被终止）
   - `INTERACTION_PROCESS_LOST`（`sticky_process` 等待期间进程意外退出）
   - 错误码与状态流转规则写入 API 合同。

## Impact

- `server/services/agent_cli_manager.py`
- `server/adapters/base.py`
- `server/adapters/codex_adapter.py`
- `server/adapters/gemini_adapter.py`
- `server/adapters/iflow_adapter.py`
- `server/services/job_orchestrator.py`
- `server/services/run_store.py`
- `server/models.py`
- `docs/api_reference.md`
- `tests/unit/test_*adapter*.py`
- `tests/integration/run_integration_tests.py`
