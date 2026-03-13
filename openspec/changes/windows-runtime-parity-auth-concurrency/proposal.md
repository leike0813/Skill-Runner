## Why

Windows 本地部署在 auth 与运行时并发预算上仍存在平台差异风险：

1. `agent_cli_manager` 在 Windows 上可能命中无扩展 shim 并触发 `WinError 193`。
2. `gemini/iflow/opencode` 的 `cli_delegate` 依赖 POSIX `pty/termios`，Windows 导入会失败。
3. 并发预算在 Windows 上不应退化为静态 fallback，而应采用可验证的等价资源探测。

需要在不改变对外 API 的前提下，统一 Windows 运行时能力并提升可预测性。

## What Changes

- 新增跨平台共享 PTY 适配层，统一 `cli_delegate` 终端读写与进程句柄抽象。
- `gemini/iflow/opencode` 的 `cli_delegate` 复用共享 PTY；Windows 走 `pywinpty`，POSIX 保持现状。
- 启动时检测 Windows `pywinpty` 能力；不可用时仅禁用 `gemini/iflow/opencode` 的 `cli_delegate`，保留 `oauth_proxy` 与 `codex cli_delegate`。
- 修复 Windows 命令解析优先级（`.cmd/.exe/.bat` 优先），覆盖 engine CLI 与 ttyd。
- `read_version` / 命令探测增加 `OSError` 兜底，避免状态写入流程中断。
- 并发预算在 Windows 上改为等价探测：
  - `mem`: `psutil.virtual_memory().available`
  - `fd`: `_getmaxstdio`（`ucrtbase` 优先，`msvcrt` 备选）
  - `pid`: Job Object `ActiveProcessLimit`（无 job 限额时不额外收紧）
- Windows 若缺 `psutil` 或关键探测 API 不可用，启动阶段 fail-fast（不做静默 hard fallback）。

## Capabilities

### Modified Capabilities

- `in-conversation-auth-flow`
- `local-deploy-bootstrap`

## Impact

- Affected code:
  - `server/runtime/auth/*`
  - `server/engines/*/auth/drivers/cli_delegate_flow.py`
  - `server/services/engine_management/engine_auth_bootstrap.py`
  - `server/services/engine_management/agent_cli_manager.py`
  - `server/services/platform/concurrency_manager.py`
  - `tests/unit/test_*auth_cli_flow.py`
  - `tests/unit/test_engine_auth_bootstrap.py`
  - `tests/unit/test_agent_cli_manager.py`
  - `tests/unit/test_concurrency_manager.py`
  - `pyproject.toml`
- API impact: None.
- Protocol impact: None.
