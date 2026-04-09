## Context

Claude 第三方 provider 的会话中鉴权早已落地为独立的 provider-config 路径：编排层会创建 `transport=provider_config` 的 waiting_auth challenge，并使用 `auth_method/challenge_kind/input_kind=custom_provider`。但主协议 schema 和主 specs 在后续统一 auth method 语义时删除了 `custom_provider`，导致当前实现虽然仍然输出这些值，却在 pending auth 持久化和事件校验时触发 `PROTOCOL_SCHEMA_VIOLATION`。

这次修复的重点不是重做 Claude custom provider 逻辑，而是把这条历史上已经存在、且当前代码仍依赖的语义重新纳入 shared SSOT。

## Goals / Non-Goals

**Goals:**
- 恢复 `custom_provider` 作为合法的 waiting_auth 协议值
- 让 runtime schema、主 specs、API 文档与现有 Claude provider-config 实现重新一致
- 保持当前 Claude custom provider waiting_auth 产品语义不变
- 用回归测试锁住 `pending_auth`、`auth.input.accepted` 和 FCMP `auth.required` 三条关键路径

**Non-Goals:**
- 不重做 Claude 1M context 配置合成
- 不把 `custom_provider` 扩成所有引擎立即共用的广义产品入口
- 不新增新的 auth transport；仅恢复既有 `provider_config` 语义

## Decisions

### 决策 1：恢复 `custom_provider`，而不是映射到 `api_key`

- 方案：在 runtime schema、交互模型和主 specs 中正式承认 `custom_provider`
- 原因：provider-config 会话表达的是“配置第三方 provider”，与单纯粘贴 API key 不是同一种 challenge；如果强行映射到 `api_key`，会丢失场景语义，并继续污染前端提示和审计解释
- 备选方案：映射到 `api_key`
- 不采用原因：会让历史实现、archived change 和当前 UI hint 全部失真

### 决策 2：恢复范围覆盖 method/challenge/input/selection/submission 全链路

- 方案：一次性补回以下枚举位置：
  - `pending_auth.auth_method`
  - `pending_auth.challenge_kind`
  - `pending_auth.input_kind`
  - `pending_auth_method_selection.available_methods`
  - `auth.input.accepted.submission_kind`
- 原因：当前 provider-config challenge 既需要等待态读模型，也需要 `interaction/reply` 和审计事件能完整通过；只补单个字段会留下新的 schema 断点

### 决策 3：shared specs 直接吸收 archived Claude provider-config 语义

- 方案：在 shared specs 中恢复 `provider_config/custom_provider` 语义，不再依赖 archived change 充当事实真源
- 原因：当前问题的根源就是 archived 语义没有回并主 SSOT，导致实现和主规格长期分叉

## Risks / Trade-offs

- [Risk] `custom_provider` 被恢复为正式合法值后，可能被误解为“所有引擎都必须支持这种等待态”  
  Mitigation: specs 和文档明确它主要用于 Claude 的 provider-config waiting_auth，属于合法协议值，不等于所有引擎立即提供该能力

- [Risk] 主协议重新放宽枚举后，历史测试可能遗漏新的合法路径  
  Mitigation: 增加 schema、FCMP 和 orchestration 三类回归，锁住 `pending_auth`、`auth.input.accepted` 和 `auth.required`
