## Why

Claude 官方模型目录已经显式区分了普通变体与 `sonnet[1m]` / `opus[1m]` 变体，但运行时配置组装仍然只会把传入模型直接写进 `env.ANTHROPIC_MODEL`。这让 1M 上下文模式无法在 headless run 与 UI shell 两条 Claude 配置生成路径上以一致、可审计的方式生效。

## What Changes

- 记录 Claude runtime config 组装对 `[1m]` 模型后缀的正式支持。
- 规定官方 Claude `[1m]` 模型通过 `CLAUDE_CODE_DISABLE_1M_CONTEXT=0` 启用 1M，上下文外其余配置保持不变。
- 规定 Claude custom provider 的 `[1m]` 模型不再写 `ANTHROPIC_MODEL`，而是写 `ANTHROPIC_DEFAULT_SONNET_MODEL=<base model>` 并在配置根上写 `model="sonnet[1m]"`。
- 明确 UI shell 的 Claude session-local settings 必须复用与 headless run 相同的 1M 配置分流逻辑。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `engine-runtime-config-layering`: Claude runtime config layering 需要正式定义 `[1m]` 模型后缀在官方模型与 custom provider 模型上的配置合成规则，并要求 UI shell 复用相同逻辑。

## Impact

- Claude runtime config composer
- Claude UI shell session config generation
- Claude custom provider model resolution
- Claude config composer / UI shell regression tests
