## Why

当前 runtime 仍存在“Parser + Detection 规则层”双层判定：
- parser 只产 diagnostics，auth_detection 再做二次映射。
- 运行时早退依赖 detection 服务的规则匹配，不是 parser 直接语义。

这会造成判定语义分散、配置重复和维护成本上升。新增样式时也容易出现 parser 与 detection 层不一致。

## What Changes

- 将鉴权样式声明单源收敛到 `adapter_profile` 的 `parser_auth_patterns.rules`。
- parser 直接基于声明规则产出统一 `auth_signal`。
- 运行时早退只消费 `auth_signal`：
  - `required=true`
  - `confidence=high`
  - 输出空闲超过 `SYSTEM.AUTH_DETECTION_IDLE_GRACE_SECONDS`
  - 触发 early-exit 并进入后续 `waiting_auth` 流程。
- lifecycle 终态鉴权判定改为从 `runtime_parse_result.auth_signal` 归一化，不再走 rule-registry 文本匹配层。

## Scope

- Affected code:
  - `server/contracts/schemas/adapter_profile_schema.json`
  - `server/runtime/adapter/common/profile_loader.py`
  - `server/runtime/adapter/common/parser_auth_signal_matcher.py` (new)
  - `server/runtime/adapter/types.py`
  - `server/engines/{codex,gemini,iflow,opencode}/adapter/{adapter_profile.json,stream_parser.py}`
  - `server/runtime/auth_detection/signal.py` (new)
  - `server/runtime/adapter/base_execution_adapter.py`
  - `server/services/orchestration/{job_orchestrator.py,run_job_lifecycle_service.py}`
  - `server/runtime/auth_detection/{service.py,rule_registry.py}`
  - tests under `tests/unit/test_auth_detection_*`, `tests/unit/test_adapter_failfast.py`, `tests/unit/test_adapter_profile_loader.py`
- API impact:
  - 无新增/删除 HTTP API。
- Runtime protocol impact:
  - 无 FCMP/RASP 事件类型变更；仅提升 auth_required 判定一致性与及时性。
