# run-audit-contract Specification

## Purpose
TBD - created by archiving change simplify-temp-skill-lifecycle-and-complete-state-audit-cutover. Update Purpose after archive.
## Requirements
### Requirement: Request Input Snapshot Is Audit-Only

New runs MUST persist request input snapshots at `.audit/request_input.json`.

#### Scenario: New run request snapshot
- WHEN a run is created
- THEN the request payload snapshot is written to `.audit/request_input.json`
- AND no root-level `input.json` is written for that run

### Requirement: Legacy Output Files Are Not Written

New runs MUST NOT write `logs/stdout.txt`, `logs/stderr.txt`, or `raw/output.json`.

#### Scenario: Canonical output paths only
- WHEN a new run produces stdout, stderr, or terminal output
- THEN stdout and stderr are written only to `.audit/stdout.<attempt>.log` and `.audit/stderr.<attempt>.log`
- AND terminal output is written only to `result/result.json`
- AND legacy `logs/stdout.txt`, `logs/stderr.txt`, and `raw/output.json` are absent

### Requirement: Attempt Audit Files Are History Only

Attempt-scoped audit files under `.audit/` MUST be append-only history and MUST NOT be treated as current truth.

#### Scenario: missing audit logs do not change current state
- **WHEN** an attempt audit log is missing
- **THEN** the system MAY emit diagnostics
- **BUT** it MUST keep `.state/state.json` authoritative for current status

### Requirement: Attempt Audit Skeleton Exists Before Turn Started

The runtime MUST initialize the attempt audit skeleton before emitting `lifecycle.run.started`.

#### Scenario: worker claimed before attempt start
- **WHEN** a worker claims dispatch for attempt N
- **THEN** `.audit/meta.N.json`, `.audit/stdout.N.log`, and `.audit/stderr.N.log` MUST exist before `turn.started`

### Requirement: Run audit MUST include full-lifecycle service log mirror file

每个 run 的 `.audit` MUST 包含 `service.run.log` 作为服务日志全集镜像，覆盖该 run 生命周期内 attempt 内外编排日志。

#### Scenario: run audit pre-creates run-scope service log
- **WHEN** orchestration 完成 run 目录初始化
- **THEN** `.audit/service.run.log` MUST 存在
- **AND** 后续日志追加 MUST 使用该文件作为 run 全集镜像

### Requirement: Attempt audit MUST include service-process log mirror files

每个 run attempt 的 `.audit` 骨架 MUST 包含 `service.<attempt>.log`，用于保存该 run 的服务进程日志镜像。

#### Scenario: attempt audit skeleton pre-creates service log file
- **WHEN** orchestration 初始化 attempt N 的审计骨架
- **THEN** `.audit/service.N.log` MUST 被创建
- **AND** 该文件可在 attempt 执行过程中持续追加

### Requirement: Service log mirror MUST remain run-scoped and history-only

服务日志镜像 MUST 仅包含匹配当前 `run_id`（attempt 分片默认同时匹配 `attempt_number`）的服务日志记录，并且仅作为审计历史，不作为运行状态真相源。

#### Scenario: unscoped logs are excluded from run audit mirror
- **WHEN** 服务日志记录缺失 `run_id` 上下文或 `run_id` 不匹配
- **THEN** 该记录 MUST NOT 写入 `.audit/service.run.log` 或 `.audit/service.<attempt>.log`

#### Scenario: attempt log is subset of run full log
- **GIVEN** run 同时开启 run-scope 与 attempt-scope 镜像
- **WHEN** attempt N 执行期间产生服务日志记录
- **THEN** 记录 MUST 出现在 `.audit/service.run.log`
- **AND** 若记录匹配 attempt N，MUST 同时出现在 `.audit/service.N.log`

### Requirement: Run audit contract MUST be independent from request directories

System MUST keep run audit artifacts rooted in run directory and MUST NOT require request directory snapshots for audit completeness.

#### Scenario: request snapshot persisted from DB payload
- **WHEN** run starts from unified request store
- **THEN** run audit snapshot MUST be derivable from DB request payload
- **AND** audit flow MUST NOT depend on `data/requests/{request_id}`

### Requirement: Unified run observability MUST not expose run_source split

Run observability and replay MUST be keyed by request/run identity only, without installed/temp source branching.

#### Scenario: single observability path for run replay
- **WHEN** client reads run events/chat/history
- **THEN** backend MUST serve unified `/v1/jobs/{request_id}` observability paths
- **AND** response semantics MUST be source-agnostic

### Requirement: Attempt audit skeleton MUST include io_chunks file
attempt 审计骨架 MUST 预创建 `.audit/io_chunks.<attempt>.jsonl`，作为 chunk 级真相源。

#### Scenario: initialize attempt audit skeleton
- **WHEN** orchestration 初始化 attempt 审计骨架
- **THEN** `.audit/io_chunks.<attempt>.jsonl` MUST 已存在
- **AND** 不替代既有 `stdout/stderr` 明文日志文件

### Requirement: Protocol rebuild MUST backup audit files before overwrite
手动重构协议 MUST 在覆盖写回前备份当前审计协议文件。

#### Scenario: rebuild protocol for a run
- **WHEN** 管理端触发 run 协议重构
- **THEN** 系统 MUST 将待覆盖的协议文件备份到 `.audit/rebuild_backups/<timestamp>/attempt-<N>/`
- **AND** 重构失败时原审计文件仍可从备份恢复

