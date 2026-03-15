## ADDED Requirements

### Requirement: Windows command resolution MUST prefer executable wrappers over shim scripts
在 Windows 上，系统解析 engine CLI 与 ttyd 命令时 MUST 优先使用可执行包装器（`.cmd/.exe/.bat`），避免命中不可直接执行的无扩展 shim。

#### Scenario: managed engine command resolution on Windows
- **GIVEN** managed npm prefix 同时存在 `opencode` 与 `opencode.cmd`
- **WHEN** 系统解析 engine command
- **THEN** 结果 MUST 优先为 `opencode.cmd`（或其他可执行包装器）
- **AND** 不应优先返回无扩展 shim

#### Scenario: ttyd command resolution on Windows
- **GIVEN** PATH 中存在多个 ttyd 名称变体
- **WHEN** 系统解析 ttyd command
- **THEN** 解析顺序 MUST 优先 `.cmd/.exe/.bat`

### Requirement: Engine status probing MUST degrade gracefully on Windows process launch errors
在 Windows 上，命令探测与版本读取遇到 `OSError`（如 `WinError 193`）时，系统 MUST 退化为“该命令不可用/版本未知”，而不是中断启动流程。

#### Scenario: read_version hits WinError 193
- **GIVEN** 版本探测命令触发 `OSError`
- **WHEN** 系统执行 status 收集
- **THEN** `read_version` MUST 返回空值
- **AND** status 写入流程 MUST continue without uncaught exception

### Requirement: Windows concurrency probing MUST use parity resource sources
在 Windows 上，并发预算 MUST 使用平台等价资源探测，而不是静态 hard-cap fallback。

#### Scenario: Windows runtime computes concurrency budget from parity probes
- **GIVEN** runtime platform is Windows
- **WHEN** 系统计算并发上限
- **THEN** 内存维度 MUST 使用 `psutil.virtual_memory().available`
- **AND** fd 维度 MUST 使用 `_getmaxstdio`（`ucrtbase` 优先，`msvcrt` 备选）
- **AND** pid 维度 MUST 使用 Job Object `ActiveProcessLimit`
- **AND** 总上限 MUST 仍按 `min(cpu, mem, fd, pid, hard_cap)` 计算

#### Scenario: Windows runtime has no active-process job limit
- **GIVEN** runtime platform is Windows
- **AND** 当前进程不在受限 job 或 job 未设置 `ActiveProcessLimit`
- **WHEN** 系统计算 pid 维度
- **THEN** pid 维度 MUST NOT 额外收紧（按 `hard_cap` 参与最小值）

### Requirement: Windows parity probe dependency failures MUST fail fast
在 Windows 上，若并发等价探测依赖缺失或关键 API 不可用，系统 MUST fail-fast，禁止静默降级到固定 fallback。

#### Scenario: psutil missing on Windows
- **GIVEN** runtime platform is Windows
- **AND** `psutil` 不可用
- **WHEN** 服务初始化并发管理组件
- **THEN** 启动流程 MUST fail fast with actionable error
- **AND** 系统 MUST NOT silently fallback to fixed hard-cap concurrency
