## Why

当前 NDJSON 运行时路径对所有逻辑行统一施加 `4096` 字节截断保护，这对 `tool_result` 一类高体积事件是合理的，但会误伤正常的 agent 文本输出。随着 `qwen / claude / codex / opencode` 都在 live 语义面上稳定产出 `agent.reasoning` 与 `agent.message`，这类文本被统一截断已经开始影响对话可读性与审计一致性。

## What Changes

- 为共享 NDJSON overflow guard 增加语义豁免规则。
- 仅当消息会被归类为 `agent.reasoning` 或 `agent.message` 时，跳过 `4096` 字节截断。
- 保持 `tool_use`、`tool_result`、`command_execution`、`tool_call` 等非消息类事件继续沿用现有 overflow repair / sanitize / substitute 语义。
- 要求 live semantic 入口与 audit/raw 入口共用同一套豁免判定，避免 live 与落盘事实漂移。
- 要求 NDJSON-based engine parser 提供轻量预分类能力，供 shared runtime 在完整 parse 之前识别 reasoning / assistant message。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `engine-adapter-runtime-contract`: 调整 NDJSON overflow guard 规则，使 `agent.reasoning` / `agent.message` 获得语义豁免，并要求 live/audit 两条 shared 路径使用同一套判定。

## Impact

- 影响 shared runtime NDJSON 基础设施：`NdjsonLineBuffer`、`NdjsonIngressSanitizer`
- 影响 NDJSON-based engine parser：`codex`、`claude`、`opencode`、`qwen`
- 不影响外部 HTTP API 与 runtime event schema
- 影响 live 展示、audit 落盘、strict replay 对长 agent 文本的可见性与一致性
