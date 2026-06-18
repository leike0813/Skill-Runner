# run-file-contract Specification

## Purpose
TBD - created by archiving change complete-runtime-file-contract-cutover-and-scan. Update Purpose after archive.
## Requirements
### Requirement: New Runs Emit Only Canonical Runtime Files

New runs MUST emit only the canonical runtime file layout.

#### Scenario: create-run initializes canonical directories only
- **WHEN** a new run directory is created
- **THEN** it contains `.state/`, `.audit/`, `result/`, `artifacts/`, `bundle/`, and `uploads/`
- **AND** it does not contain `interactions/`, `logs/`, `raw/`, `status.json`, `current/projection.json`, or root `input.json`

### Requirement: Waiting Payload Lives Only In State

Current waiting payload MUST live only inside `.state/state.json`.

#### Scenario: run enters waiting_auth or waiting_user
- **WHEN** the run transitions into `waiting_auth` or `waiting_user`
- **THEN** current waiting data is embedded under `.state/state.json.pending`
- **AND** no `interactions/pending*.json` file exists

### Requirement: New Runs Must Not Emit Legacy Output Files

New runs MUST NOT emit legacy output or mirror files.

#### Scenario: process output is captured for a new run
- **WHEN** attempt logs are written
- **THEN** `.audit/stdout.<attempt>.log` and `.audit/stderr.<attempt>.log` are used
- **AND** `logs/stdout.txt`, `logs/stderr.txt`, and `raw/output.json` are absent

### Requirement: Artifact contract MUST be driven by output artifact-path fields
The system MUST treat output fields marked with `x-type: artifact|file` as the canonical artifact contract.

#### Scenario: terminal result resolves artifact paths
- **WHEN** a run reaches terminal normalization
- **THEN** the system resolves each output artifact-path field to a run-local file
- **AND** rewrites the field to a bundle-relative path

### Requirement: required artifact validation MUST use resolved file existence
The system MUST validate required artifacts by checking the declared output field and the resolved file, rather than a fixed `artifacts/<pattern>` path.

#### Scenario: dynamic file name passes after resolve
- **GIVEN** a required output artifact field points to a real file with a dynamic file name
- **WHEN** terminal validation runs
- **THEN** the run passes artifact validation

### Requirement: ordinary bundles MUST be contract-driven
Non-debug bundles MUST include only `result/result.json` and resolved artifact files.

#### Scenario: uploads and temp files are excluded from normal bundle
- **WHEN** a non-debug bundle is built
- **THEN** uploads and unrelated working files are excluded
- **AND** resolved artifact files are included regardless of whether they live under `artifacts/`

### Requirement: file inputs MUST support declarative uploads-relative paths
File inputs MUST be expressible as `uploads/`-relative paths in `POST /v1/jobs`.

#### Scenario: file input declared as uploads-relative path
- **WHEN** a client submits `input.paper = "papers/a.pdf"`
- **AND** upload zip contains `papers/a.pdf`
- **THEN** runtime resolves the file to the uploaded file and injects its absolute path

#### Scenario: file path omitted falls back to strict-key compatibility
- **WHEN** a file input key is not explicitly provided in the request body
- **THEN** runtime MAY still resolve `uploads/<input_key>` as a compatibility fallback

### Requirement: run 工作目录结果文件 MUST 可作为终态输出恢复来源

当 run 已成功执行但主路径结构化输出缺失或非法时，系统 MUST 能从 run 工作目录内恢复结果文件，而不依赖 `result/result.json` 或审计目录。

#### Scenario: default result filename is discovered under run workspace
- **GIVEN** skill 未声明自定义结果文件名
- **AND** `run_dir` 子树中存在 `<skill-id>.result.json`
- **WHEN** 主路径结构化输出失败且 lifecycle 进入结果恢复
- **THEN** 系统必须将该文件视为候选结果文件

#### Scenario: declared result filename overrides default
- **GIVEN** `runner.json.entrypoint.result_json_filename` 声明了非空字符串
- **WHEN** lifecycle 扫描 run 工作目录
- **THEN** 系统必须只按该文件名匹配候选结果文件
- **AND** 不再使用默认 `<skill-id>.result.json`

#### Scenario: multiple candidate result files choose latest mtime
- **GIVEN** `run_dir` 内存在多个同名候选结果文件
- **WHEN** lifecycle 选择最终恢复来源
- **THEN** 系统必须优先选择 `mtime` 最新的文件
- **AND** 若 `mtime` 相同，则按浅层路径优先
- **AND** 结果必须记录 `OUTPUT_RESULT_FILE_MULTIPLE_CANDIDATES`

#### Scenario: audit and terminal result directories are excluded
- **GIVEN** `.audit/` 或 `result/` 下存在同名 JSON 文件
- **WHEN** lifecycle 扫描候选结果文件
- **THEN** 这些文件不得参与候选选择

### Requirement: New runner-owned terminal results MUST use actual result path
New runs SHALL write the runner-owned terminal result to the run's persisted `resultJsonPath`.

#### Scenario: New run writes namespaced result
- **WHEN** a new logical run is allocated namespace `<safeSkillId>.<n>`
- **THEN** its terminal result is written to `result/<safeSkillId>.<n>/result.json`
- **AND** callers MUST read the persisted actual result path rather than deriving `result/result.json`

#### Scenario: Legacy result path remains readable
- **GIVEN** a historical run has no persisted actual result path
- **WHEN** a caller reads the result
- **THEN** the system may fall back to `result/result.json`

### Requirement: New input manifests MUST use actual input manifest path
New runs SHALL write the runner-owned input manifest to the run's persisted `inputManifestPath`.

#### Scenario: New run writes namespaced input manifest
- **WHEN** a new logical run is allocated namespace `<safeSkillId>.<n>`
- **THEN** its runner-owned input manifest is written to `.audit/<safeSkillId>.<n>/input_manifest.json`

### Requirement: Package-owned result fallback MUST ignore runner-owned namespaces
Package-owned result fallback discovery SHALL exclude runner-owned result and audit subtrees.

#### Scenario: Fallback ignores runner-owned files
- **WHEN** lifecycle scans a workspace for a package-owned fallback result file
- **THEN** files under `result/` and `.audit/` do not participate in candidate selection

### Requirement: Skill run feedback sidecar MUST be optional and result-local

The system SHALL treat `_skill_run_feedback.md` as an optional Markdown sidecar located in the same directory as the actual terminal `result.json`.

#### Scenario: successful run may produce feedback
- **WHEN** a run succeeds and its actual result path is `result/<namespace>/result.json`
- **THEN** the agent may write `result/<namespace>/_skill_run_feedback.md`
- **AND** the file MUST NOT be required by output schema
- **AND** the file MUST NOT be added to `result.json`

#### Scenario: non-success routes do not require feedback
- **WHEN** a run fails, is canceled, is pending, or is waiting for user input
- **THEN** the feedback sidecar MUST NOT be required
- **AND** absence of the sidecar MUST NOT affect that route

#### Scenario: feedback sidecar diagnostics do not change terminal status
- **WHEN** a successful run has missing, empty, or unreadable feedback sidecar state
- **THEN** the system records diagnostic logs only
- **AND** the run remains succeeded

### Requirement: Normal bundles MUST include present feedback sidecars

Normal run bundles SHALL include `_skill_run_feedback.md` when the file exists beside an included terminal `result.json`.

#### Scenario: namespaced feedback sidecar is bundled
- **WHEN** a bundle is built and `result/<namespace>/_skill_run_feedback.md` exists beside `result/<namespace>/result.json`
- **THEN** the bundle includes `result/<namespace>/_skill_run_feedback.md`
- **AND** existing business artifacts and result layout are unchanged

#### Scenario: legacy feedback sidecar is bundled
- **WHEN** a legacy run has `result/_skill_run_feedback.md` beside `result/result.json`
- **THEN** the bundle includes `result/_skill_run_feedback.md`


### Requirement: New request-bound runs MUST use workspace_dir as file root

New request-bound runs MUST use the persisted physical `workspace_dir` as the root for runner-owned files.

#### Scenario: New run allocates workspace root
- **WHEN** a non-reuse request creates a run
- **THEN** the backend creates `data/workspaces/<workspace_id>`
- **AND** `workspace_id` defaults to the new `run_id`
- **AND** the backend does not create `data/runs/<run_id>`.

#### Scenario: Reuse run inherits workspace root
- **GIVEN** a source request completed successfully with persisted workspace metadata
- **WHEN** a later request uses `runtime_options.workspace.mode = "reuse"`
- **THEN** the new logical run receives a new `run_id`
- **AND** it reuses the source request's `workspace_id` and `workspace_dir`
- **AND** no symlink is created under `data/runs/<new_run_id>`.

### Requirement: Runner-owned files MUST remain namespace-owned

Runner-owned files in a shared workspace MUST use the request's persisted namespace.

#### Scenario: Contracts are namespaced
- **WHEN** output schema contracts are materialized for a request-bound run
- **THEN** `target_output_schema.json` is written under `.audit/<namespace>/contracts/`
- **AND** engine-specific compatible schema artifacts are written in the same contracts directory.

#### Scenario: Bundles are namespaced
- **WHEN** a request-bound bundle is generated
- **THEN** bundle files and manifests are written under `bundle/<namespace>/`
- **AND** root `bundle/run_bundle*.zip` is not current truth for that run.

### Requirement: Legacy run dirs MUST remain readable as fallback

Historical no-layout records MUST remain readable through `data/runs/<run_id>` fallback.

#### Scenario: Legacy record has no workspace metadata
- **GIVEN** a run record has no persisted `workspace_dir`
- **WHEN** a read path resolves its files
- **THEN** the backend may fall back to `data/runs/<run_id>`.

### Requirement: Request-bound state files MUST use run-owned namespace

Request-bound run state and dispatch files MUST use the persisted workspace namespace whenever layout metadata exists.

#### Scenario: Queued and running state use namespaced state files
- **WHEN** a request-bound run is initialized, admitted, scheduled, claimed, or marked running
- **THEN** the backend writes `.state/<namespace>/state.json`
- **AND** dispatch phase writes `.state/<namespace>/dispatch.json`
- **AND** root `.state/state.json` is not updated as current truth for that request-bound run.

#### Scenario: Queued initialization refetches layout after request binding
- **GIVEN** a request was bound to a run after an earlier request record was loaded
- **WHEN** queued state is initialized with that stale request record
- **THEN** the backend refetches the bound request metadata before resolving state paths
- **AND** initialization still writes `.state/<namespace>/state.json` and `.state/<namespace>/dispatch.json`.

#### Scenario: Interaction and auth callbacks update namespaced state
- **WHEN** reply, auth selection, auth input, auth import, auth status reconciliation, or auth timeout updates current status for a request-bound run
- **THEN** the update targets `.state/<namespace>/state.json`
- **AND** root `.state/state.json` is only used when no layout metadata exists.

### Requirement: Package-owned fallback scans MUST not confuse runner-owned namespace files

Fallback scans for package-owned outputs SHALL keep runner-owned state, audit, and result namespaces separate from package-owned artifacts.

#### Scenario: Result fallback excludes runner-owned namespaces
- **WHEN** lifecycle scans a workspace for package-owned fallback output
- **THEN** files under `result/`, `.state/`, and `.audit/` are not treated as package-owned output candidates.

### Requirement: Request-bound bundles MUST use run-owned namespace

Request-bound bundle zip files and manifests MUST use the persisted workspace namespace whenever layout metadata exists.

#### Scenario: Bundle generation writes namespaced bundle files
- **WHEN** a request-bound run with namespace `<safeSkillId>.<n>` succeeds
- **THEN** the backend writes `bundle/<safeSkillId>.<n>/run_bundle.zip`
- **AND** debug bundle generation writes `bundle/<safeSkillId>.<n>/run_bundle_debug.zip`
- **AND** the corresponding manifests are written in that same bundle namespace directory
- **AND** root `bundle/run_bundle*.zip` is not updated as current truth for that request-bound run.

#### Scenario: Bundle collection only includes the current namespace
- **GIVEN** a reused workspace contains multiple result namespaces
- **WHEN** the caller downloads a bundle for one request
- **THEN** the bundle includes that request's actual `resultJsonPath`
- **AND** it may include `_skill_run_feedback.md` from the same result directory
- **AND** it may include artifacts referenced by that result payload
- **AND** it does not include result, audit, state, feedback, or artifact files solely owned by another namespace.

### Requirement: State files MUST NOT be current request-bound artifacts

New request-bound runs MUST NOT rely on `.state/<namespace>/state.json` or `.state/<namespace>/dispatch.json` as current runner-owned state artifacts.

#### Scenario: Request-bound lifecycle writes state
- **WHEN** a request-bound run transitions state or dispatch phase
- **THEN** the backend writes `request_run_state`, `request_current_projection`, and/or `request_dispatch_state`
- **AND** it does not create `.state/<namespace>/state.json`
- **AND** it does not create `.state/<namespace>/dispatch.json`.

#### Scenario: Legacy state files exist
- **GIVEN** legacy `.state` files exist in a workspace
- **WHEN** a request-bound API reads current state
- **THEN** those files are treated as diagnostic/legacy data only.
