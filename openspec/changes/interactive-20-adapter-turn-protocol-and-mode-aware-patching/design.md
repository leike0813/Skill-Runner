## Context

交互执行的本质是“回合编排”。  
如果 adapter 仍只返回终态结果，orchestrator 无法判断是否需要进入 `waiting_user`，只能把中间问题误判为失败文本。

## Goals

1. 定义引擎无关的回合协议，供 orchestrator 统一消费。
2. 保证 ask_user 载荷结构稳定、可校验。
3. 让 `skill_patcher` 与执行模式一致，避免指令冲突。
4. 让 adapter 的 CLI 参数构造与执行模式一致，避免 interactive 被自动执行参数破坏。

## Non-Goals

1. 不实现 token 级 streaming 协议。
2. 不为不同技能定义私有交互 DSL。
3. 不改变现有 output schema 校验规则。

## Prerequisite

- 必须先完成 `interactive-05-engine-session-resume-compatibility`，并复用其 `EngineSessionHandle` 与 `interactive_profile` 能力分层结果。
- `interactive-20` 不重复定义 resume 参数细节，只定义 turn 协议与模式感知 patch 规则。

## Design

### 1) Turn Protocol 结构

`AdapterTurnResult` 建议字段：
- `outcome: final | ask_user | error`
- `final_data`（当 outcome=final）
- `interaction`（当 outcome=ask_user）
  - `kind`, `prompt`, `options`, `required_fields`, `context`
- `stderr`, `repair_level`, `failure_reason`

### 2) Base Adapter 改造

- 保留现有执行五阶段骨架；
- 解析层从“仅提取最终 JSON”改为“先识别控制信号，再识别最终结果”；
- 为 ask_user 提供严格校验，缺字段按 `error` 返回。

### 3) 三引擎适配策略

- 统一要求 Agent 输出 envelope（可嵌入现有 JSON 结果中）；
- adapter 内完成各引擎文本/NDJSON 差异抹平；
- orchestrator 不感知引擎差异，仅消费统一协议对象。

### 4) Patcher 模式感知

`skill_patcher` 采用两段式 pipeline，避免把“路径重定向”与“执行语义”耦合在一个 patch 文案里：

- Step A: `artifact_patch`（模式无关，始终执行）
  - 仅负责注入 artifact 输出重定向；
  - 明确覆盖 skill 原始文案中的输出路径描述；
  - `auto` 与 `interactive` 均要求生成该段。
- Step B: `mode_patch`（模式相关，按 execution_mode 分支）
  - `auto`：注入“不得问用户”与“自行决策推进”约束；
  - `interactive`：注入“允许 ask_user，但必须结构化输出 interaction 载荷”约束。

约束：
- 两段 patch 的文案边界必须清晰，不允许重复描述 artifact 路径；
- `interactive` 最终文案中不得出现“禁止向用户提问”的指令；
- `auto` 最终文案中必须包含禁止交互提问的指令。

### 5) CLI 参数构造模式感知

为三引擎定义统一规则：自动执行参数只允许在 `auto` 模式注入。

- `auto`：
  - Gemini / iFlow：保留 `--yolo`；
  - Codex：保留现有自动执行参数分支（`--full-auto` 或 `--yolo`）。
- `interactive`：
  - Gemini / iFlow：不得注入 `--yolo`；
  - Codex：不得注入 `--full-auto` 或 `--yolo`；
  - reply/resume 回合同样不得注入自动执行参数。

建议实现方式：
- 在 adapter 命令构造层引入 `execution_mode` 入参；
- 将“自动执行参数列表”封装为单一函数，避免各 adapter 分散判断；
- 对最终命令做断言日志（debug 级）以便排障。

## Risks & Mitigations

1. **风险：引擎输出不稳定导致误判 ask_user**
   - 缓解：严格 envelope 校验 + 失败即 error，不进入 waiting_user。
2. **风险：改动 adapter 基类影响 auto 稳定性**
   - 缓解：保留 auto fast-path 回归测试，确保无 ask_user 时行为一致。
3. **风险：patcher 分步后顺序或组合错误**
   - 缓解：固定执行顺序为 `artifact_patch -> mode_patch`，并为两段 patch 分别增加单测断言。
4. **风险：interactive 回合误带自动执行参数导致无法中断提问**
   - 缓解：为三引擎增加命令行构造单测，断言 interactive 下不出现 `--yolo/--full-auto`。
