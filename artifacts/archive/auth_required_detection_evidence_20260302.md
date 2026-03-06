# Auth Required Detection Evidence (2026-03-02)

Related analysis:
- [auth_required_detection_analysis.md](/home/joshua/Workspace/Code/Python/Skill-Runner/docs/auth_required_detection_analysis.md)

## Scope
This note consolidates evidence for detecting authentication-required failures in backend-oriented agent execution.

Included evidence only covers samples intended to inform non-interactive backend detection. Interactive-only prompts such as browser URLs, device codes, and authorization-code entry remain background references and are not treated as primary backend indicators.

## Sample Source
- Capture batch: `2026-03-02`
- Source root: `data/harness_runs/20260302T*`
- Fixture mirror: `tests/fixtures/auth_detection_samples/`

## Strong-Evidence Samples
These samples provide backend-visible evidence that is strong enough to directly inform first-pass auth-required rules.

### Codex
- Stable evidence:
  - `401 Unauthorized`
  - `Missing bearer or basic authentication in header`
- Fixture:
  - `codex/openai_missing_bearer_401`
- Detection intent:
  - `auth_required/api_key_missing/high`

### Gemini
- Stable backend-visible evidence:
  - `Please set an Auth method`
  - `GEMINI_API_KEY`
  - `GOOGLE_GENAI_USE_VERTEXAI`
  - `GOOGLE_GENAI_USE_GCA`
- Fixture:
  - `gemini/auth_method_not_configured`
- Detection intent:
  - `auth_required/api_key_missing/high`

### iFlow
- Stable backend-visible evidence:
  - `SERVER_OAUTH2_REQUIRED`
  - `OAuth2 令牌已过期`
  - `需要重新认证`
  - `需要使用服务器OAuth2流程`
- Fixture:
  - `iflow/oauth_token_expired`
- Detection intent:
  - `auth_required/oauth_reauth/high`

### OpenCode
OpenCode requires provider-aware parsing. Primary evidence should come from structured payloads, not TUI interaction prompts.

Strong-evidence provider fixtures:
- `opencode/minimax_login_fail_401`
  - `statusCode=401`
  - response body carries `authentication_error`
- `opencode/moonshot_invalid_authentication`
  - `Invalid Authentication`
  - `invalid_authentication_error`
- `opencode/openrouter_missing_auth_header`
  - `Missing Authentication header`
  - provider code `401`
- `opencode/zai_token_expired_or_incorrect`
  - `token expired or incorrect`
- `opencode/deepseek_invalid_api_key`
  - `Authentication Fails ... api key ... invalid`
  - response body type `authentication_error`
- `opencode/opencode_invalid_api_key`
  - `Invalid API key.`
  - wrapper response type `AuthError`
- `opencode/google_api_key_missing`
  - `ProviderAuthError`
  - `providerID=google`
  - `API key is missing`

Expected interpretation:
- Prefer structured fields such as `error.name`, `statusCode`, `providerID`, `responseBody`, and provider message text.
- Do not rely on TUI-only prompts for OpenCode backend detection.

## Problematic Samples
These samples should be retained as evidence, but they are not clean first-pass rule templates. They represent cases where the underlying scenario is auth-related while the visible backend output is misleading, incomplete, or operationally abnormal.

### OpenCode
- `opencode/iflowcn_unknown_step_finish_loop`
  - Canonical sample id: `iflowcn_unknown_step_finish_loop`
  - User-confirmed auth failure, but current observable output is misleading
  - Repeatedly emits `step_start` / `step_finish(reason="unknown")` pairs instead of a stable provider-auth error
  - Does not terminate on its own; the captured run was stopped manually
  - The process exits only after manual `^C`, so this is operationally closer to a stuck loop than a normal failed turn
  - This sample should be treated as a problematic edge case, not a standard positive or negative template

## Background-Only Interactive References
The following patterns are valid references for upstream interactive auth flows, but should not become primary backend detection rules:
- `Please visit the following URL`
- `Enter the authorization code`
- `Open this link in your browser`
- `Enter this one-time code`

Source references:
- `references/codex/codex-rs/login/src/device_code_auth.rs`
- `references/gemini-cli/packages/core/src/code_assist/oauth2.ts`
- `references/opencode/packages/opencode/src/provider/auth.ts`
- `references/iflow2api/iflow2api/oauth.py`

## Categories That Should Not Be Strong-Detected Yet
These categories should remain conservative until more evidence is collected:
- Model errors without explicit auth semantics
- Provider failures without auth-related status/message fields
- OpenCode `step_finish reason="unknown"` style noise without auth evidence

## Implementation Constraints Implied by the Evidence
1. Backend auth detection should prioritize structured fields and backend-visible error text.
2. Interactive URL/code prompts must remain secondary background evidence only.
3. If a backend run ever emits interactive authorization prompts, it should be treated as execution-mode drift or abnormal output, not as a normal primary signal.
4. Future generic `waiting_user` inference must not override a high-confidence auth-required detection.
