# Design: harden-agent-cli-process-lifecycle-governance

## Core Architecture
- `ProcessLeaseStore`: 文件化 lease 持久化（`data/runtime_process_leases/*.json`）。
- `RuntimeProcessSupervisor`: 统一 register/release/terminate/reap/sweep。
- `process_termination`: 跨平台 TERM→KILL 终止工具。

## Lifecycle Rules
1. 子进程创建后必须 register lease。
2. 任意终态路径必须 release lease。
3. 启动时先 `reap_orphan_leases_on_startup()`，再恢复 run。
4. 清理范围仅限有 lease 的受管进程，不做命令行扫描。

## Integration Points
- `base_execution_adapter`: run attempt 子进程接入 lease。
- `engine_auth_flow_manager` + `session_lifecycle`: auth 子进程接入 lease。
- `ui_shell_manager`: ttyd 子进程接入 lease。
- `run_recovery_service`: 消费启动期 orphan reap 报告，输出结构化恢复日志。

## Safety
- orphan 清理失败仅告警，不阻断启动。
- 终止失败返回结构化结果并保留后续收敛路径（例如 finalize/release）。
