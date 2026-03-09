## 1. Single Source Migration

- [x] 1.1 Extend `adapter_profile_schema.json` with `auth_detection.rules`.
- [x] 1.2 Extend adapter profile loader to expose `auth_detection.rules`.
- [x] 1.3 Move codex/gemini/iflow/opencode auth detection rules into each `adapter_profile.json`.
- [x] 1.4 Switch `AuthDetectionRuleRegistry` to load rules from adapter profiles only.

## 2. Early Exit Mechanism

- [x] 2.1 Add incremental auth detection probe in `base_execution_adapter` read-stream phase.
- [x] 2.2 Add idle blocking early-exit (`AUTH_REQUIRED`) with global grace threshold.
- [x] 2.3 Add config key `SYSTEM.AUTH_DETECTION_IDLE_GRACE_SECONDS` (default 3).

## 3. Gemini Detection Refresh

- [x] 3.1 Add parser diagnostic `GEMINI_OAUTH_CODE_PROMPT_DETECTED`.
- [x] 3.2 Add gemini rule matching parser diagnostic -> `auth_required/high/oauth_reauth`.

## 4. Tests

- [x] 4.1 Update rule source tests to assert adapter-profile source and no YAML runtime loading.
- [x] 4.2 Add/adjust gemini tests for new diagnostic + rule hit.
- [x] 4.3 Run targeted pytest for auth detection + adapter parser/behavior.
