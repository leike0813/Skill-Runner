## Why

当前系统会把非终态的 agent message 先按 `reasoning` 暴露，再在回合收敛时通过 `promoted/final` 变成正式对话内容。这会把“代理正在组织中的正文”与“真正的推理过程”混在一起，也让前端默认只能用思考气泡承载大量文本，显示空间和可读性都不理想。

## What Changes

- 重新定义非终态 agent message 的语义分类，不再把这类内容先当作 `reasoning` 再 promote，而是赋予独立的消息语义。
- 调整 canonical chat replay 与交互式协议，使这类 agent message 能以独立种类进入聊天时间线，同时保留真正的 reasoning / tool / command 过程语义。
- 新增一种更接近终端 plain 风格的前端展示模式，并设为默认展示方式；在该模式下，所有 agent message 都直接作为对话内容展示，其余过程事件仍作为推理过程显示。
- 保留传统气泡模式；在该模式下，非终态 agent message 仍然和 `reasoning`、`tool_call`、`command_execution` 一样，被包裹在推理过程区域中，而不是直接展开成正文消息。
- 提供前端开关，允许用户在新的 plain 模式与传统气泡模式之间切换。
- **BREAKING** 现有“非终态 agent message 一律按 reasoning 暴露，再由 promoted/final 收敛”的规范语义将被替换，依赖旧语义的前端/派生逻辑需要跟随新的 message kind 与展示规则调整。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `interactive-job-api`: 调整 FCMP/chat replay 对非终态 agent message、promoted/final 和用户可见消息时间线的要求。
- `interactive-run-observability`: 调整 runtime/RASP 中 agent 过程消息与真正 reasoning 的语义边界。
- `canonical-chat-replay`: 扩展 canonical chat replay 的消息 kind 和派生规则，使非终态 agent message 成为独立聊天语义。
- `runtime-event-command-schema`: 更新运行时事件/命令 schema，使新的 agent message 语义有明确合同。
- `builtin-e2e-example-client`: 为内建 E2E 前端增加默认 plain 模式和模式切换开关，并定义其展示语义。
- `run-observability-ui`: 为主 UI 的 run 观测页面增加同样的展示模式切换与默认 plain 渲染要求。

## Impact

- 影响 runtime 协议、canonical chat replay 派生、FCMP/RASP 事件语义和相关 schema。
- 影响 E2E 前端与主 run 观测 UI 的默认展示模式、消息分组、模式切换和消息去重逻辑。
- 影响依赖 `assistant.reasoning` / `assistant_process` 近似表达正文消息的现有前端消费方式与测试基线。
