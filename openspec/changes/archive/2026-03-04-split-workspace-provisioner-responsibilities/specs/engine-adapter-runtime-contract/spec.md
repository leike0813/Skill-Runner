## MODIFIED Requirements

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

## ADDED Requirements

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
