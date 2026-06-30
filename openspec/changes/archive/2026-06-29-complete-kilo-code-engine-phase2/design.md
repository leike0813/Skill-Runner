## Context

Kilo Code phase 1 is already integrated as a managed execution engine. Kilo auth is currently declared as disabled, and the config composer rejects top-level `provider` roots. Local source and runtime probes show that Kilo Gateway official auth is a device authorization flow exposed by `api.kilo.ai`, while third-party provider auth/config follows the OpenCode lineage closely enough to reuse the existing OpenCode provider-aware machinery.

Kilo Gateway is special because auth uses Kilo's own `provider_id=kilo` OAuth record, while Kilo model catalog provider identity is derived from the model id by taking everything left of the final slash. For example, `kilo/openai/gpt-5.2` resolves to model provider `kilo/openai` and model `gpt-5.2`. Third-party providers should not get a parallel Skill Runner auth model; they should use the same provider IDs, auth modes, UI methods, and credential record shapes already supported for OpenCode where applicable.

## Goals / Non-Goals

**Goals:**

- Make Kilo a provider-aware engine in the shared auth strategy and provider registry.
- Implement Kilo Gateway device auth through `oauth_proxy` with immediate polling and no manual input requirement.
- Reuse OpenCode provider auth for non-Gateway Kilo providers, including API-key and supported OAuth providers.
- Allow Kilo native `provider` config in `.kilo/kilo.jsonc`.
- Preserve complete Kilo runtime model IDs and provider IDs.
- Keep secrets redacted in errors, logs, and config-related summaries.

**Non-Goals:**

- Do not manage Kilo Dashboard or Gateway BYOK settings.
- Do not implement `kilo auth login` as `cli_delegate`.
- Do not add a Kilo-specific third-party provider CRUD service.
- Do not replace OpenCode provider auth internals with a larger shared abstraction unless needed to avoid duplication.

## Decisions

1. **Provider-aware Kilo registry composes OpenCode providers**

   Kilo gets an engine-local provider registry so the shared provider-aware layer can treat it as a first-class engine. That registry prepends or appends a Kilo Gateway provider record and otherwise delegates to the OpenCode provider registry. This keeps OpenCode provider IDs and labels as the SSOT for third-party providers.

2. **Kilo Gateway uses a Kilo-local oauth_proxy flow**

   Auth `provider_id=kilo` uses a Kilo-specific flow that calls:

   - `POST https://api.kilo.ai/api/device-auth/codes`
   - `GET https://api.kilo.ai/api/device-auth/codes/<code>`

   Approved sessions write a Kilo-readable OAuth record under the managed XDG data home. The flow exposes `auth_url`, `user_code`, and expiry metadata through the existing auth session snapshot shape.

3. **Third-party providers delegate to OpenCode runtime behavior**

   For `provider_id != kilo`, Kilo's runtime handler reuses OpenCode's provider-aware runtime behavior. The plan avoids copying OpenCode's provider branching. If a delegated session is produced for Kilo, the externally visible engine remains `kilo`, but credential persistence uses the same OpenCode-compatible store unless implementation evidence shows Kilo requires an equivalent mirror in Kilo's own store.

4. **Config opens provider, MCP remains governed**

   Phase 2 removes the phase-1 rejection of top-level `provider` from skill/runtime `kilo_config`. Top-level `mcp` remains forbidden for user and skill layers and can only come from governed MCP config.

5. **Kilo model identity becomes multi-provider**

   Kilo profile changes `provider_contract.multi_provider` to `true`. Runtime model strings passed to the CLI remain complete IDs such as `kilo/openai/gpt-5.2` or `openai-compatible/my-model`; shared model normalization must not collapse them to a canonical provider or split Kilo model ids at the first slash.

## Risks / Trade-offs

- **Kilo third-party credential path may drift from OpenCode** -> Verify with tests and local source assumptions; if Kilo needs its own auth store, mirror the same record shape instead of inventing a new schema.
- **Gateway auth API may change** -> Keep the flow small, fail with redacted structured errors, and cover status variants in unit tests.
- **Delegating OpenCode behavior can leak engine labels** -> Kilo handler must normalize returned session engine/driver metadata where the session is externally visible.
- **Provider config can contain secrets** -> Redact `apiKey`, token-like fields, and headers in logs/errors.

## Migration Plan

Existing Kilo phase-1 execution remains valid. After this change, Kilo auth capabilities appear in the same provider-aware UI/API surfaces as OpenCode and Qwen. Existing `.kilo/kilo.jsonc` generation continues to work; configs that include `provider` begin to pass, while configs that include user-authored `mcp` still fail before launch.
