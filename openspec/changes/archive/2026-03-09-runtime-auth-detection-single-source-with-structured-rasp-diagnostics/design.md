## Design Overview

本设计采用“单源证据 + parser 单次判定 + snapshot 消费 + 结构化诊断”。

### 1) Single Source of Auth Evidence

- engine-specific evidence：`server/engines/*/adapter/adapter_profile.json` 中 `parser_auth_patterns.rules`
- common fallback evidence：`server/engines/common/auth_detection/common_fallback_patterns.json`

规则声明仅描述“证据样式（match）”，不再携带流程动作声明。

### 2) Parser-First, One-Pass Auth Signal

四引擎 parser 统一通过共享 matcher 产出 `auth_signal`：

- `required`
- `confidence` (`high|low`)
- `matched_pattern_id`
- optional `provider_id`
- optional `reason_code`

其中：
- engine-specific match -> `high`
- common fallback match -> `low`

### 3) Lifecycle Snapshot Consumption

执行阶段在 `ProcessExecutionResult/EngineRunResult` 保存 `auth_signal_snapshot`。  
生命周期仅消费该快照，不再进行二次 rule detect。

状态推进规则：
- `high` + idle-blocking 条件可触发 early-exit，并进入 `waiting_auth`
- `low` 仅保留为诊断，不驱动 `waiting_auth`

### 4) Structured RASP Diagnostic

保留 RASP 事件外壳不变（category/type/source/seq/order），扩展：

- `event.type=diagnostic.warning`
- `data.code=AUTH_SIGNAL_MATCHED_HIGH|AUTH_SIGNAL_MATCHED_LOW`
- `data.auth_signal`:
  - `matched_pattern_id`
  - `confidence`
  - optional `provider_id`
  - optional `reason_code`

### 5) SSOT + Guard

- Schema 固化：
  - adapter profile：无 `classify`
  - auth fallback schema
  - runtime contract：`diagnostic.warning.data.auth_signal`
- Invariant 固化：
  - 单源证据
  - lifecycle 只消费 snapshot
  - `low` 不得进入 `waiting_auth`
  - auth 诊断必须走 `data.auth_signal`
