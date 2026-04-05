## Why

`engine-auth-qwen`、`qwen-stream-parser` 和 `qwen-ui-shell-security` 把 qwen 的要求拆成了独立 capability，但这些内容本质上分别属于 provider-aware auth、runtime parser、inline terminal security 这些跨引擎共享能力。继续保留 qwen 专属 spec 会让规范层次与项目中其它引擎不一致，也会让后续新增引擎时更容易继续复制 engine-specific capability。

## What Changes

- 将 `engine-auth-qwen` 中仍然有效的要求并入共享 auth specs，分别落到 provider strategy、auth observability，以及已存在的 management/UI capability。
- 将 `qwen-stream-parser` 中的 parser/live/run_handle/auth detection 要求并入共享 runtime/parser observability specs，不再保留 qwen 专属 parser capability。
- 将 `qwen-ui-shell-security` 中的 UI shell 配置资产、分层与安全限制要求并入共享 inline-terminal / runtime contract / config-layering specs。
- **BREAKING** 归档/同步后移除 `engine-auth-qwen`、`qwen-stream-parser`、`qwen-ui-shell-security` 三个 engine-specific capability，要求后续 change 不再向这些 capability 追加 delta。

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `engine-auth-strategy-policy`: 吸收 qwen provider-aware auth matrix 与显式 provider 声明要求。
- `engine-auth-observability`: 吸收 qwen oauth_proxy / coding-plan 的共享鉴权可观测与完成语义。
- `engine-adapter-runtime-contract`: 吸收 qwen runtime parser、live parser、UI shell config asset profile 契约。
- `engine-runtime-config-layering`: 吸收 qwen UI shell session-local config layering 要求。
- `interactive-run-observability`: 吸收 qwen run_handle / process event / live observability 语义。
- `ui-engine-inline-terminal`: 吸收 qwen UI shell enforced security 行为，并泛化为 inline terminal 的共享约束。
- `engine-auth-qwen`: 移除该 engine-specific capability，迁移到共享 auth specs。
- `qwen-stream-parser`: 移除该 engine-specific capability，迁移到共享 runtime / observability specs。
- `qwen-ui-shell-security`: 移除该 engine-specific capability，迁移到共享 UI shell / runtime specs。

## Impact

- 影响 `openspec/specs/` 中的共享 capability 文档结构与归属边界。
- 影响 `openspec/changes/*` 后续写 delta spec 的目标 capability 选择。
- 不引入新的对外 API；主要影响 spec 组织方式、归档后 capability 集合，以及后续变更的规范入口。
