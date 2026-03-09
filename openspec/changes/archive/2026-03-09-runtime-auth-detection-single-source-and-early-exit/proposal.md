## Why

当前 runtime 鉴权判定存在两处问题：
- 规则来源仍是 `server/engines/auth_detection/*.yaml`，与 adapter profile 并行，存在双源漂移风险。
- run 执行仅在进程退出后才做 auth detection；当 CLI 进入“等待授权码输入”并阻塞时，run 会卡在 `running`，无法自动进入 `waiting_auth`。

这会导致新版本 CLI 输出样式变化后，鉴权判定滞后甚至失效，影响会话稳定性。

## What Changes

- 将 auth detection 规则单源迁移到各引擎 `adapter_profile.json` 的 `auth_detection.rules`。
- `AuthDetectionRuleRegistry` 改为仅从 adapter profile 加载规则（硬切，不再读 YAML rule pack）。
- 在 `base_execution_adapter` 增加增量鉴权探测与阻塞早退：
  - 命中 `auth_required + high`
  - 进程持续空闲超过 `SYSTEM.AUTH_DETECTION_IDLE_GRACE_SECONDS`（默认 3s）
  - 提前终止本轮 CLI，返回 `failure_reason=AUTH_REQUIRED` 进入后续 `waiting_auth` 流程。
- Gemini parser 补充新诊断码 `GEMINI_OAUTH_CODE_PROMPT_DETECTED`，对应规则走诊断码匹配，不把交互文案写入规则。

## Scope

- Affected code:
  - `server/contracts/schemas/adapter_profile_schema.json`
  - `server/runtime/adapter/common/profile_loader.py`
  - `server/engines/{codex,gemini,iflow,opencode}/adapter/adapter_profile.json`
  - `server/runtime/auth_detection/rule_registry.py`
  - `server/runtime/adapter/base_execution_adapter.py`
  - `server/engines/gemini/adapter/stream_parser.py`
  - `server/config.py`
  - `tests/unit/test_auth_detection_rule_loader.py`
  - `tests/unit/test_auth_detection_gemini.py`
  - `tests/unit/test_gemini_adapter.py`
- API impact:
  - 无新增/删除 HTTP API。
- Runtime protocol impact:
  - 无事件类型变更；仅提高 `AUTH_REQUIRED` 判定及时性。
