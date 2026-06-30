# Design

## OpenCode / Kilo

OpenCode remains the SSOT for third-party OpenCode-family provider metadata. Kilo continues to reuse the OpenCode provider registry and adds only its `kilo` Gateway provider locally.

Google AntiGravity is removed from the exposed provider registry and strategy. The OpenCode bootstrap config also drops the AntiGravity plugin and `provider.google` model catalog so the default runtime config no longer advertises or enables that route.

New providers are API-key only. They reuse the existing OpenCode API-key auth flow and persist into the engine auth store with the standard OpenCode-family `{"type": "api", "key": "..."}` record shape.

## Qwen

Qwen OAuth is no longer exposed as a startable auth option. The Qwen auth runtime treats every remaining provider as API-key based.

The existing Coding Plan flow is generalized into a preset-driven settings writer. Coding Plan China/Global keep the current snapshot-backed model list and region-specific base URL behavior. Other Qwen providers use static presets derived from the current Qwen Code provider definitions and write:

- `modelProviders.openai`
- `env.<provider_env_key>`
- `security.auth.selectedType=openai`
- `model.name=<first preset model>`

Existing unrelated Qwen settings are preserved where possible; managed provider rows using the same known env keys/base URLs are replaced to avoid stale duplicates.

## Compatibility

The external auth session API shape does not change. Removed providers fail during provider registry lookup or driver support checks. Historical credential files are not deleted automatically.
