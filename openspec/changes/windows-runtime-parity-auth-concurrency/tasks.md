## 1. OpenSpec Artifacts

- [x] 1.1 Rename change id to `windows-runtime-parity-auth-concurrency`.
- [x] 1.2 Update proposal/design/tasks/spec deltas to include concurrency parity and fail-fast policy.

## 2. Shared PTY Runtime

- [x] 2.1 Add cross-platform shared PTY runtime abstraction for cli_delegate.
- [x] 2.2 Implement Windows `pywinpty` branch with process adapter (`pid/poll`).
- [x] 2.3 Keep POSIX `openpty + subprocess` behavior unchanged.

## 3. Engine Auth Bootstrap and Routing

- [x] 3.1 Add Windows `pywinpty` capability probe at bootstrap.
- [x] 3.2 Disable `cli_delegate` driver registration for `gemini/iflow/opencode` when probe fails.
- [x] 3.3 Emit actionable warning while preserving `oauth_proxy` and `codex cli_delegate`.

## 4. Windows Runtime Parity

- [x] 4.1 Add Windows candidate ordering (`.cmd/.exe/.bat` first) for managed/global engine command resolution.
- [x] 4.2 Apply same ordering to ttyd command resolution.
- [x] 4.3 Add `OSError` fallback in version/probe command execution paths.
- [x] 4.4 Implement Windows concurrency probe parity (`psutil` memory + WinAPI stdio/job limits).
- [x] 4.5 Enforce fail-fast when Windows parity probes are unavailable.

## 5. Tests and Validation

- [x] 5.1 Update/add unit tests for bootstrap routing gate and command resolution.
- [x] 5.2 Add Windows-branch unit coverage for gemini/iflow/opencode cli_delegate flow runtime paths.
- [x] 5.3 Add/extend concurrency manager tests for Windows parity and fail-fast behavior.
- [x] 5.4 Run targeted pytest, mypy, and openspec validation.
