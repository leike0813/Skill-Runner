# interactive-engine-turn-protocol Specification

## Purpose
TBD - created by archiving change interactive-20-adapter-turn-protocol-and-mode-aware-patching. Update Purpose after archive.
## Requirements
### Requirement: 引擎适配层 MUST 输出统一回合协议
The system MUST express turn results via a unified protocol, and `ask_user` MUST NOT be a hard prerequisite for entering `waiting_user` in interactive mode.

#### Scenario: ask_user 仅作为可选增强信息
- **WHEN** 引擎输出 `ask_user` 结构
- **THEN** 系统可将其解析为 pending 的增强字段（如 `ui_hints/options/context`）
- **AND** 不将其作为唯一控制流判定依据

#### Scenario: ask_user 可选增强优先使用非 JSON 结构
- **WHEN** 引擎需要输出 ask_user 风格提示
- **THEN** 应优先使用与 JSON 明显不同的结构化格式（例如 YAML block）
- **AND** 避免被最终业务 JSON 解析链误识别

### Requirement: 系统 MUST 校验 ask_user 载荷完整性
Validation of ask_user payload MUST be non-blocking: malformed ask_user MUST NOT directly fail the run and MUST NOT be treated as final business output for schema validation.

#### Scenario: ask_user 载荷不完整
- **WHEN** ask_user 缺失 `interaction_id/prompt` 等字段或类型不匹配
- **THEN** 系统忽略其结构化控制含义并回退到后端生成的 pending 基线
- **AND** run 仍可进入 `waiting_user`

### Requirement: 运行时补丁 MUST 与执行模式一致
Runtime patching MUST remain mode-aware; in interactive mode it MUST NOT require structured ask_user output, and it MUST enforce "no done marker before real completion".

#### Scenario: interactive 模式补丁
- **WHEN** run 以 `interactive` 模式执行
- **THEN** 补丁允许请求用户输入
- **AND** 不强制 ask_user JSON 结构
- **AND** 未完成前不得提前输出 `__SKILL_DONE__`

### Requirement: Adapter CLI 命令构造 MUST 与执行模式一致
系统 MUST 在构造引擎 CLI 命令时保持自动执行参数策略一致：`auto` 与 `interactive` 两种模式都保留自动执行参数。  
并且 iFlow 在所有执行场景 MUST 默认包含 `--thinking` 参数。

#### Scenario: Gemini auto 模式命令
- **WHEN** Gemini 以 `auto` 模式执行
- **THEN** 命令包含 `--yolo`

#### Scenario: Gemini interactive 模式命令
- **WHEN** Gemini 以 `interactive` 模式执行
- **THEN** 命令包含 `--yolo`

#### Scenario: iFlow auto 模式命令
- **WHEN** iFlow 以 `auto` 模式执行
- **THEN** 命令包含 `--yolo`
- **AND** 命令包含 `--thinking`

#### Scenario: iFlow interactive 模式命令
- **WHEN** iFlow 以 `interactive` 模式执行
- **THEN** 命令包含 `--yolo`
- **AND** 命令包含 `--thinking`

#### Scenario: Codex auto 模式命令
- **WHEN** Codex 以 `auto` 模式执行
- **THEN** 命令包含自动执行参数（`--full-auto` 或 `--yolo`）

#### Scenario: Codex interactive 模式命令
- **WHEN** Codex 以 `interactive` 模式执行
- **THEN** 命令包含自动执行参数（`--full-auto` 或 `--yolo`）

#### Scenario: interactive resume 回合命令
- **WHEN** run 在 `interactive` 模式执行 reply/resume 回合
- **THEN** Gemini 命令包含自动执行参数（`--yolo`）
- **AND** iFlow 命令包含自动执行参数（`--yolo`）与 `--thinking`
- **AND** Codex 命令包含自动执行参数（`--yolo` / `--full-auto`）

### Requirement: 完成态判定 MUST 按 execution_mode 区分
系统 MUST 以 execution_mode 区分完成态判定规则。

#### Scenario: interactive 模式强条件判定完成
- **WHEN** run 以 `interactive` 模式执行
- **AND** 解析到 `__SKILL_DONE__`
- **THEN** 回合可进入完成判定与最终输出校验并可结束运行

#### Scenario: done marker 检测兼容转义流文本
- **WHEN** 运行时输出为 NDJSON 事件行，且 marker 位于 assistant 回复字段的字符串文本（例如 `\"__SKILL_DONE__\": true`）
- **THEN** 系统必须将其识别为 done marker 证据
- **AND** done marker 证据仅来自 assistant 回复内容（例如 codex `item.completed.item.type=agent_message`、gemini `response`、opencode `type=text`）
- **AND** `tool_use`/tool 回显中的 marker 文本 MUST NOT 作为 done marker 证据
- **AND** 运行时判定与审计判定必须保持一致

#### Scenario: interactive 模式软条件判定完成
- **WHEN** run 以 `interactive` 模式执行
- **AND** 未解析到 `__SKILL_DONE__`
- **AND** 当前回合输出通过 output schema 校验
- **THEN** 系统可判定执行完成
- **AND** 记录 warning `INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER`

#### Scenario: interactive 模式缺失 done marker 进入等待态
- **WHEN** run 以 `interactive` 模式执行
- **AND** 未解析到 `__SKILL_DONE__`
- **AND** 当前回合输出未通过 output schema 校验
- **AND** 进程未发生中断性失败
- **THEN** 系统进入 `waiting_user`

#### Scenario: auto 模式不严格依赖 done marker
- **WHEN** run 以 `auto` 模式执行
- **AND** 最终输出通过 schema 校验
- **THEN** 系统可判定执行成功
- **AND** 不要求必须存在 `__SKILL_DONE__`

#### Scenario: done marker 在两种模式下均不参与业务校验
- **WHEN** 系统执行 output schema validation
- **THEN** 必须先移除 `__SKILL_DONE__`
- **AND** 仅对业务字段进行校验

#### Scenario: marker 已检测但输出无效必须失败
- **WHEN** 当前回合检测到 `__SKILL_DONE__`
- **AND** 输出解析失败或 output schema 校验失败
- **THEN** run 必须进入 `failed`
- **AND** 不得回退为 `waiting_user`

### Requirement: 运行时 skill patch 注入 MUST 模块化且顺序固定
系统 MUST 按固定模块顺序注入运行时 patch 到 `SKILL.md`。

#### Scenario: patch 顺序固定
- **WHEN** 运行时执行 skill patch
- **THEN** 注入顺序为：
  1. runtime enforcement
  2. artifact redirection（若存在 artifacts）
  3. output format contract
  4. output schema specification（若 output schema 可用）
  5. mode patch（auto 或 interactive）

#### Scenario: mode 注入互斥
- **WHEN** execution_mode=`interactive`
- **THEN** 仅注入 interactive mode patch
- **AND** 不注入 auto mode patch
