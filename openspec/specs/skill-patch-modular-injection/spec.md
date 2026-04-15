# skill-patch-modular-injection Specification

## Purpose
定义 runtime skill patch 的模块化注入模型、模板来源与幂等行为。
## Requirements
### Requirement: 系统 MUST 以模块化计划驱动 skill patch
系统 MUST 通过统一 patch plan 生成注入模块列表并依序执行。

#### Scenario: 模块计划生成
- **WHEN** 运行时调用 skill patch
- **THEN** 系统生成可审计的模块顺序和内容

### Requirement: 模板 MUST 是注入文案唯一来源
系统 MUST 从 `server/assets/templates` 读取固定模板内容。

#### Scenario: 模板读取失败
- **WHEN** 任一必需模板缺失
- **THEN** 系统 fail fast 并返回明确错误

### Requirement: 输出 schema 注入 MUST 动态可选
系统 MUST 在 output schema 存在且可解析时注入 schema 说明块，并且该说明块 MUST 来自 structured-output pipeline 选定的 prompt contract artifact。

#### Scenario: schema 可解析
- **WHEN** 发现有效 output schema
- **THEN** 注入 `### Output Schema Specification`
- **AND** 注入内容 MUST 使用当前 engine 通过 structured-output pipeline 解析出的 prompt contract artifact

#### Scenario: engine 需要 compat prompt contract
- **WHEN** 当前 engine profile 声明 prompt contract 使用 compatibility artifact
- **THEN** patch 注入 MUST 使用 compatibility summary
- **AND** 该 summary MUST 与命令行实际注入的 machine schema artifact 保持同一治理来源

#### Scenario: schema 缺失或无效
- **WHEN** output schema 缺失或解析失败
- **THEN** 跳过 schema 说明模块并继续其余 patch 注入

### Requirement: 注入 MUST 保持幂等
Patch composition MUST remain modular and idempotent while YAML-side-channel wording is retired from the target contract.

#### Scenario: legacy YAML wording is deprecated
- **WHEN** legacy `<ASK_USER_YAML>` wording appears in historical notes
- **THEN** it MUST be labeled deprecated/current-implementation-only
- **AND** it MUST NOT be presented as the target injection contract

### Requirement: Runtime SKILL patch MUST use a fixed composition order
系统 MUST 按固定顺序组合 runtime `SKILL.md` 注入模块，避免静态模板与动态合同重复表达同一语义。

#### Scenario: runtime skill patch composition
- **WHEN** 运行时为 skill 生成 patch plan
- **THEN** 注入顺序 MUST 为 Runtime Enforcement → Runtime Output Overrides → Output Format Contract → Output Contract Details → Execution Mode
- **AND** Execution Mode 模块 MUST 出现在动态 contract details 之后

### Requirement: Interactive mode patch MUST express policy only
`patch_mode_interactive.md` MUST 仅表达 interactive 行为策略，不得重复 pending 分支的字段级合同说明。

#### Scenario: interactive mode patch rendering
- **WHEN** 运行时以 interactive 模式 patch `SKILL.md`
- **THEN** mode patch MUST 说明自主执行、最多一问、final/pending 二选一
- **AND** mode patch MUST NOT 重复 `message`、`ui_hints`、`options` 或 `files` 的字段级定义

### Requirement: 输出 schema 注入 MUST 来自 run-scoped materialization
Runtime patching MUST consume the run-scoped materialized schema summary instead of deriving patch text directly from raw `output.schema.json`.

#### Scenario: auto patch uses materialized markdown
- **WHEN** execution mode is `auto`
- **AND** a run-scoped schema summary artifact exists
- **THEN** the injected output schema section MUST come from the materialized markdown projection

#### Scenario: interactive patch keeps legacy ask-user compatibility in this phase
- **WHEN** execution mode is `interactive`
- **AND** a run-scoped schema summary artifact exists
- **THEN** the injected output schema section MUST come from the materialized markdown projection
- **AND** the interactive mode patch MUST still preserve current ask-user compatibility instructions for pending turns
- **AND** it MUST NOT yet require the pending JSON branch as the live prompt protocol

### Requirement: 注入 MUST 保持模块化与幂等
Patch composition MUST remain modular and idempotent after switching output schema injection to precomputed materialized markdown.

#### Scenario: repeated patching does not duplicate materialized schema section
- **WHEN** the same skill snapshot is patched multiple times
- **THEN** the materialized schema section MUST NOT be duplicated

### Requirement: Prompt organization MUST separate run-root instructions from runtime SKILL patching
系统 MUST 将 run-root instruction file 与 runtime `SKILL.md` patch 视为两个独立层次，禁止再次通过 skill prompt prefix 混合两者职责。

#### Scenario: prompt organization layers
- **WHEN** runtime 组织引擎可见提示信息
- **THEN** run-root instruction file MUST 承载 engine-agnostic 全局执行约束
- **AND** runtime `SKILL.md` MUST 继续承载 skill-local runtime patch 模块
- **AND** 最终 CLI prompt MUST 仅由 invoke line 与 body prompt 组成

### Requirement: Prompt organization SSOT MUST separate patched SKILL instructions from assembled body prompt defaults
系统 MUST 明确区分 runtime-patched `SKILL.md` 与 adapter prompt builder 的默认 body 模板，禁止将旧 prompt-builder 兼容变量继续视为 runtime instruction source。

#### Scenario: documentation describes prompt assembly
- **WHEN** 系统文档描述 skill prompt assembly
- **THEN** 文档 MUST 将 body 默认模板描述为共享模板加 profile extra block
- **AND** 文档 MUST NOT 继续声明 `params_json`、`input_prompt`、`skill_dir`、`input_file` 为 prompt-builder 提供的兼容上下文

