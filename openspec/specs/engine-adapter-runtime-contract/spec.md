# engine-adapter-runtime-contract Specification

## Purpose
定义执行适配器（adapter）的运行时契约、目录边界与扩展方式，确保引擎差异可管理、可验证、可扩展，同时避免回归到单体大类实现。
## Requirements
### Requirement: Adapter MUST 提供统一运行时命令构建接口
系统 MUST 为所有引擎 Adapter 提供统一的命令构建契约，至少覆盖 start 与 resume 两类执行入口，并允许调用方显式指定是否启用 API 默认 Profile 参数。

#### Scenario: API 链路构建 start 命令
- **WHEN** 后端 API 编排层请求构建某引擎 start 命令且声明启用 Profile
- **THEN** Adapter 返回可执行命令数组并应用该引擎 Profile 默认参数

#### Scenario: Harness 链路构建 start 命令
- **WHEN** Harness 请求构建某引擎 start 命令且声明禁用 Profile
- **THEN** Adapter 返回仅基于透传参数与必要上下文的命令数组

### Requirement: Adapter MUST 提供统一 runtime 流解析接口

系统 MUST 要求所有引擎 Adapter 提供 runtime 流解析接口，输出统一结构字段（parser、confidence、session_id、assistant_messages、raw_rows、diagnostics、structured_types），并暴露可供 auth detection 使用的原始材料。

#### Scenario: Claude `type=result` defaults to completion-only semantics

- **GIVEN** Claude runtime stream contains a terminal `{"type":"result"}` row
- **WHEN** adapter 解析该 runtime 流
- **THEN** 该 `result` 行 MUST 继续产出 turn completion 语义与 completion metadata
- **AND** `result.result` MUST NOT 默认进入 `assistant_messages`

#### Scenario: Claude `result.result` may become a fallback assistant message only in narrow conditions

- **GIVEN** Claude runtime stream contains a terminal `{"type":"result"}` row
- **AND** 当前 turn 没有真实 assistant body message
- **AND** 该 `result` 行没有 `structured_output`
- **AND** `result.result` 非空
- **WHEN** adapter 解析该 runtime 流
- **THEN** adapter MAY 产出一条 fallback assistant message
- **AND** 该消息 MUST 带有 `details.source = "claude_result_fallback"`

### Requirement: Adapter MUST 暴露 chunk 级运行时输出
系统 MUST 允许 adapter 在子进程执行过程中逐 chunk 暴露 stdout/stderr，以支撑 live protocol publish。

#### Scenario: chunk output is forwarded to the live emitter
- **WHEN** adapter 从运行中的引擎进程读到 stdout 或 stderr chunk
- **THEN** MUST 先交给 live runtime emitter
- **AND** 不能等到事后 audit 重建才对外可见

### Requirement: Stream parser MUST 支持 live session
系统 MUST 提供 parser live session 合同，使引擎 parser 可以在执行期间增量吐出语义事件。

#### Scenario: parser session emits semantic output before audit materialization
- **WHEN** parser 已识别出完整 assistant / diagnostic 语义
- **THEN** 它 MUST 能通过 live session 立即产出 emission
- **AND** batch parse 仅作为 backfill / parity / cold replay 路径保留

### Requirement: Engine-specific adapter 实现 MUST 按引擎聚合
系统 MUST 将 engine-specific adapter 代码放置在 `server/engines/<engine>/adapter/*`，并通过 execution adapter class 装配到执行注册表。

#### Scenario: 注册引擎适配器入口
- **WHEN** 系统初始化 `EngineAdapterRegistry`
- **THEN** 适配器实例来源为 `server/engines/<engine>/adapter/execution_adapter.py` 中的 class
- **AND** MUST NOT 依赖 `entry.py` 工厂或 `build_adapter()` 历史入口

### Requirement: Adapter 组件契约 MUST 标准化
系统 MUST 提供 adapter 组件契约，以约束配置、环境、提示词、命令、解析与会话句柄能力边界。

#### Scenario: 新引擎接入
- **WHEN** 新增一个引擎适配器
- **THEN** 实现方按统一组件契约实现
- **AND** 不需要复制粘贴完整历史 adapter 大类

### Requirement: Legacy 单体 adapter 文件 MUST NOT 存在于运行路径
系统在 commonization 收口后 MUST NOT 依赖或保留旧单体 adapter 路径作为运行实现。

#### Scenario: 旧文件清理
- **WHEN** 扫描适配器实现路径
- **THEN** `server/engines/*/adapter/adapter.py` 不存在
- **AND** `server/adapters/base.py` 不存在

### Requirement: Engine adapter 目录中的旧组件文件 MUST NOT 保留
系统 MUST 将 prompt/session/workspace 的共性实现统一到 runtime common，禁止在每个引擎目录重复保留同类组件文件。

#### Scenario: 目录结构检查
- **WHEN** 扫描 `server/engines/<engine>/adapter/`
- **THEN** 不存在 `entry.py`
- **AND** 不存在 `prompt_builder.py`
- **AND** 不存在 `session_codec.py`
- **AND** 不存在 `workspace_provisioner.py`

### Requirement: Runtime common 组件 MUST 承载引擎无关高重复逻辑

跨引擎高重复逻辑 MUST 位于 `server/runtime/adapter/common/*`，引擎目录仅保留差异实现。

#### Scenario: Prompt/session/validation 逻辑复用
- **WHEN** 四引擎装配 PromptBuilder、SessionCodec 与 per-attempt run-folder validation
- **THEN** 共性步骤来自 runtime common
- **AND** 引擎仅通过 profile 与少量差异参数定制

### Requirement: Prompt/Session/Workspace MUST 由 Adapter Profile 驱动

`PromptBuilder`、`SessionHandleCodec`、`AttemptRunFolderValidator` MUST 由 profile 驱动的 runtime/common 组件实现。

#### Scenario: 执行适配器初始化
- **WHEN** 任一引擎 execution adapter 初始化
- **THEN** 使用 `ProfiledPromptBuilder`、`ProfiledSessionCodec`、`ProfiledAttemptRunFolderValidator`
- **AND** profile 来源为 `server/engines/<engine>/adapter/adapter_profile.json`

### Requirement: Adapter Profile 校验 MUST fail-fast
adapter profile 校验失败 MUST 在 registry 初始化阶段直接报错并阻止服务进入可运行状态。

#### Scenario: profile 非法
- **WHEN** 任一引擎 `adapter_profile.json` 缺失必填字段或枚举非法
- **THEN** `EngineAdapterRegistry` 初始化失败
- **AND** 服务不得进入可运行状态

### Requirement: Adapter Profile MUST 声明引擎执行资产路径

每个引擎 adapter profile MUST 承载配置资产、attempt workspace 布局与模型目录元信息，作为执行期单一来源。

#### Scenario: config composer 读取资产
- **WHEN** adapter 构建运行时配置
- **THEN** `bootstrap/default/enforced/schema/skill-defaults` 路径来自 profile 字段
- **AND** composer 不再硬编码 `assets/configs/<engine>/*` 路径

#### Scenario: validator 读取 attempt workspace 布局
- **WHEN** adapter 校验当前 attempt 的 run folder
- **THEN** attempt workspace 根目录与 skills 根目录来自 profile 的 `attempt_workspace` 字段
- **AND** `attempt_workspace` 仅描述布局，不描述 skill 安装策略

### Requirement: engine skill config resolution MUST be declarative-first with fixed fallback
Engine adapters MUST resolve skill-specific config assets from `runner.json.engine_configs` first, then fall back to the engine's canonical fixed filename.

#### Scenario: declared engine config missing and fallback exists
- **GIVEN** `runner.json.engine_configs.opencode` points to an invalid or missing file
- **AND** `assets/opencode_config.json` exists
- **THEN** runtime MUST use the fallback file
- **AND** runtime MUST log the fallback decision without surfacing a user-facing warning

#### Scenario: declared engine config missing and fallback absent
- **GIVEN** `runner.json.engine_configs.codex` cannot be resolved
- **AND** `assets/codex_config.toml` does not exist
- **THEN** runtime MUST continue without skill-specific engine defaults

### Requirement: Services MUST be domain-organized in phase1
系统 MUST 将 `server/services` 按域分包（orchestration/skill/ui/platform），并停止继续新增扁平 services 模块。

#### Scenario: Service module placement
- **WHEN** 新增服务模块
- **THEN** 模块路径必须位于对应域子包
- **AND** 不允许新增根级 `server/services/*.py` 业务实现文件

### Requirement: Runtime MUST be the only Run Core implementation layer
系统 MUST 将 Run Core 逻辑收敛到 `server/runtime/*`，phase1 不允许新增 `server/services/run/*`。

#### Scenario: Run core placement
- **WHEN** 实现运行时协议、状态机、事件物化与运行观测能力
- **THEN** 代码必须位于 `server/runtime/*`
- **AND** `server/services` 仅允许 façade/兼容导入层

### Requirement: Runtime adapter common MUST NOT depend on flat services modules
`server/runtime/adapter/common/*` MUST 不再直接依赖扁平 services 模块。

#### Scenario: Adapter common imports
- **WHEN** 检查 `server/runtime/adapter/common/*` import
- **THEN** 不出现 `server.services.<flat_module>` 引用

### Requirement: Runtime modules MUST not directly import orchestration singletons
`server/runtime/**` MUST 通过 contracts/ports 与 orchestration 协作，不得直接依赖 `server/services/orchestration/*`。

#### Scenario: Runtime boundary guard
- **WHEN** 检查 runtime 模块依赖
- **THEN** 不存在 `from server.services.orchestration...` 或等价直接导入
- **AND** runtime 仅依赖 runtime contracts 与注入端口

### Requirement: Runtime execution business modules MUST live in orchestration
`run_execution_core` 与 `run_interaction_service` 作为业务编排模块 MUST 位于 `services/orchestration`。

#### Scenario: Execution module ownership
- **WHEN** 扫描运行执行核心模块
- **THEN** `server/runtime/execution/` 下不再存在上述业务实现文件
- **AND** 等价实现位于 `server/services/orchestration/`

### Requirement: Legacy compatibility imports MUST be removed in phase2
phase2 后，adapter/runtime 相关旧路径兼容导入层 MUST NOT 存在。

#### Scenario: Compatibility layer cleanup
- **WHEN** 完成 phase2 收口
- **THEN** 不存在仅用于兼容旧路径的 re-export 模块
- **AND** 全仓引用均指向新目录结构

### Requirement: Trust strategy MUST be adapter-local and centrally dispatched
run folder trust 策略 MUST 以引擎 adapter 层实现，并由 orchestration trust manager 统一调度。

#### Scenario: Adapter-local trust strategy placement
- **WHEN** 为引擎实现 run folder trust
- **THEN** codex 与 gemini 策略分别位于 `server/engines/codex/adapter/trust_folder_strategy.py` 与 `server/engines/gemini/adapter/trust_folder_strategy.py`
- **AND** `server/services/orchestration/run_folder_trust_manager.py` 内部不出现 `if engine == ...` 分支
- **AND** 未注册策略引擎自动使用 registry 内置 noop fallback

### Requirement: Legacy orchestration compatibility shells MUST NOT exist
phase2 收口后，orchestration 目录中的兼容壳文件 MUST 被删除。

#### Scenario: Compatibility shell cleanup
- **WHEN** 完成 phase2 增量收口
- **THEN** 以下文件不存在：
  - `server/services/orchestration/codex_config_manager.py`
  - `server/services/orchestration/config_generator.py`
  - `server/services/orchestration/opencode_model_catalog.py`

### Requirement: Adapter MUST separate per-attempt validation from run-scope skill materialization

系统 MUST 将 per-attempt run-folder validation 与 create-run skill materialization 分离。

#### Scenario: Non-reply attempt validates existing run folder
- **WHEN** start 或 non-reply resumed attempt 准备启动引擎进程
- **THEN** adapter MUST 先生成或确认本次 attempt 的 config
- **AND** MUST 校验已解析的 run folder 满足最小执行合同
- **AND** MUST NOT 在该路径执行 skill reinstall、recopy、unpack 或 patch

#### Scenario: auth-completed resume re-runs config and validation only
- **GIVEN** 一个 run 已进入 `waiting_auth` 并完成鉴权
- **WHEN** auth-completed resumed attempt 开始
- **THEN** adapter MAY 重新执行 config compose 与 run-folder validation
- **AND** MUST 直接复用已有 run-local skill snapshot

#### Scenario: validator detects snapshot drift and hard-fails
- **GIVEN** 当前 attempt 的 run-local skill snapshot 缺失 `SKILL.md`、`assets/runner.json`、schema 文件或 config 文件
- **WHEN** `AttemptRunFolderValidator` 校验 run folder
- **THEN** 该 attempt MUST 失败
- **AND** 系统 MUST NOT 进行隐式修复或 fallback source selection

### Requirement: Adapter MUST consume orchestration-resolved manifests only

adapter/runtime common MUST 将传入的 `SkillManifest` 视为 orchestration 已解析的 canonical source。

#### Scenario: Adapter does not reopen source selection
- **GIVEN** orchestration 已为当前 attempt 解析 canonical `SkillManifest`
- **WHEN** adapter/runtime common 准备执行
- **THEN** adapter MUST 直接消费该 manifest
- **AND** MUST NOT 重新在 registry、temp staging 或 `skill_override` 之间进行选择

### Requirement: Adapters MUST expose chunk-level runtime output during execution
The system MUST require runtime adapters to expose stdout/stderr chunks while the subprocess is still running, so the protocol layer can publish live events without waiting for post-hoc audit reconstruction.

#### Scenario: chunk output is forwarded to the live emitter
- **WHEN** the adapter reads a stdout or stderr chunk from a running engine process
- **THEN** it MUST forward that chunk to the live runtime emitter before process completion

### Requirement: Stream parsers MUST support incremental live parsing

The system MUST provide a live parser session contract so engine-specific parsers can emit semantic events incrementally during execution.

#### Scenario: overflowed non-message NDJSON line is repaired before semantic parsing

- **WHEN** a live NDJSON parser session observes a single logical line whose buffered size exceeds `4096` bytes before the terminating newline
- **AND** that logical line is not semantically classified as `agent.reasoning` or `agent.message`
- **THEN** it MUST stop retaining the full raw body in live memory
- **AND** it MUST attempt to repair the retained prefix into a valid JSON object when that line terminates or the process exits
- **AND** if repair succeeds, it MUST continue semantic parsing from the repaired object instead of dropping the line

#### Scenario: agent reasoning or message NDJSON line bypasses live truncation guard

- **WHEN** a live NDJSON parser session observes a logical line that is semantically classified as `agent.reasoning` or `agent.message`
- **AND** that line exceeds `4096` bytes before the terminating newline
- **THEN** the shared live buffer MUST NOT truncate or substitute that logical line solely because of the `4096` byte limit
- **AND** the engine-specific live parser MUST continue its normal semantic extraction from the full logical line

### Requirement: Batch parse MUST remain secondary and backfill-only
The system MAY retain batch parse utilities for backfill, cold replay, and parity testing, but MUST NOT use batch materialization as the live-authoritative source for SSE.

#### Scenario: active SSE does not require batch materialization
- **WHEN** an active run has published live events
- **THEN** the SSE path MUST serve those events directly
- **AND** MUST NOT invoke batch FCMP/RASP materialization as a prerequisite

### Requirement: Live parser emission order MUST define canonical RASP order

系统 MUST 将 live parser session 的 emission 顺序定义为 canonical RASP 顺序；audit mirror、batch backfill 和 replay 路径 MUST NOT 改写该顺序。

#### Scenario: repaired overflow warnings precede repaired semantic events

- **WHEN** a long NDJSON line is repaired and yields both a diagnostic warning and one or more semantic emissions
- **THEN** the warning emission MUST be published before the repaired semantic emissions for that same line
- **AND** subsequent rows MUST retain their original live order after that repaired line

### Requirement: Parser-originated FCMP MUST be produced as candidates before publication
系统 MUST 先把 parser-originated FCMP 构造成 candidate，再交给顺序 gate 决定是否发布。

#### Scenario: parser does not publish FCMP directly
- **WHEN** parser 识别出 assistant 或 diagnostic 语义
- **THEN** 它 MUST 先产出可被 gate 消费的 candidate
- **AND** MUST NOT 直接绕过 gate 发布 FCMP

### Requirement: Parser-originated FCMP MUST derive from incremental emissions without retroactive reordering
系统 MUST 从 parser 的增量 emission 派生 parser-originated FCMP，且 MUST NOT 允许事后 batch rebuild 重新定义它们在 active run 中的相对顺序。

#### Scenario: live parser FCMP is not overwritten by batch backfill
- **WHEN** parser live session 已发布某条 assistant 或 diagnostic FCMP
- **THEN** batch parse/backfill MAY 作为 parity 或 fallback 使用
- **AND** MUST NOT 覆盖该 FCMP 在 active timeline 中的相对顺序

### Requirement: Live parser emissions MUST expose stable correlation anchors
系统 MUST 要求 live parser emission 为派生的 FCMP/RASP 提供稳定的关联锚点，以支撑跨流因果回溯。

#### Scenario: FCMP and RASP share publish correlation
- **WHEN** 同一 parser emission 同时派生出 FCMP 和 RASP
- **THEN** 两者 MUST 共享稳定的 `publish_id`
- **AND** 后续依赖事件 MAY 通过 `caused_by.publish_id` 建立因果关系

### Requirement: Runtime auth session snapshots MUST distinguish credential observability from completion
runtime auth session snapshot MUST 将静态凭据观测与 auth session completion 彻底解耦。

#### Scenario: credential presence does not imply completed session
- **WHEN** engine 本地凭据已经存在
- **AND** auth session 仍在 challenge-active
- **THEN** runtime auth snapshot MUST NOT 被视为 completed
- **AND** MUST NOT 触发 `auth.completed`

### Requirement: Runtime auth handlers MUST not expose readiness as completion semantics
adapter/runtime auth handlers MUST NOT 再以 readiness-like 字段表达 session completion。

#### Scenario: terminal success is explicit
- **WHEN** auth session 被标记为 `succeeded` 或 `completed`
- **THEN** 该状态 MUST 来自显式 completion path
- **AND** MUST NOT 来自凭据存在性推断

### Requirement: Adapter MUST 通过统一进程治理注册并释放 run attempt 进程
运行时 adapter 在创建引擎子进程后 MUST 注册 lease，并在任意退出路径 release；取消执行 MUST 通过统一终止器。

#### Scenario: 正常完成释放 lease
- **WHEN** run attempt 正常结束
- **THEN** 对应 lease 状态变为 closed

#### Scenario: 取消执行统一终止
- **WHEN** 收到取消请求
- **THEN** adapter 使用统一终止器处理进程树
- **AND** lease 最终关闭

### Requirement: Platform cache fingerprint SHALL resolve engine defaults via adapter profile
`cache_key_builder` MUST 使用 adapter profile 的 `config_assets.skill_defaults_path`，并且 MUST NOT 再硬编码 engine 默认配置文件名。

#### Scenario: 计算技能指纹
- **WHEN** 平台为指定 engine 计算 skill fingerprint
- **THEN** 默认配置文件路径来自 adapter profile
- **AND** 平台层不包含 engine 文件名分支

### Requirement: Runtime adapter profile loader SHALL use unified engine catalog
Runtime adapter profile loader MUST read supported engines from a unified engine catalog source, and MUST NOT maintain a local hard-coded engine source-of-truth.

#### Scenario: 引擎列表更新
- **WHEN** 统一 engine catalog 增减 engine
- **THEN** profile loader 使用更新后的列表
- **AND** 无需同步修改本地硬编码引擎常量

### Requirement: Protocol history queries MUST preserve live responsiveness for active runs

The system MUST avoid routing running protocol history requests through heavyweight audit reindex and full-file reads when a live journal already exists for the current attempt.

#### Scenario: running current-attempt FCMP history uses live-first hot path

- **WHEN** a `protocol/history` query requests `stream=fcmp` for a run whose status is `queued` or `running`
- **AND** the resolved attempt equals the current attempt
- **THEN** the service MUST return the FCMP history from the live journal hot path
- **AND** it MUST NOT require audit JSONL reads before returning
- **AND** it MUST NOT trigger FCMP global reindex on that hot path

#### Scenario: running current-attempt RASP history uses live-first hot path

- **WHEN** a `protocol/history` query requests `stream=rasp` for a run whose status is `queued` or `running`
- **AND** the resolved attempt equals the current attempt
- **THEN** the service MUST return the RASP history from the live journal hot path
- **AND** it MUST NOT require audit JSONL reads before returning

#### Scenario: non-current or terminal history keeps audit semantics

- **WHEN** a `protocol/history` query targets a terminal run or a non-current attempt
- **THEN** the service MAY continue using the existing audit-backed history path
- **AND** it MUST preserve the existing `protocol/history` response shape

### Requirement: Protocol history changes MUST NOT alter UI-facing stream contracts

The system MUST preserve existing UI and protocol contracts while optimizing the running hot path.

#### Scenario: running live-first history preserves response shape

- **WHEN** a running current-attempt FCMP or RASP history request is served from the live-first hot path
- **THEN** the response MUST still include `attempt`, `available_attempts`, `events`, `cursor_floor`, and `cursor_ceiling`
- **AND** it MUST remain compatible with the existing run detail UI polling logic without frontend changes

### Requirement: Runtime stream text views MUST preserve UTF-8 decoding integrity across chunk boundaries

The system MUST preserve the textual meaning of raw runtime bytes when converting `stdout` / `stderr` chunks into log text and live parser input.

#### Scenario: execution stream decoding preserves split multibyte UTF-8 characters

- **WHEN** the runtime reads `stdout` or `stderr` in multiple raw byte chunks
- **AND** a valid UTF-8 multibyte character is split across chunk boundaries
- **THEN** `stdout/stderr.log` MUST decode that character correctly
- **AND** the live parser input text MUST match the same once-decoded UTF-8 replacement text
- **AND** the system MUST NOT inject extra replacement characters solely because of chunk boundaries

#### Scenario: execution stream decoding still replaces genuinely invalid bytes

- **WHEN** the runtime reads raw bytes that are not valid UTF-8
- **THEN** the text view MAY include replacement characters
- **AND** those replacements MUST correspond only to genuinely invalid byte sequences

### Requirement: Strict replay MUST reconstruct the same UTF-8 text truth as live execution

The system MUST decode `io_chunks` for strict replay using the same incremental UTF-8 semantics as the live execution path.

#### Scenario: strict replay preserves split multibyte UTF-8 characters

- **WHEN** strict replay rebuilds text from `io_chunks`
- **AND** a valid UTF-8 multibyte character is split across multiple stored chunks
- **THEN** the replay rows' `text` MUST match the once-decoded UTF-8 replacement text of the original byte stream
- **AND** replay MUST NOT reintroduce chunk-boundary replacement drift

#### Scenario: byte references remain anchored to raw bytes

- **WHEN** the runtime exposes `raw_ref.byte_from` and `raw_ref.byte_to`
- **THEN** those byte ranges MUST remain anchored to the original raw byte stream
- **AND** this change MUST NOT alter the `io_chunks` byte SSOT or its file format

### Requirement: Runtime raw stream ingestion MUST preserve canonical protocol progress

系统 MUST 保证 runtime 对 subprocess stdout/stderr 的采集不会因为超长 NDJSON 单行而破坏后续协议推进。

#### Scenario: oversized non-message NDJSON stdout line is sanitized before audit persistence

- **WHEN** an NDJSON engine emits a single stdout logical line whose size exceeds `4096` bytes before the terminating newline
- **AND** that logical line is not semantically classified as `agent.reasoning` or `agent.message`
- **THEN** runtime ingress MUST stop retaining that line's full original body in live parser memory
- **AND** it MUST sanitize the retained prefix into either a repaired JSON line or a runtime diagnostic JSON line before writing to the normal runtime audit hot path
- **AND** the original oversized body MUST NOT be written to `io_chunks` or `stdout.log`

#### Scenario: oversized non-message line is quarantined into sidecar audit assets

- **WHEN** runtime ingress sanitizes or substitutes an oversized non-message NDJSON logical line
- **THEN** it MUST preserve the original decoded logical line in a dedicated overflow sidecar raw file
- **AND** it MUST append an attempt-scoped overflow index record pointing to that raw file
- **AND** downstream parser/live publication MUST continue consuming only the sanitized row or diagnostic stub

### Requirement: Sanitized overflow handling MUST preserve business semantics when possible

系统 MUST 优先保住超长 NDJSON 行的业务语义，而不是保留完整中间正文。

#### Scenario: oversized tool_result line is repaired into valid JSON

- **WHEN** an oversized NDJSON line can be repaired into a valid JSON object from its retained prefix
- **THEN** runtime MUST emit that repaired JSON line as the sanitized raw row
- **AND** downstream engine-specific parsers MUST continue normal semantic extraction from that repaired object
- **AND** runtime MUST emit a diagnostic warning with code `RUNTIME_STREAM_LINE_OVERFLOW_SANITIZED`
- **AND** the overflow sidecar index record MUST mark the quarantined row as `sanitized`

#### Scenario: unrecoverable oversized line is substituted with runtime diagnostic JSON

- **WHEN** an oversized NDJSON line cannot be repaired into a valid JSON object
- **THEN** runtime MUST substitute a runtime diagnostic JSON line in place of the original row
- **AND** runtime MUST emit a diagnostic warning with code `RUNTIME_STREAM_LINE_OVERFLOW_DIAGNOSTIC_SUBSTITUTED`
- **AND** the overflow sidecar index record MUST mark the quarantined row as `substituted`
- **AND** later logical lines in the same stream MUST continue normal runtime parsing and publication

### Requirement: Runtime audit writing MUST NOT block the single-worker execution hot path

The system MUST ensure that runtime audit persistence does not synchronously block the main chunk-processing path of active runs.

#### Scenario: active run output is mirrored through background audit writers

- **WHEN** the runtime reads `stdout` / `stderr` chunks from an active subprocess
- **THEN** `stdout.log` / `stderr.log` / `io_chunks` MUST be persisted through background serial writers
- **AND** FCMP / RASP / chat replay audit mirrors MUST NOT perform per-event synchronous file writes on the main event loop hot path

#### Scenario: audit backpressure does not block live protocol publication

- **WHEN** an audit writer queue reaches its bounded capacity
- **THEN** the runtime MAY drop audit writes for that writer
- **AND** the system MUST continue prioritizing live journal publication and core protocol progression

### Requirement: Runtime auth detection MUST use low-frequency bounded windows

The system MUST avoid re-parsing the full accumulated runtime output on a high-frequency cadence while a run is active.

#### Scenario: active auth detection probes only recent output windows

- **WHEN** auth detection is enabled for an active run
- **THEN** the runtime MUST probe only recent bounded `stdout` / `stderr` windows
- **AND** it MUST NOT rebuild auth detection input by repeatedly joining the full historical output

#### Scenario: auth detection cadence is throttled

- **WHEN** a run is actively streaming output
- **THEN** auth detection probes MUST be throttled to a lower-frequency cadence than the previous `0.25s` path
- **AND** the runtime MUST still perform one final forced probe before process completion handling finishes

### Requirement: Slot release MUST remain decoupled from audit drain completion

The system MUST preserve current concurrency capacity semantics when introducing asynchronous audit writing.

#### Scenario: slot release does not wait for full audit drain

- **WHEN** the subprocess for a run attempt has exited and stream readers have completed
- **THEN** run slot release MUST NOT wait for full audit writer drain
- **AND** any terminal audit flush performed on the main lifecycle path MUST be bounded by a short best-effort budget

### Requirement: Terminal protocol history MUST avoid blocking on incomplete mirror drain

The system MUST keep terminal protocol/history reads responsive even if background audit mirrors are still draining.

#### Scenario: terminal protocol history falls back to live-first when bounded flush times out

- **WHEN** a terminal FCMP or RASP history request is served
- **AND** the bounded mirror flush does not finish within its budget
- **THEN** the system MUST return the currently available live protocol rows without synchronously waiting for audit completion
- **AND** the response shape and event schema MUST remain unchanged

### Requirement: Qwen is a first-class supported engine

The runtime adapter layer SHALL treat `qwen` as a first-class supported engine with a dedicated adapter package under `server/engines/qwen/**`.

#### Scenario: Qwen adapter is registered

- **WHEN** the engine adapter registry is initialized
- **THEN** it MUST validate and register the `qwen` adapter profile
- **AND** `engine=qwen` MUST resolve to a concrete execution adapter

### Requirement: Qwen non-interactive execution uses the top-level qwen CLI contract

Qwen non-interactive execution SHALL use the top-level `qwen` command with `stream-json` output and `--resume`-based session continuation.

#### Scenario: Build Qwen start command

- **WHEN** the runtime builds a Qwen start command
- **THEN** it MUST invoke the top-level `qwen` executable
- **AND** it MUST include `--output-format stream-json`
- **AND** it MUST include `--approval-mode yolo`
- **AND** it MUST include `-p "<prompt>"`

#### Scenario: Build Qwen resume command

- **WHEN** the runtime builds a Qwen resume command
- **THEN** it MUST invoke the top-level `qwen` executable
- **AND** it MUST include `--output-format stream-json`
- **AND** it MUST include `--approval-mode yolo`
- **AND** it MUST include `--resume <session_id>`
- **AND** it MUST include `-p "<prompt>"`

### Requirement: Qwen parser extracts stable non-live semantics

Qwen phase-1 stream parsing SHALL only extract the semantic subset needed by Skill Runner from non-live NDJSON output.

#### Scenario: Parse Qwen stream-json output

- **WHEN** Qwen emits NDJSON events
- **THEN** the parser MUST extract `session_initialized` for session handle recovery
- **AND** it MUST extract `assistant` payloads for assistant text
- **AND** it MUST extract `result` payloads for final result text
- **AND** live streaming support is not required in this phase

### Requirement: Engine enumeration includes qwen

The `ENGINE_KEYS` configuration SHALL include `qwen` in the tuple of supported engines.

#### Scenario: Engine keys registry

- **WHEN** the system loads engine keys
- **THEN** `qwen` MUST be present in the `ENGINE_KEYS` tuple

### Requirement: Qwen runtime parser MUST conform to the shared adapter runtime contract
Qwen parser 语义 MUST 作为共享 adapter runtime contract 的一部分定义，而不是通过独立 qwen parser capability 单独维护。

#### Scenario: qwen runtime stream parsing uses shared contract fields
- **WHEN** Qwen 解析 `stream-json` NDJSON 运行时输出
- **THEN** parser MUST 提取 `system/subtype=init` 作为 `session_id` / `run_handle` 候选
- **AND** 它 MUST 提取 `assistant.message.content[].type=text` 为 `assistant_messages`
- **AND** 它 MUST 提取 `thinking`、`tool_use`、`tool_result` 为 `process_events`
- **AND** 它 MUST 提取 `result` 作为 turn-complete 语义与最终文本候选

#### Scenario: qwen live parser remains stdout and pty scoped
- **WHEN** Qwen live parser session 增量处理 NDJSON
- **THEN** live session MUST 接受 `stdout` 与 `pty`
- **AND** 它 MUST 为 `run_handle`、`turn_marker`、`assistant_message`、`process_event` 发出共享 emission
- **AND** 普通 `stderr` auth banner MUST NOT 被当作 live semantic event 处理

### Requirement: Adapter profile MAY declare UI shell config assets for session-local security
支持 UI shell 的 adapter profile MUST 能声明 session-local config 资产与目标路径，使安全限制通过共享 runtime contract 装配，而不是依赖 engine-specific capability。

#### Scenario: qwen adapter profile resolves ui shell config assets
- **WHEN** runtime 读取 qwen adapter profile 的 `ui_shell.config_assets`
- **THEN** profile MUST 能解析 default、enforced、settings schema 与 target relpath
- **AND** target relpath MUST 指向 `.qwen/settings.json`

### Requirement: Codex headless sandbox availability MUST be determined by runtime probe

Codex headless execution MUST determine sandbox availability from a real runtime probe and persist
that result in a Codex-side sidecar asset.

#### Scenario: `LANDLOCK_ENABLED=0` marks Codex sandbox unavailable

- **WHEN** runtime probes Codex sandbox availability
- **AND** environment variable `LANDLOCK_ENABLED=0`
- **THEN** the probe result MUST be `available=false`
- **AND** it MUST use warning code `CODEX_SANDBOX_DISABLED_BY_ENV`

#### Scenario: missing bubblewrap marks Codex sandbox unavailable

- **WHEN** runtime probes Codex sandbox availability
- **AND** neither `bwrap` nor `bubblewrap` can be resolved
- **THEN** the probe result MUST be `available=false`
- **AND** it MUST use warning code `CODEX_SANDBOX_DEPENDENCY_MISSING`
- **AND** the missing dependency list MUST include `bubblewrap`

#### Scenario: bubblewrap uid-map failure marks Codex sandbox runtime unavailable

- **WHEN** runtime probes Codex sandbox availability
- **AND** the bubblewrap smoke test fails with `uid_map`, `Operation not permitted`, `Permission denied`, or equivalent initialization failure wording
- **THEN** the probe result MUST be `available=false`
- **AND** it MUST use warning code `CODEX_SANDBOX_RUNTIME_UNAVAILABLE`
- **AND** the diagnostic message MUST preserve the first failing line for troubleshooting

#### Scenario: successful smoke test marks Codex sandbox available

- **WHEN** runtime probes Codex sandbox availability
- **AND** the bubblewrap smoke test succeeds
- **THEN** the probe result MUST be `available=true`
- **AND** it MUST be persisted to `agent_home/.codex/sandbox_probe.json`

### Requirement: Codex headless fallback MUST downgrade both command and generated config

Codex headless fallback MUST be effective: when sandbox runtime is unavailable, the runtime MUST
downgrade both CLI intent and generated profile settings.

#### Scenario: unavailable probe downgrades headless argv and config together

- **WHEN** Codex headless start or resume runs with sandbox probe `available=false`
- **THEN** command construction MUST downgrade `--full-auto` to `--yolo`
- **AND** generated Codex profile settings MUST set `sandbox_mode = "danger-full-access"`
- **AND** generated Codex profile settings MUST preserve `approval_policy = "never"`

#### Scenario: available probe keeps declared sandboxed defaults

- **WHEN** Codex headless start or resume runs with sandbox probe `available=true`
- **THEN** command construction MAY keep `--full-auto`
- **AND** generated Codex profile settings MUST keep the declared sandboxed mode rather than forcing `danger-full-access`

#### Scenario: missing or unreadable sidecar does not fail open

- **WHEN** headless Codex needs sandbox availability
- **AND** `agent_home/.codex/sandbox_probe.json` is missing or unreadable
- **THEN** runtime MUST synchronously execute a fresh Codex sandbox probe
- **AND** it MUST persist the new probe result before command/config decisions are finalized

### Requirement: Codex sandbox status collection MUST reuse probe truth

Codex sandbox management status MUST surface the same persisted runtime probe truth used by the
headless launch path.

#### Scenario: status collection returns runtime probe detail

- **WHEN** management code collects Codex sandbox status
- **THEN** it MUST return the persisted or freshly probed Codex sandbox result
- **AND** it MUST surface `available`, `status`, `warning_code`, `message`, `dependencies`, and `missing_dependencies`
- **AND** it MUST NOT regress to an environment-variable-only heuristic once the runtime probe model exists

### Requirement: Structured output pipeline MUST align machine schema transport and prompt contract rendering
系统 MUST 通过统一 structured-output pipeline 决定引擎实际使用的 machine schema 与对应 prompt contract 文本，禁止两者分别由不同调用点独立选择。

#### Scenario: canonical passthrough engine
- **WHEN** 某引擎使用 canonical passthrough 策略
- **THEN** CLI schema 注入 MUST 使用 canonical machine schema
- **AND** prompt contract rendering MUST 使用 canonical schema 派生文本

#### Scenario: compat-translated engine
- **WHEN** 某引擎使用 compat translate 策略
- **THEN** CLI schema 注入 MUST 使用 engine-effective compat schema
- **AND** prompt contract rendering MUST 使用与该 compat schema 一致的派生文本

### Requirement: Engine adapters MUST consume prompt contract text as in-memory runtime data
系统 MUST 将 prompt contract 文本视为 structured-output pipeline 的内存结果，而不是 run-scoped Markdown artifact 路径。

#### Scenario: adapter or patch consumer requests prompt contract
- **WHEN** adapter bootstrap、skill patcher 或 repair builder 请求 prompt contract
- **THEN** 返回值 MUST 为内存中的 rendered contract text
- **AND** 系统 MUST NOT 依赖 `.audit/contracts/*.md` prompt artifact path

### Requirement: Adapter structured-output dispatch MUST route through the shared runtime pipeline

Adapter command construction and parsed payload handling MUST delegate structured-output transport decisions to the shared runtime pipeline.

#### Scenario: command builder asks pipeline for effective schema artifact
- **WHEN** an adapter constructs a non-passthrough start or resume command
- **THEN** it MUST resolve structured-output CLI arguments from the shared runtime pipeline
- **AND** engine-local command builders MUST NOT independently decide between canonical and compatibility schema artifacts

#### Scenario: parsed payload is canonicalized in shared adapter runtime
- **WHEN** an adapter parser extracts a structured final payload
- **THEN** the shared adapter runtime MUST apply the configured payload canonicalizer before returning the final turn result
- **AND** downstream orchestration MUST receive the canonical payload shape rather than any engine transport shim

### Requirement: Run-root instruction files MUST carry engine-agnostic global execution constraints
系统 MUST 在 run materialization 阶段将 engine-agnostic 全局执行约束渲染到 `run_dir` 根目录的引擎约定文件中，而不是在 first-attempt prompt 中追加隐藏前缀。

#### Scenario: materialize run-root instruction file
- **WHEN** 系统为某个 run 物化 run-local skill snapshot
- **THEN** Claude MUST 生成 `run_dir/CLAUDE.md`
- **AND** Gemini MUST 生成 `run_dir/GEMINI.md`
- **AND** 其他引擎 MUST 生成 `run_dir/AGENTS.md`
- **AND** 系统 MUST NOT 在 engine workspace 子目录再写第二份同类文件

### Requirement: Engine prompt assembly MUST begin with an adapter-owned invoke line
系统 MUST 由 adapter profile 声明 skill invoke line 模板，并保证最终 prompt 的第一行始终为该 invoke line。

#### Scenario: assemble skill prompt
- **WHEN** runtime 为某个 skill 构建最终 prompt
- **THEN** 第 1 行 MUST 来自 `prompt_builder.skill_invoke_line_template`
- **AND** 第 2 行起 MUST 来自 body prompt
- **AND** 若 body prompt 为空，最终 prompt MUST 仅包含 invoke line

### Requirement: Prompt builder profiles MUST declare invoke-line and optional default-body extra blocks only
系统 MUST 将 adapter profile 中的 prompt builder 配置收口为 skill 调用首行模板与默认 body 前后 extra block，禁止继续声明旧的 body-template fallback、parameter-prompt、params-json、skill-dir 注入开关。

#### Scenario: adapter profile declares prompt builder
- **WHEN** 系统加载某引擎的 `adapter_profile.json`
- **THEN** `prompt_builder` MUST 至少声明 `skill_invoke_line_template`
- **AND** `prompt_builder` MUST 声明 `body_prefix_extra_block` 与 `body_suffix_extra_block`
- **AND** 系统 MUST reject removed legacy prompt-builder fields

### Requirement: Runtime prompt assembly MUST use a shared default body template
系统 MUST 在 skill 未声明 engine/common body prompt 时回退到一份共享默认 body 模板，而不是为各引擎维护重复的默认 body 模板文件。

#### Scenario: skill prompt override is absent
- **WHEN** `entrypoint.prompts[engine]` 与 `entrypoint.prompts.common` 都不存在
- **THEN** runtime MUST render the shared prompt body template
- **AND** runtime MUST apply profile prefix/suffix extra blocks around that shared body

#### Scenario: skill prompt override exists
- **WHEN** `entrypoint.prompts[engine]` 或 `.common` 命中
- **THEN** runtime MUST treat that prompt text as the full body prompt
- **AND** runtime MUST NOT wrap it with profile default-body extra blocks

### Requirement: Engine config composers MUST consume governed MCP renderer output
Engine config composers MUST receive or compute governed MCP renderer output and merge it through the shared runtime config layering path. Engine-specific composers MUST NOT independently parse skill MCP declarations.

#### Scenario: composer receives governed MCP config
- **WHEN** an engine config composer prepares the config for a run
- **THEN** governed MCP renderer output MUST be available as a dedicated system-generated layer
- **AND** composer behavior MUST use the engine-native root shape produced by the renderer

### Requirement: Adapter runtime MUST reject MCP bypass inputs before launch
Adapter runtime preparation MUST fail fast when user-controlled config contains direct MCP root keys.

#### Scenario: bypass key reaches adapter preparation
- **WHEN** adapter runtime preparation sees `mcpServers`, `mcp_servers`, or `mcp` from skill defaults or runtime overrides
- **THEN** it MUST raise a configuration error before building the engine command

### Requirement: Codex adapter MUST support per-run MCP profiles
Codex adapter runtime MUST support selecting a per-run profile when governed MCP resolution includes declared MCP entries.

#### Scenario: per-run profile is selected
- **GIVEN** governed MCP resolution for a Codex run includes declared MCP
- **WHEN** the Codex adapter builds the start or resume command
- **THEN** the command MUST select the per-run profile that contains those MCP entries

#### Scenario: per-run profile cleanup is requested
- **GIVEN** a Codex run used a per-run MCP profile
- **WHEN** orchestration performs terminal cleanup
- **THEN** it MUST invoke Codex profile cleanup for that run profile

### Requirement: Engine adapters MUST consume secret-resolved governed MCP config
Engine adapters SHALL consume MCP renderer output after runtime secret references have been resolved and SHALL keep raw MCP secrets out of skill manifests, skill config assets, runtime overrides, logs, and management responses.

#### Scenario: Codex MCP config includes resolved auth
- **WHEN** Codex runtime config composition renders a governed MCP server with auth
- **THEN** the adapter MUST receive the auth under the Codex-native MCP root
- **AND** declared run-local MCP behavior MUST continue to use per-run profile selection and cleanup

#### Scenario: JSON MCP engines include resolved auth
- **WHEN** Gemini, Qwen, or Claude runtime config composition renders a governed MCP server with auth
- **THEN** the adapter MUST receive the auth under `mcpServers`

#### Scenario: OpenCode MCP config includes resolved auth
- **WHEN** OpenCode runtime config composition renders a governed MCP server with auth
- **THEN** the adapter MUST receive the auth under `mcp`

#### Scenario: Direct root bypass remains rejected
- **WHEN** an engine adapter receives skill config or runtime override input containing a native MCP root
- **THEN** the adapter or shared composer MUST reject that input before applying governed MCP output

### Requirement: Claude adapter MUST use active state for MCP lifecycle
The Claude adapter SHALL prepare and clean up governed MCP state using the active Claude state file derived from the runtime `CLAUDE_CONFIG_DIR`.

#### Scenario: Claude run starts with run-local MCP
- **WHEN** a Claude run resolves run-local MCP servers
- **THEN** the adapter MUST materialize those servers into the current run project entry before launching Claude

#### Scenario: Claude run reaches terminal cleanup
- **WHEN** a Claude run used run-local MCP entries
- **THEN** the adapter MUST attempt to remove those run-local entries during terminal cleanup
- **AND** cleanup failure MUST NOT change the terminal run outcome

