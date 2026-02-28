# interactive-05-engine-session-resume-compatibility 实现记录

## 变更范围
- 新增交互恢复模型：`EngineSessionHandle`、`EngineResumeCapability`、`EngineInteractiveProfile`、`InteractiveErrorCode`。
- 新增交互运行态持久化：`request_interactive_runtime` 表，以及 profile/session-handle/sticky-wait 读写接口。
- 引擎能力探测：
  - `AgentCliManager` 增加 resume 静态 + 动态 probe。
  - probe 结果映射为 `resumable` / `sticky_process`。
- 三引擎恢复实现：
  - Codex: 解析首条 `thread.started.thread_id`，恢复命令使用位置参数 `thread_id`（在 prompt 前）。
  - Gemini: 解析 JSON `session_id`，恢复命令追加 `--resume <session_id>`。
  - iFlow: 解析 `<Execution Info>` 中 `session-id`，恢复命令追加 `--resume <session-id>`。
- Orchestrator 集成：
  - interactive 模式下持久化 profile、pending interaction、session handle / sticky wait 运行态。
  - 支持 `waiting_user` 状态输出与 resume 上下文注入。
  - 映射错误码：`SESSION_RESUME_FAILED` / `INTERACTION_WAIT_TIMEOUT` / `INTERACTION_PROCESS_LOST`。
- API 交互回复路径：
  - `POST /v1/jobs/{request_id}/interaction/reply` 接收后触发续跑任务。
  - sticky 路径增加 deadline 与进程丢失检查，并按错误码失败。

## 测试与校验
- 定向单测：
  - `49 passed`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m pytest -q tests/unit/test_agent_cli_manager.py tests/unit/test_codex_adapter.py tests/unit/test_gemini_adapter.py tests/unit/test_iflow_adapter.py tests/unit/test_run_store.py tests/unit/test_jobs_interaction_routes.py tests/unit/test_job_orchestrator.py`
- 全量单元测试：
  - `262 passed`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m pytest tests/unit`
- 类型检查：
  - `Success: no issues found in 50 source files`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m mypy server`
- OpenSpec：
  - `openspec validate "interactive-05-engine-session-resume-compatibility" --type change --strict`
  - `openspec archive "interactive-05-engine-session-resume-compatibility" -y`
  - 归档目录：`openspec/changes/archive/2026-02-16-interactive-05-engine-session-resume-compatibility`

