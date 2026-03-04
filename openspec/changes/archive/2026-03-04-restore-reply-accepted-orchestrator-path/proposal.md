## Why

当前交互式 reply 提交虽然已经成功落库并驱动续跑，但缺少 canonical 的 `interaction.reply.accepted` 发布链路。结果是 canonical chat replay 无法渲染普通用户回复气泡，而共享 runtime 文档与规格又已经将 `interaction.reply.accepted` 视为 FCMP 生命周期的一部分，导致实现与合同发生漂移。

## What Changes

- 将交互式 reply acceptance 统一收敛到 canonical 后端发布路径：`submit_reply` 追加 orchestrator event，协议翻译层产出 FCMP，canonical chat replay 再从该 FCMP 派生用户气泡。
- 为 `interaction.reply.accepted` 增加 schema-backed 的 orchestrator event 合同，稳定承载 `interaction_id`、`accepted_at`、`response_preview` 等元数据。
- 明确 reply acceptance 的发布来源必须与其他 orchestrator 驱动的生命周期事件保持对称，由 orchestrator event 进入 FCMP，而不是在 reply endpoint 自行合成 FCMP。
- 收紧 canonical chat replay 要求：普通用户回复只能来源于 FCMP `interaction.reply.accepted`，不引入 endpoint 本地气泡或 interaction history fallback。

## Capabilities

### New Capabilities
- `canonical-chat-replay`: 定义普通用户回复气泡必须从 canonical FCMP 发布链路派生，而不是从 endpoint 本地合成。

### Modified Capabilities
- `interactive-job-api`: 交互式 reply 提交后必须先发布 canonical backend acceptance event，随后才在 chat replay 中可见。
- `job-orchestrator-modularization`: reply acceptance 必须经过 orchestrator event 管线后再进入 FCMP。
- `runtime-event-command-schema`: 运行时 schema 必须识别 `interaction.reply.accepted` orchestrator event 及其稳定 payload。

## Impact

- 影响代码：`run_interaction_service`、runtime event 模型/schema、FCMP translator、chat replay derivation。
- 影响 API：不新增 public endpoint；现有 `/chat` 与 `/chat/history` 将恢复普通用户 reply 的可见性。
- 影响测试：协议 schema、FCMP 翻译、chat replay 派生、observability/chat UI replay。
