## Context

现有 `cli_delegate` 在三个引擎中重复维护 PTY 逻辑并直接依赖 POSIX `pty`。  
Windows 缺失 `termios`，会在导入阶段失败；同时 Windows 命令解析可能命中不可直接执行 shim。  
此外，并发预算在 Windows 上需要等价资源探测，而不是静态 fallback。

## Design Goals

1. 在 Windows 上提供可运行的 `cli_delegate` 路径（依赖 `pywinpty`）。
2. 保持 POSIX 行为不退化。
3. 平台差异收敛到共享层，减少三套驱动重复逻辑。
4. 启动期显式处理 Windows 能力缺失并给出可操作日志。
5. 并发预算在 Windows 上使用等价探测并具备 fail-fast 语义。

## Design

### 1) Shared PTY Runtime Layer

- 新增共享 PTY 运行时模块，提供：
  - 最小进程句柄契约：`pid + poll()`
  - PTY 句柄契约：`read(size) / write(text) / close()`
  - 统一入口：`spawn_cli_pty(...)`
- POSIX 分支继续使用 `openpty + subprocess.Popen`。
- Windows 分支使用 `winpty.PtyProcess.spawn(...)`，并通过轻量 process adapter 暴露 `pid/poll`。

### 2) Driver Integration

- `gemini/iflow/opencode` 的 `cli_delegate_flow` 统一改为调用共享 `spawn_cli_pty`。
- 会话对象保留原字段兼容单测，同时新增共享 runtime 引用。
- 读写/关闭优先走 runtime；无 runtime 时保留旧 fd 路径用于测试桩兼容。

### 3) Bootstrap Capability Gate

- `engine_auth_bootstrap` 在 Windows 启动时检测 `pywinpty` 能力（import + `PtyProcess.spawn` 可用性）。
- 若不可用：
  - 仅过滤 `gemini/iflow/opencode` 的 `cli_delegate` driver 注册项；
  - 保留其 `oauth_proxy`；
  - 保留 `codex` 的 `cli_delegate`；
  - 输出一次性 warning（含修复指引）。

### 4) Windows Command Resolution Hardening

- `agent_cli_manager` 引入 Windows 候选重排：优先 `.cmd/.exe/.bat`。
- 应用于：
  - `resolve_managed_engine_command`
  - `resolve_global_engine_command`
  - `resolve_ttyd_command`
- `read_version` 与 `_run_command` 增加 `OSError` 兜底，返回“不可用/失败”而非抛异常。

### 5) Windows Concurrency Probe Parity

- 并发预算公式保持不变：`min(cpu_limit, mem_limit, fd_limit, pid_limit, hard_cap)`。
- Windows 维度实现：
  - `mem_limit`：`psutil.virtual_memory().available`
  - `fd_limit`：`_getmaxstdio`（`ucrtbase` 优先，`msvcrt` 备选）
  - `pid_limit`：Job Object `ActiveProcessLimit`；无 job 限额时该维度不额外收紧（取 `hard_cap`）
- Windows 缺 `psutil` 或关键探测 API 不可用时抛出 fatal probe error，启动 fail-fast，不走静默 fallback。
- POSIX 维度保持 `resource + /proc/meminfo` 原语义。

## Non-Goals

- 不新增对外 API 字段。
- 不改变 OAuth proxy 语义。
- 不引入新的对外配置项。
