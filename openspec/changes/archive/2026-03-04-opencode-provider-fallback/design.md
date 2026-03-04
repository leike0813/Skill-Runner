## Context

`opencode` 与其他 engine 不同，interactive auth provider 不是固定在 detection 结果里。request 的 `engine_options.model` 已经编码了 provider 身份，例如 `deepseek/deepseek-reasoner`、`moonshot/...`、`openrouter/...`。当前实现却把 provider 归因绑到了 `auth_detection.provider_id`，导致 detection 未抽取出 provider 时，即使 `auth_required + high confidence` 也无法创建 `pending_auth`。

本 change 只做 engine-specific 修复，不修改 shared SSOT 文档，也不把规则推广为全局 runtime contract。

## Goals / Non-Goals

**Goals**
- 对 `opencode` 从 request-side `engine_options.model` 解析 canonical provider。
- 在 detection provider 缺失时仍能进入 `waiting_auth`。
- 保证 pending auth、auth session、FCMP challenge provider 一致。
- provider 无法解析时留下明确诊断，而不是静默掉进普通 `AUTH_REQUIRED`。

**Non-Goals**
- 不修改其他 engine 的 provider 逻辑。
- 不重构 auth detection 层。
- 不修改 shared SSOT 文档。

## Decisions

### 1. Canonical provider 来源

仅对 `opencode`：
- orchestration MUST 从 `engine_options.model` 解析 provider
- 解析规则是取第一个 `/` 前缀并做 `strip + lower`

### 2. Detection provider 降级为证据

`auth_detection.provider_id` 继续保留在审计/meta 中，但不再作为 `opencode` auth orchestration 的主判据。

### 3. waiting_auth 创建条件

对 `opencode`：
- `auth_detection.classification == auth_required`
- `confidence == high`
- request-side model 可解析 provider
- provider 能在 opencode provider registry 中解析出 auth mode

满足则进入 `waiting_auth`；否则保留失败并写出 `OPENCODE_PROVIDER_UNRESOLVED_FROM_MODEL` 诊断。

### 4. FCMP provider 一致性

FCMP `auth.required` / `auth.challenge.updated` 必须以 pending auth canonical provider 为准。若 orchestrator row data 未携带 provider，protocol translation 可回退到 pending auth payload，而不是输出 `null`。

## Risks / Trade-offs

- request model 非法时仍会失败。这个行为是保守且可诊断的。
- 此变更只修 `opencode`，不抽象成跨 engine 机制，可避免把 engine-local 规则过早写进 shared SSOT。
