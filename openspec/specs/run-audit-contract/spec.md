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

### Requirement: request_input audit MUST capture first-attempt rendered prompt and effective spawn command
系统 MUST 在 `.audit/request_input.json` 记录首 attempt 的最终渲染 prompt 与实际执行命令信息，用于跨平台排障。

#### Scenario: first-attempt audit preserves native schema dispatch arguments
- **GIVEN** run 正在执行首个 Claude 或 Codex headless attempt
- **AND** internal `run_options` 提供 `__target_output_schema_relpath`
- **WHEN** runtime 完成最终执行命令确定
- **THEN** `.audit/request_input.json` 中的 `spawn_command_original_first_attempt` MUST include the injected native schema flag
- **AND** `spawn_command_effective_first_attempt` MUST include the same schema flag unless command normalization rewrites only the executable wrapper

### Requirement: audit write failures MUST degrade to fallback files without blocking run
当 `.audit/request_input.json` 无法写入时，系统 MUST 降级写入回退审计文件，且不得中断 run 主流程。

#### Scenario: request_input json unavailable
- **GIVEN** `.audit/request_input.json` 缺失、损坏或写入失败
- **WHEN** runtime 执行首 attempt 审计写入
- **THEN** 系统 MUST 以 best-effort 写入 `.audit/prompt.1.txt` 与 `.audit/argv.1.json`
- **AND** run 主流程 MUST continue

### Requirement: Attempt audit MUST preserve quarantined overflow raw lines

Attempt-scoped audit assets MUST preserve the original decoded text of overflowed non-message NDJSON
logical lines in dedicated sidecar files.

#### Scenario: overflow index points to per-line raw sidecar

- **WHEN** runtime quarantines an overflowed non-message NDJSON logical line during attempt `N`
- **THEN** it MUST append a record to `.audit/overflow_index.N.jsonl`
- **AND** that record MUST include `overflow_id`, `attempt_number`, `stream`, `line_start_byte`, `total_bytes`, `sha256`, `disposition`, `diagnostic_code`, `raw_relpath`, `head_preview`, and `tail_preview`
- **AND** the referenced raw sidecar file MUST exist under `.audit/overflow_lines/N/`

#### Scenario: normal hot-path audit files remain sanitized

- **WHEN** runtime quarantines an overflowed non-message NDJSON logical line
- **THEN** `.audit/stdout.N.log`, `.audit/pty-output.N.log`, and `.audit/io_chunks.N.jsonl` MUST continue to store only the sanitized row or diagnostic stub
- **AND** they MUST NOT duplicate the full quarantined raw line body

### Requirement: Prompt-facing output contract Markdown MUST NOT be materialized as a run audit artifact
系统 MUST 保留 canonical machine schema `.json` 作为 run-scoped audit truth，但 MUST NOT 再落盘 prompt-facing output contract Markdown artifact。

#### Scenario: output contract audit assets
- **WHEN** runtime 为 run materialize target output schema
- **THEN** `.audit/contracts/target_output_schema.json` MUST 存在
- **AND** `.audit/contracts/target_output_schema.md` MUST NOT 被创建

#### Scenario: compat output contract audit assets
- **WHEN** 某引擎需要 compat-translated machine schema
- **THEN** compat `.json` artifact MAY 被 materialize
- **AND** compat `.md` prompt artifact MUST NOT 被 materialize

### Requirement: Repair Round Audit History

Each attempt MUST expose a canonical repair-round history file.

#### Scenario: Repair audit tracks parse and schema outcomes
- **WHEN** an attempt enters the output convergence loop
- **THEN** runtime MUST append records to `.audit/output_repair.<attempt>.jsonl`
- **AND** each round record MUST indicate whether deterministic parse repair was applied
- **AND** each round record MUST indicate whether deterministic parse repair succeeded
- **AND** each round record MUST indicate whether schema validation succeeded
- **AND** exhausted or skipped records MUST identify the legacy fallback target

### Requirement: run audit MUST reserve a repair-round history surface
The target audit contract MUST include a dedicated attempt-scoped repair history stream.

#### Scenario: repair-round audit file is canonical target history
- **WHEN** phase 3B emits output-convergence round history
- **THEN** the canonical file MUST be `.audit/output_repair.<attempt>.jsonl`
- **AND** each record MUST be history-only and append-only
- **AND** current runtime MAY leave this file absent until the implementation phase begins

### Requirement: repair audit records MUST follow the attempt/internal-round model
The target repair audit stream MUST reflect the same dual-layer governance model as the machine contract.

#### Scenario: repair round audit includes executor and fallback context
- **WHEN** a repair record is written
- **THEN** it MUST identify the outer `attempt_number`
- **AND** it MUST identify the `internal_round_index`
- **AND** it MUST capture `repair_stage`, `candidate_source`, and any legacy fallback target reached after repair stops

### Requirement: Run audit MAY include engine-compatible schema artifacts without changing canonical truth

Run-scoped audit assets under `.audit/contracts/` MAY include engine-compatible structured-output artifacts as derived transport files, and those artifacts MUST remain subordinate to canonical truth.

#### Scenario: canonical artifacts remain primary while compat artifacts coexist
- **WHEN** runtime materializes an engine-compatible schema or prompt summary artifact
- **THEN** it MUST keep canonical `target_output_schema.json` and `target_output_schema.md` intact
- **AND** the derived compatibility artifacts MUST use distinct filenames under `.audit/contracts/`
- **AND** these derived artifacts MUST be treated as transport/audit assets rather than as replacements for canonical truth

#### Scenario: spawn-command audit remains sufficient to debug injected transport artifact
- **WHEN** the first attempt injects an engine-specific schema CLI argument
- **THEN** existing first-attempt command audit fields in `.audit/request_input.json` MUST remain sufficient to observe which transport artifact or inline schema shape was actually launched
- **AND** runtime MUST NOT require a second structured-output-specific command audit channel for this slice

### Requirement: First-attempt prompt audit MUST record only the assembled skill prompt
系统 MUST 将 `.audit/request_input.json` 中的 `rendered_prompt_first_attempt` 语义收口为首次实际调用引擎时的最终 assembled skill prompt。

#### Scenario: first-attempt prompt audit
- **WHEN** 第一个 attempt 首次实际调用引擎
- **THEN** `rendered_prompt_first_attempt` MUST 记录最终 assembled prompt
- **AND** 该字段 MUST NOT 隐含 run-root instruction file 的文本内容

#### Scenario: prompt audit fallback
- **WHEN** 系统无法回写 `.audit/request_input.json`
- **THEN** `.audit/prompt.1.txt` MUST 记录同一份 assembled prompt

### Requirement: Prompt audit MUST reflect the simplified assembled prompt contract
系统 MUST 继续将 `.audit/request_input.json.rendered_prompt_first_attempt` 视为最终 assembled skill prompt，但该 prompt 不得再依赖被移除的 prompt-builder compatibility context。

#### Scenario: first-attempt prompt is audited
- **WHEN** 系统记录 first-attempt rendered prompt
- **THEN** 它 MUST reflect invoke-line plus body prompt assembly
- **AND** the body MUST come from either skill-declared body text or the shared default body template with optional profile extra blocks

