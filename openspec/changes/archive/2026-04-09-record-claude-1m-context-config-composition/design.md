## Context

Claude 的官方模型目录已经新增 `sonnet[1m]` 与 `opus[1m]`，但配置合成层此前只支持把模型值直接写入 `env.ANTHROPIC_MODEL`。对于官方模型，这不足以显式控制 1M context 开关；对于 custom provider，这会与 Claude 通过根 `model` 和 `ANTHROPIC_DEFAULT_SONNET_MODEL` 指向 provider 模型的写法冲突。与此同时，UI shell 之前只复用一个“返回 env 覆盖”的 helper，无法表达根上的 `model` 字段。

## Goals / Non-Goals

**Goals:**
- 让 Claude headless run 与 UI shell 共享同一套 `[1m]` 模型分流逻辑。
- 保持官方模型与 custom provider 模型在 1M 模式下的配置行为清晰且可审计。
- 避免默认层残留的 `ANTHROPIC_MODEL` 污染 custom provider 的 1M 路径。

**Non-Goals:**
- 不修改对外请求协议或模型目录接口。
- 不为 `opus[1m]` custom provider 再引入另一套 provider-specific 根 `model` 写法；本次按既定 `model="sonnet[1m]"` 合同记录。
- 不改动 Claude schema 本身，除非为匹配既有 schema 修正文档化的值类型。

## Decisions

- 将原来的 `build_claude_model_env_overrides()` 提升为返回完整 runtime override 的共享 helper，而不是仅返回 `env` 片段。这样 headless run 与 UI shell 都能消费同一份结构，并支持根上的 `model`。
- `[1m]` 语义继续只由模型名后缀触发，不新增单独布尔开关。
- 官方 `[1m]` 模型保持 `ANTHROPIC_MODEL=<原始模型名>`，只把 `CLAUDE_CODE_DISABLE_1M_CONTEXT` 覆盖为 `"0"`。
- custom provider `[1m]` 模型使用 `ANTHROPIC_DEFAULT_SONNET_MODEL=<base model>` + 根 `model="sonnet[1m]"`，并在最终配置中显式去除默认层遗留的 `ANTHROPIC_MODEL`。
- Claude `env` schema 现有要求是字符串值，因此 `CLAUDE_CODE_DISABLE_1M_CONTEXT` 记录为 `"0"` / `"1"`，而不是整数。

## Risks / Trade-offs

- [Risk] custom provider 的 `[1m]` 路径若不移除默认层 `ANTHROPIC_MODEL`，会与新的根 `model` 写法冲突。  
  Mitigation: 在最终 compose 后显式删除该键。

- [Risk] UI shell 若继续单独拼 `env`，会与 headless run 再次漂移。  
  Mitigation: UI shell 改为复用同一个 Claude runtime override builder。

- [Risk] Claude custom provider 解析若仍严格按原始 `provider/model` 匹配，会拒绝 `provider/model[1m]`。  
  Mitigation: custom provider resolve 路径先去掉 `[1m]` 再匹配 provider 模型。
