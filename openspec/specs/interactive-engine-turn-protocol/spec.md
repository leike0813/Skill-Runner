# interactive-engine-turn-protocol Specification

## Purpose
TBD - created by archiving change interactive-20-adapter-turn-protocol-and-mode-aware-patching. Update Purpose after archive.
## Requirements
### Requirement: 引擎适配层 MUST 输出统一回合协议
系统 MUST 通过统一协议表达 `final/ask_user/error` 三类回合结果。

#### Scenario: 适配器返回 ask_user
- **WHEN** 任一引擎在执行中需要用户输入
- **THEN** 适配器返回 `outcome=ask_user`
- **AND** 包含结构化 interaction 载荷

#### Scenario: 适配器返回 final
- **WHEN** 任一引擎完成任务并产生最终结果
- **THEN** 适配器返回 `outcome=final`
- **AND** 提供可供输出 schema 校验的数据

### Requirement: 系统 MUST 校验 ask_user 载荷完整性
系统 MUST 在进入 waiting_user 前校验 interaction 载荷，非法载荷不得进入交互态。

#### Scenario: ask_user 缺少必填字段
- **WHEN** 适配器产出的 interaction 缺失 `interaction_id/prompt` 等关键字段
- **THEN** 系统将该回合判定为错误
- **AND** run 不进入 `waiting_user`

### Requirement: 运行时补丁 MUST 与执行模式一致
系统 MUST 基于 execution_mode 生成一致的运行时指令补丁。

并且系统 MUST 将运行时补丁分为：
- 模式无关的 artifact 重定向补丁；
- 模式相关的执行语义补丁。

#### Scenario: auto 模式补丁
- **WHEN** run 以 `auto` 模式执行
- **THEN** 补丁保持“不得询问用户决策”的约束

#### Scenario: interactive 模式补丁
- **WHEN** run 以 `interactive` 模式执行
- **THEN** 补丁允许请求用户输入
- **AND** 要求输出结构化 ask_user 载荷

#### Scenario: artifact 重定向补丁在两种模式都生效
- **WHEN** run 以 `auto` 或 `interactive` 模式执行
- **THEN** 都会注入 artifact 输出重定向补丁
- **AND** 输出路径被约束到 run 的 `artifacts/` 目录

#### Scenario: interactive 模式不包含禁止提问约束
- **WHEN** run 以 `interactive` 模式执行
- **THEN** 最终补丁文案不得包含“禁止向用户提问”的约束

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

