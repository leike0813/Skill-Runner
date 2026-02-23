## ADDED Requirements

### Requirement: 系统 MUST 记录可回放的运行时审计工件
系统 MUST 为每次运行尝试生成编号化审计工件，以支持解析复现、故障定位与跨实现一致性验证。

#### Scenario: 生成 attempt 编号工件
- **WHEN** 同一 run 首次执行或后续 resume 回合执行
- **THEN** 系统生成 `meta.N.json`、`stdin.N.log`、`stdout.N.log`、`stderr.N.log`、`pty-output.N.log` 等审计文件
- **AND** interactive 模式下初始执行 `N=1`，每次用户 reply 回合 `N` 递增
- **AND** auto 模式下仅存在 `N=1`
- **AND** 不覆盖历史 attempt 文件

#### Scenario: meta 文件包含重建摘要
- **WHEN** 系统完成某个 attempt 的流重建
- **THEN** `meta.N.json` 包含重建摘要字段（如 `reconstruction_used`、`stdout_chunks`、`stderr_chunks`、`reconstruction_error`）
- **AND** 摘要可用于在不读取完整原始流的情况下定位重建质量

### Requirement: 系统 MUST 以 PTY + trace 采集运行输出
系统 MUST 以 PTY 运行 Agent，并通过 write syscall trace 重建 stdout/stderr 分流结果；trace 可用于运行期重建，但 MUST NOT 作为持久化日志文件落盘。

#### Scenario: PTY 运行与 trace 并行采集
- **WHEN** 系统启动引擎命令
- **THEN** 引擎运行在 PTY 环境中
- **AND** 系统采集 PTY 原始输出与 write(fd=1,2) trace
- **AND** trace 采集结果仅用于运行期重建，不要求写入 run 目录文件

#### Scenario: 基于 trace 重建 stdout/stderr
- **WHEN** 运行结束后执行流重建
- **THEN** 系统根据 trace 还原 stdout/stderr 内容
- **AND** 重建结果可定位到源 fd 与输出区间

#### Scenario: 不落盘 fd-trace 审计文件
- **WHEN** 系统完成一次运行或恢复回合
- **THEN** run 目录中不产生 `fd-trace.N.log` 文件
- **AND** 其他审计工件与重建结果保持可用

### Requirement: 系统 MUST 记录文件系统变更且排除审计目录噪声
系统 MUST 在执行前后采集文件快照并输出差异，同时忽略审计目录，避免审计器自写文件污染业务结果。

#### Scenario: 生成 fs diff
- **WHEN** 运行完成并进行快照比对
- **THEN** 系统输出 `created/modified/deleted` 三类差异集合
- **AND** 差异结果不包含审计目录路径

### Requirement: 系统 MUST 以统一优先级判定完成态
系统 MUST 使用统一规则判定 `completed/awaiting_user_input/interrupted/unknown`，并保留判定证据与诊断。

#### Scenario: 显式 done 信号优先
- **WHEN** 审计流中存在合法 completion signal 或 done marker
- **THEN** 系统优先判定为 `completed`
- **AND** 记录 `reason_code` 与证据来源

#### Scenario: 仅命中终止信号且无 done marker
- **WHEN** 命中引擎终止信号但未命中 done marker
- **THEN** 系统判定为 `awaiting_user_input`
- **AND** 产出 `DONE_MARKER_MISSING` 类诊断信息
