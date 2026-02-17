# interactive-11-session-timeout-unification-and-consumer-refactor 实现记录

## 变更范围
- 会话超时统一：
  - 新增 `server/services/session_timeout.py`，提供统一解析器：
    - 统一键：`session_timeout_sec`
    - 默认值：`1200`
    - 兼容历史键：`interactive_wait_timeout_sec` / `hard_wait_timeout_sec` / `wait_timeout_sec`
    - 冲突优先级：新键优先，旧键忽略
- 配置与校验：
  - `options_policy` 接入统一解析，产出归一化 `session_timeout_sec`，并记录 deprecation 日志。
  - 运行时允许键增加：`session_timeout_sec` 及历史兼容键。
  - `core_config` 增加 `SYSTEM.SESSION_TIMEOUT_SEC`（支持环境变量 `SKILL_RUNNER_SESSION_TIMEOUT_SEC`）。
- 消费位点统一：
  - Orchestrator 统一使用归一化值计算 `wait_deadline_at`。
  - sticky watchdog 超时链路统一消费同一超时值。
  - 在 `run_store.request_interactive_runtime` 持久化 `effective_session_timeout_sec`。
  - `status.json` 与 `run_observability` 输出增加 `effective_session_timeout_sec`。
- 文档更新：
  - 对外文档仅保留 `session_timeout_sec`，不再公开 interactive 专用旧命名。

## 测试与校验
- 定向单测：
  - `73 passed`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m pytest -q tests/unit/test_options_policy.py tests/unit/test_runs_router_cache.py tests/unit/test_temp_skill_runs_router.py tests/unit/test_jobs_interaction_routes.py tests/unit/test_job_orchestrator.py tests/unit/test_run_observability.py tests/unit/test_run_store.py tests/unit/test_session_timeout.py`
- 全量单元测试：
  - `275 passed`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m pytest tests/unit`
- 类型检查：
  - `Success: no issues found in 51 source files`
  - 命令：`conda run --no-capture-output -n DataProcessing python -m mypy server`
- OpenSpec：
  - `openspec validate "interactive-11-session-timeout-unification-and-consumer-refactor" --type change --strict --no-interactive`
  - `openspec archive "interactive-11-session-timeout-unification-and-consumer-refactor" -y`
  - 归档目录：`openspec/changes/archive/2026-02-16-interactive-11-session-timeout-unification-and-consumer-refactor`

