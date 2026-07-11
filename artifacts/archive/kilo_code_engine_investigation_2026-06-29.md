# Kilo Code Engine Investigation

Date: 2026-06-29

## Purpose

This note records the initial investigation for adding Kilo Code as a new Skill Runner engine. It focuses on configuration schema and authentication because those areas define most of the integration shape and OpenSpec scope.

No OpenSpec change was created during this investigation, and no implementation files were modified.

## External Kilo Facts

Official CLI documentation:

- Kilo CLI can be launched interactively with `kilo`.
- Non-interactive execution uses `kilo run "<task>"`.
- Authentication is managed by `kilo auth`.
- Model discovery is exposed through `kilo models`.
- Session import/export and session management are first-class CLI capabilities.
- `kilo run` supports JSON output, automatic execution, model selection, and session resume flags.

Relevant public sources:

- CLI documentation: <https://kilo.ai/docs/code-with-ai/platforms/cli>
- Official configuration schema: <https://app.kilo.ai/config.json>
- npm package: <https://www.npmjs.com/package/@kilocode/cli>

Package facts observed from npm:

- Package name: `@kilocode/cli`
- Binary names: `kilo`, `kilocode`
- Latest observed version: `7.3.54`
- Install command advertised by the package: `npm install -g @kilocode/cli`

## Local Probe Findings

Local probe date: 2026-06-29

Observed local installation:

- `kilo --version`: `7.3.54`
- `kilo` path: `/home/joshua/.nvm/versions/node/v24.12.0/bin/kilo`
- `kilocode` path: `/home/joshua/.nvm/versions/node/v24.12.0/bin/kilocode`
- Both commands point to the same npm launcher.
- The npm launcher runs a native binary at `@kilocode/cli/bin/.kilo`.
- The native binary is a Linux x86-64 ELF executable.

Kilo initializes local state even for help/list commands:

- Default config path: `~/.config/kilo/kilo.jsonc`
- Default data path: `~/.local/share/kilo`
- Default database path: `~/.local/share/kilo/kilo.db`
- Default credential path shown by `kilo auth list`: `~/.local/share/kilo/auth.json`

The default generated config file contains only:

```json
{
  "$schema": "https://app.kilo.ai/config.json"
}
```

The paths are XDG-aware. With isolated environment variables:

```text
XDG_CONFIG_HOME=<tmp>/config
XDG_DATA_HOME=<tmp>/data
XDG_CACHE_HOME=<tmp>/cache
```

Kilo uses:

- `<tmp>/config/kilo/kilo.jsonc`
- `<tmp>/data/kilo/kilo.db`
- `<tmp>/data/kilo/auth.json`
- `<tmp>/cache/kilo/models.json`

This is important for Skill Runner because managed execution can isolate Kilo state through XDG directories rather than by relying only on current working directory.

### Local Help Output

`kilo run --help` confirms the non-interactive command surface:

- Positional `message` array.
- `--format` choices: `default`, `json`.
- `--model` format: provider/model.
- `--session` resumes a session.
- `--continue` resumes the last session.
- `--auto` auto-approves all permissions.
- `--dangerously-skip-permissions` also exists, but `--auto` is the safer documented pipeline flag.
- `--dir` can set the run directory.
- `--variant` controls provider-specific reasoning effort.

`kilo auth --help` confirms:

- `kilo auth list`
- `kilo auth login [url]`
- `kilo auth logout`
- `kilo auth login` accepts:
  - `--provider`
  - `--method`

`kilo profile --help` confirms:

- `kilo profile`
- `kilo profile --json`

### Stdout JSONL Shape

`kilo run --format json --auto --model kilo/kilo-auto/free ...` emits JSONL on stdout and no stderr in successful runs.

Observed success events:

```json
{"type":"step_start","timestamp":1782726642906,"sessionID":"ses_...","part":{"id":"prt_...","messageID":"msg_...","sessionID":"ses_...","snapshot":"...","type":"step-start"}}
{"type":"text","timestamp":1782726643047,"sessionID":"ses_...","part":{"id":"prt_...","messageID":"msg_...","sessionID":"ses_...","type":"text","text":"first","time":{"start":1782726642988,"end":1782726643039}}}
{"type":"step_finish","timestamp":1782726643211,"sessionID":"ses_...","part":{"id":"prt_...","reason":"stop","snapshot":"...","messageID":"msg_...","sessionID":"ses_...","type":"step-finish","tokens":{"total":13196,"input":10871,"output":21,"reasoning":0,"cache":{"write":0,"read":2304}},"cost":0}}
```

Parser implications:

- Top-level `sessionID` is the canonical Kilo session id.
- `part.messageID` is the assistant message id.
- `part.text` carries text deltas or full text chunks.
- `part.reason` in `step_finish` carries the stop reason.
- `part.tokens` and `part.cost` are available on final events.
- `part.snapshot` may appear on `step-start` and `step-finish`.
- Event names use snake case at the top level, while `part.type` uses hyphenated names.

Resume behavior was verified:

- First run created `sessionID`.
- Second run with `--session <sessionID>` reused the same `sessionID`.
- The stdout shape stayed the same.

Recommended command shape after probe:

```text
kilo run --format json --auto --model <model-id> <prompt>
```

Resume:

```text
kilo run --format json --auto --session <session-id> --model <model-id> <prompt>
```

The command builder may also pass `--dir <run-dir>`, although process `cwd` isolation may be sufficient.

### Error JSONL Shape

Errors can also be emitted as JSONL on stdout.

Observed unknown model error:

```json
{"type":"error","timestamp":1782726582652,"sessionID":"ses_...","error":{"name":"UnknownError","data":{"message":"Model not found: openai/gpt-5.2. Did you mean: gpt-5.2, gpt-5.2-pro, gpt-5.2-codex?"}}}
```

Observed paid Kilo model auth error:

```json
{"type":"error","timestamp":1782726612456,"sessionID":"ses_...","error":{"name":"APIError","data":{"message":"You need to sign in to use this model.","statusCode":401,"isRetryable":false,"responseBody":"{\"error\":{\"code\":\"PAID_MODEL_AUTH_REQUIRED\",\"message\":\"You need to sign in to use this model.\"},\"error_type\":\"paid_model_auth_required\"}","metadata":{"url":"https://api.kilo.ai/api/openrouter/responses"}}}}
```

Important parser/runtime implication:

- The paid-model auth error exited with process code `0`.
- The adapter must treat Kilo `type:error` stdout events as failures even when the process exits successfully.
- Auth detection should inspect JSONL stdout, not only stderr or process return code.

### Model Catalog Probe

`kilo models` returns one model id per line.

Observed counts:

- `kilo models`: 335 lines.
- `kilo models kilo`: 252 lines.

Examples:

```text
kilo/kilo-auto/free
kilo/kilo-auto/small
kilo/kilo-auto/balanced
kilo/openai/gpt-5.2
opencode/qwen3.6-plus
opencode-go/qwen3.6-plus
alibaba-coding-plan/qwen3-coder-plus
```

Runtime-probe implication:

- Kilo model probing is easier than OpenCode because the default output is already a stable line list.
- No JSON parser is required for initial model discovery.
- A static manifest is still simpler for the first OpenSpec change, but runtime probing is technically low-risk.

Model id caveat:

- Some displayed model ids did not work when passed directly to `--model`.
- `kilo/openai/gpt-5.2` was accepted and reached provider auth.
- `openai/gpt-5.2` was rejected and suggested `gpt-5.2`.
- `opencode-go/qwen3.6-plus` was rejected and suggested `qwen3.6-plus`.

The model registry design should avoid assuming every `kilo models` line is immediately valid for `--model` without normalization or verification.

### Config Injection Probe

The installed SDK exposes `KILO_CONFIG_CONTENT` merging behavior in `@kilocode/sdk`.

Observed implementation:

- Existing `KILO_CONFIG_CONTENT` is parsed as JSON.
- Incoming config is merged over existing config.
- `agent`, `command`, `mcp`, and `mode` are shallow-merged objects.
- `plugin` and `instructions` are concatenated arrays.

Probe result:

```text
KILO_CONFIG_CONTENT='{"model":"kilo/kilo-auto/free"}' kilo run --format json --auto ...
```

This succeeded without passing `--model`, proving that `KILO_CONFIG_CONTENT` is recognized by the CLI run path.

Config composer implication:

- Prefer environment-based config injection for per-run generated config when possible.
- Keep file-based `kilo.jsonc` bootstrap for global/default managed home setup.
- This may be cleaner than writing a per-run `kilo.jsonc`, because it avoids JSONC write concerns and follows Kilo SDK behavior.

### Auth Probe

`kilo auth list` in a fresh isolated environment with no relevant provider env vars showed:

```text
Credentials <data>/kilo/auth.json
0 credentials
```

With the user's normal shell environment, `kilo auth list` also detected provider credentials from environment variables:

```text
OpenCode Go OPENCODE_API_KEY
Alibaba Coding Plan (China) ALIBABA_CODING_PLAN_API_KEY
OpenCode Zen OPENCODE_API_KEY
Alibaba Coding Plan ALIBABA_CODING_PLAN_API_KEY
```

No credential values were printed.

Kilo Gateway account auth:

- `kilo profile --json` in an isolated unauthenticated environment exits with code `1`.
- stderr contains: `Error: Not authenticated with Kilo Gateway`.

Paid model auth:

- `kilo run --format json --auto --model kilo/openai/gpt-5.2 ...` in an isolated unauthenticated environment emits a JSONL `type:error` event.
- Error message: `You need to sign in to use this model.`
- `statusCode`: `401`
- response body includes `PAID_MODEL_AUTH_REQUIRED` and `paid_model_auth_required`.
- Process exit code observed: `0`.

Free model behavior:

- `kilo run --format json --auto --model kilo/kilo-auto/free ...` succeeds even with isolated HOME/XDG and no provider env vars.
- This means Kilo should not be modeled as globally unauthenticated just because no credentials exist.

`kilo auth login` behavior:

- In non-interactive shell capture, `kilo auth login` and `kilo auth login --provider kilo` did not produce stdout/stderr within the expected timeout and left child processes running until manually terminated.
- This suggests login should be treated as a PTY/browser delegated flow, not a simple command whose stdout can be parsed reliably.
- Any auth driver using `kilo auth login` should be designed conservatively and tested with process-group cleanup.

Auth design correction after probe:

- Kilo has at least three credential modes:
  - Kilo free/anonymous model path.
  - Kilo Gateway account path for paid Kilo models and profile.
  - Provider env/API-key paths such as `OPENCODE_API_KEY` and `ALIBABA_CODING_PLAN_API_KEY`.
- Initial Skill Runner support should distinguish account auth failures from provider auth failures.
- Engine status should not report Kilo as unusable only because `kilo profile` is unauthenticated.

### Gateway, BYOK, and Direct Provider Probe

Follow-up probe date: 2026-06-29

The user observed that `kilo auth login` triggered a local prompt to open `app.kilo.ai`. This matches the probe evidence and changes the auth model:

- `kilo auth login` is primarily a Kilo Gateway account/subscription login flow.
- Kilo Gateway BYOK is managed through the Kilo platform/account layer.
- Direct third-party providers are configured through Kilo config, not through `kilo auth login`.

Public docs and schema evidence:

- Kilo Gateway authentication documents `KILO_API_KEY` as a gateway credential for Kilo's API.
- Gateway BYOK is described as adding provider API keys in Kilo dashboard or Kilo extension settings, then routing through Kilo Gateway.
- The Kilo config schema defines `provider` as an object whose keys are provider ids and whose values are `ProviderConfig`.
- `ProviderConfig.options` supports `apiKey`, `baseURL`, `enterpriseUrl`, and timeout fields.
- `Config.enabled_providers` and `Config.disabled_providers` control provider availability.

Local probe evidence:

- `KILO_API_KEY=dummy-not-secret kilo auth list` shows `Kilo Gateway KILO_API_KEY`.
- `provider.openai.options.apiKey="{env:OPENAI_API_KEY}"` passes `kilo config check`.
- With `OPENAI_API_KEY` set and that config injected, `kilo auth list` shows `OpenAI OPENAI_API_KEY`.
- `provider.openai.options.apiKey="dummy-not-secret"` also passes `kilo config check`, but `kilo auth list` does not display it as a credential.
- A custom provider such as `openai-compatible` with `options.apiKey`, `options.baseURL`, and `models` passes `kilo config check`.
- `kilo models openai-compatible` lists the custom configured model.

Minimal custom direct-provider config that passed local validation:

```json
{
  "provider": {
    "openai-compatible": {
      "options": {
        "apiKey": "{env:MY_PROVIDER_API_KEY}",
        "baseURL": "https://example.invalid/v1"
      },
      "models": {
        "my-model": {
          "name": "My Model",
          "tool_call": true,
          "limit": {
            "context": 128000,
            "output": 16384
          }
        }
      }
    }
  },
  "model": "openai-compatible/my-model"
}
```

Security observation:

- `kilo config check` can print the expanded config input on validation errors.
- If a config uses `{env:SECRET_NAME}`, the error output may contain the resolved secret value.
- Skill Runner should redact Kilo config-check stderr/stdout before logging or surfacing it.

Updated auth model:

- Kilo Gateway account auth:
  - `kilo auth login`
  - `KILO_API_KEY`
  - paid/free Kilo Gateway model routing
- Gateway BYOK:
  - Managed by Kilo account/dashboard or Kilo extension settings.
  - Externally still appears as Kilo Gateway routing.
  - Should not be implemented as a Skill Runner provider-aware auth registry in the initial change.
- Direct third-party provider auth:
  - Implemented through `kilo_config.provider.<id>.options.apiKey`.
  - Prefer `{env:...}` references rather than writing plaintext keys into config files.
  - Model availability can be controlled by custom `provider.<id>.models`.

OpenSpec implication:

- Kilo auth strategy should remain engine-scoped for Gateway account status and delegated login.
- Third-party provider configuration should be treated as engine config, not as a separate Skill Runner auth provider registry.
- The Kilo config composer must preserve arbitrary `provider` objects and `options.apiKey` fields while applying normal secret redaction rules to logs.

### Source-Based Gateway Auth Proxy Investigation

Follow-up source probe date: 2026-06-30

Source tree inspected:

- `references/kilocode/packages/kilo-gateway/src/auth/device-auth-tui.ts`
- `references/kilocode/packages/kilo-gateway/src/plugin.ts`
- `references/kilocode/packages/kilo-gateway/src/types.ts`
- `references/kilocode/packages/kilo-gateway/src/api/constants.ts`
- `references/kilocode/packages/opencode/src/auth/index.ts`
- `references/kilocode/packages/opencode/src/provider/auth.ts`
- `references/kilocode/packages/opencode/src/server/routes/instance/httpapi/groups/provider.ts`
- `references/kilocode/packages/opencode/src/server/routes/instance/httpapi/handlers/provider.ts`
- `references/kilocode/packages/kilo-console/src/client.ts`
- `references/kilocode/packages/kilo-console/src/routes/profile/LoginRoute.tsx`
- `references/kilocode/packages/core/src/global.ts`

Core conclusion:

- It is feasible to implement an official Kilo Gateway web auth proxy in Skill Runner.
- The flow should be described as Kilo Gateway Device Authorization, not as a generic OAuth redirect/PKCE flow.
- The official Kilo web/console implementation already uses a browser-facing flow backed by device-code polling.
- Skill Runner does not need a local browser callback port for Kilo Gateway account auth.

Official flow shape from source:

1. Start auth by calling:

   ```text
   POST https://api.kilo.ai/api/device-auth/codes
   ```

2. Response shape:

   ```json
   {
     "code": "...",
     "verificationUrl": "https://app.kilo.ai/device-auth?code=...",
     "expiresIn": 599
   }
   ```

3. Ask the user/browser to open `verificationUrl`.
4. Poll:

   ```text
   GET https://api.kilo.ai/api/device-auth/codes/<code>
   ```

5. Poll statuses:

   - HTTP `202`: pending, represented as `{ "status": "pending" }`.
   - HTTP `403`: denied.
   - HTTP `410`: expired.
   - HTTP `200`: approved, response includes `token` and `userEmail`.

6. On approval, Kilo stores the returned token as both `access` and `refresh` in an OAuth auth record.

Kilo source details:

- `KILO_API_BASE` defaults to `https://api.kilo.ai` and is overrideable through `KILO_API_URL`.
- Poll interval is `3000` ms.
- `authenticateWithDeviceAuthTUI()` returns an `AuthOAuthResult` with:
  - `url`: Kilo `verificationUrl`
  - `instructions`: includes the device code
  - `method`: `auto`
  - `callback()`: performs device-code polling and returns auth credentials
- Successful callback returns:

  ```json
  {
    "type": "success",
    "provider": "kilo",
    "refresh": "<token>",
    "access": "<token>",
    "expires": 1780000000000
  }
  ```

Auth persistence contract from source:

- Kilo/OpenCode auth file path is `Global.Path.data/auth.json`.
- `Global.Path.data` resolves to `<XDG_DATA_HOME>/kilo` when XDG is isolated.
- Provider auth key for Kilo Gateway is `kilo`.
- Stored OAuth record shape is:

  ```json
  {
    "kilo": {
      "type": "oauth",
      "refresh": "<token>",
      "access": "<token>",
      "expires": 1780000000000
    }
  }
  ```

This means the Skill Runner auth proxy and subsequent `kilo run` / `kilo models` executions must share the same Kilo XDG environment. If they do, the official Kilo CLI will naturally pick up the login state.

Existing official web API surface:

- Kilo's internal OpenCode HTTP API exposes:
  - `GET /provider/auth`
  - `POST /provider/:providerID/oauth/authorize`
  - `POST /provider/:providerID/oauth/callback`
- For `providerID = kilo` and `method = 0`, these routes execute the same Kilo Gateway device auth flow.
- Kilo Console uses this two-step API:
  - `startKiloLogin()` calls provider OAuth authorize.
  - `completeKiloLogin()` calls provider OAuth callback and waits for the device-code polling result.
- Console then opens the returned auth URL in the browser and shows the device code.

Implementation implication for Skill Runner:

- Preferred design is a Skill Runner native auth session for Kilo Gateway:
  - `start`: call Kilo device-code endpoint, return `verificationUrl`, redacted/display code, `expiresIn`, and a local auth-session id.
  - `poll/complete`: poll the Kilo endpoint until approved, denied, expired, cancelled, or timed out.
  - `persist`: write the Kilo OAuth record into the engine-managed XDG data directory, using the same path that later Kilo executions will use.
  - `verify`: optionally call `kilo profile --json` or Kilo `/api/profile` with the returned token.
- An alternative is to run a Kilo server/instance and call its `/provider/kilo/oauth/authorize` and `/callback` endpoints. That maximizes reuse of Kilo's provider auth implementation, but is heavier and couples Skill Runner auth to a long-lived Kilo server process.
- Calling `kilo auth login` as a black-box subprocess is less desirable because it is interactive, opens a browser, waits internally, and is harder to cancel and observe reliably.

Live endpoint probe:

- A direct probe of `POST https://api.kilo.ai/api/device-auth/codes` returned HTTP `200` with `verificationUrl` and `expiresIn`.
- An immediate `GET` against the returned code endpoint returned HTTP `202` and pending status.
- The device code from the probe was treated as sensitive and was not recorded in this artifact.
- The live `expiresIn` observed during this probe was around 10 minutes; Kilo Console currently uses a 15 minute UI fallback. Skill Runner should use the server-provided `expiresIn`.

Security and logging implications:

- Device codes, tokens, `Authorization` headers, `responseHeaders`, cookies, and auth file contents must be redacted from logs and error summaries.
- Kilo error JSONL can include large response metadata; auth detection should extract semantic fields and avoid surfacing raw response headers.
- Directly writing `auth.json` is feasible, but should be isolated to the Kilo engine auth component and guarded by schema validation and file permission handling.

Updated auth design conclusion:

- Phase 2 can support Kilo Gateway account login through a managed web/device auth session.
- This should be engine-scoped Kilo Gateway auth, not provider-aware auth registry support.
- Kilo Gateway BYOK remains a Kilo account/dashboard concern.
- Direct third-party providers remain config-driven through `kilo_config.provider.<id>`, preferably using environment references for secrets.

Recommended internal engine identifier: `kilo`.

Rationale:

- Existing engine identifiers are short CLI-style names: `codex`, `opencode`, `claude`, `qwen`.
- The primary binary is `kilo`.
- Display surfaces can still label the engine as `Kilo Code`.

## Local Architecture Findings

Adding Kilo is not isolated to `server/engines/kilo`. The current engine set is constrained by schema enums, engine registries, bootstrap behavior, auth strategy schema, tests, and UI metadata.

Known integration points:

- `server/config_registry/keys.py`
  - Add `kilo` to active `ENGINE_KEYS`.
- `server/engines/__init__.py`
  - Export `kilo`.
- `server/contracts/schemas/adapter_profile_schema.json`
  - Add `kilo` to the engine enum.
- `server/contracts/schemas/engine_auth_strategy.schema.json`
  - Add `kilo` to required engine auth strategies and properties.
- `server/contracts/schemas/mcp_registry.schema.json`
  - Add `kilo` if MCP governance applies to Kilo.
- `server/contracts/schemas/skill/skill_runner_manifest.schema.json`
  - Add `kilo` wherever skill manifests enumerate supported engines.
- `server/services/engine_management/engine_adapter_registry.py`
  - Register and validate the Kilo adapter profile.
- `server/services/engine_management/engine_upgrade_manager.py`
  - Add Kilo to supported managed engines.
- `server/services/engine_management/agent_cli_manager.py`
  - Add package/bootstrap fallback behavior.
- `server/runtime/auth_detection/detector_registry.py`
  - Add Kilo auth detection if the engine emits recognizable auth failures.
- `server/runtime/auth_detection/rule_registry.py`
  - Kilo parser auth patterns should be loaded from its adapter profile.
- `server/services/engine_management/model_registry.py`
  - Kilo needs either a static model manifest or a runtime probe integration.
- UI engine metadata and templates
  - Add Kilo labels, status display, and optional MCP controls.
- Unit tests
  - Update engine set assertions, schema validation tests, bootstrap tests, auth strategy tests, adapter profile loader tests, status cache tests, and upgrade manager tests.

Existing references that are useful as implementation templates:

- `docs/developer/adapter_component_guide.md`
- `docs/developer/auth_runtime_driver_guide.md`
- `openspec/changes/archive/2026-04-05-add-qwen-code-engine/`
- `server/engines/opencode/`
- `server/engines/qwen/`

## Configuration Schema Implications

Kilo has an official JSON schema at `https://app.kilo.ai/config.json`. The integration should treat this as the primary schema source for engine-specific config validation.

Recommended assets:

- `server/engines/kilo/schemas/kilo_config_schema.json`
- `server/engines/kilo/config/default_config.json`
- `server/engines/kilo/config/enforced_config.json`
- `server/engines/kilo/config/auth_strategy.yaml`
- `server/engines/kilo/adapter/adapter_profile.json`
- `server/engines/kilo/adapter/config_composer.py`
- `server/engines/kilo/adapter/command_builder.py`
- `server/engines/kilo/adapter/execution_adapter.py`
- `server/engines/kilo/adapter/stream_parser.py`

Recommended runtime config option:

- `kilo_config`

Recommended skill package fallback asset:

- `assets/kilo_config.json`

Kilo appears to use JSONC-style config files. The existing bootstrap/profile loader only supports `json` and `text` bootstrap formats. Initial support should avoid introducing a JSONC writer unless it is necessary.

Recommended first-pass approach:

- Validate config with the Kilo JSON schema.
- Write standard JSON content to the Kilo config target path.
- Use a `.jsonc` target path if the CLI expects that name, because JSON is valid JSONC.

Open question:

- Confirm the exact config discovery path used by the Kilo CLI when running under a managed `cwd` and isolated agent home. The likely target is `run_dir/kilo.jsonc`, but this should be verified against the real CLI.

## Command and Output Shape

Kilo's CLI appears close to OpenCode-style execution.

Expected start command shape:

```text
kilo run --auto --format json --model <provider/model> <prompt>
```

Expected resume command shape:

```text
kilo run --session <session-id> --auto --format json --model <provider/model> <prompt>
```

The exact argument ordering should be verified with the real CLI. Kilo documentation examples suggest `kilo run <task> --format json` is accepted, so the command builder should follow documented CLI behavior rather than assume strict OpenCode compatibility.

Stream parsing should be straightforward if `--format json` emits one JSON event per line. A Kilo parser can likely follow the same design as the OpenCode or Qwen stream parsers:

- Parse JSON lines from stdout.
- Extract session identity once it appears.
- Extract assistant/output deltas.
- Extract final result/status.
- Treat stderr auth and process failures through the existing auth detection layer.

Open question:

- Capture a real `kilo run --format json` sample before locking parser semantics.

## Authentication Findings

Authentication is the highest-risk area because the public docs clearly expose `kilo auth`, but do not fully specify a stable file-level credential contract.

Known facts:

- Kilo CLI supports `kilo auth`.
- API keys are optional according to the npm README.
- Users can use Kilo credits or bring their own keys.

Not yet confirmed:

- Credential file path.
- Credential file schema.
- Whether `kilo auth` supports a non-interactive machine-readable flow.
- Whether BYOK provider configuration has a stable writable config contract.
- Which providers should be exposed in Skill Runner if provider-aware auth is desired.

Recommended first OpenSpec scope:

- Treat Kilo as an engine-scoped auth integration.
- Use `cli_delegate` auth via `kilo auth`.
- Add auth detection patterns for:
  - not authenticated
  - run `kilo auth`
  - missing API key
  - invalid API key
  - provider 401/403 failures
- Allow credential/config import only after the file path and schema are confirmed.
- Do not initially implement full provider-aware BYOK management.

Reasoning:

- Kilo supports a broad provider/model ecosystem, so provider-aware auth could become large quickly.
- Without a stable credential file contract, writing auth files directly is fragile.
- CLI-delegated auth is the least speculative initial integration path.

Alternative scope:

- Implement provider-aware BYOK support for a deliberately small provider subset.

This requires a product decision before design:

- Which providers should be exposed?
- Should Kilo account/credits be represented as a provider?
- Should OpenRouter or another aggregator be the default BYOK route?

## Model Catalog

Kilo exposes `kilo models`, so runtime model probing is possible. However, the existing runtime probe lifecycle has OpenCode-specific behavior.

Recommended first-pass option:

- Start with a static model manifest and snapshot for Kilo.
- Add runtime model probing later after the engine execution path is stable.

Alternative:

- Add a Kilo-specific `kilo models` runtime probe during the initial change.

Tradeoff:

- Runtime probing is more dynamic but expands implementation and test scope.
- Static manifest is easier to validate and keeps the first engine integration smaller.

## Suggested OpenSpec Change Scope

Suggested change id:

- `add-kilo-code-engine`

Likely specs to update:

- `engine-adapter-runtime-contract`
- `engine-runtime-config-layering`
- `engine-auth-strategy-policy`
- `engine-auth-observability`
- `engine-status-cache-management`
- `engine-upgrade-management`
- `local-deploy-bootstrap`
- `ui-engine-management`
- `external-runtime-harness-cli`
- `mcp-config-governance`
- skill manifest/schema specs that enumerate engine IDs

Core implementation areas:

- Engine key and registry additions.
- Kilo adapter profile and adapter components.
- Kilo config schema and config composer.
- Kilo auth strategy and auth detection.
- Kilo package/bootstrap management.
- Optional Kilo model manifest.
- UI engine metadata.
- Unit tests for schema, registry, bootstrap, auth, parser capability, and managed engine status.

## Decisions Needed Before Design

1. Auth scope:
   - Recommended: engine-scoped Kilo Gateway auth first, covering `kilo auth login`, `KILO_API_KEY`, and JSONL auth detection.
   - Direct third-party provider keys should be handled through `kilo_config.provider.*.options`, not through a Skill Runner provider-aware auth registry.

2. Config target path:
   - Confirmed default global path: `~/.config/kilo/kilo.jsonc`.
   - Recommended per-run path: inject generated runtime config through `KILO_CONFIG_CONTENT`.

3. Output parser contract:
   - Confirmed real `kilo run --format json` transcripts exist in `artifacts/kilo_code_stdout_sample-*.jsonl`.
   - Parser tests should cover success events, `type:error` events, and auth errors with process exit code `0`.

4. Model catalog:
   - Recommended: static manifest first.
   - Alternative: implement `kilo models` runtime probe in the first change.

## Recommended Next Step

Create an OpenSpec change named `add-kilo-code-engine` after confirming the auth scope. The design should explicitly state that initial Kilo authentication is CLI-delegated unless provider-aware BYOK support is selected as part of the change.

## 执行样例

### 样例1（工具调用与推理）：

- 命令：
```shell
kilo run --auto -m alibaba-coding-plan-cn/qwen3.7-plus --format json "去搜索一下美国和伊朗的摩擦的最新情况，然后编写一个脚本，计算从这场摩擦开始到现在经过了多少天，然后找到这个天数的所有质因数分解结果"
```
- stdout输出：`artifacts/kilo_code_stdout_sample-1.jsonl`

### 样例2（多轮对话）：

- 第一轮命令：
```shell
kilo run --auto -m alibaba-coding-plan-cn/qwen3.7-plus --format json "尝试问我三个问题，然后从我的回答中推断出我的职业。**要求：每次只能问一个问题，一个一个来。**"
```
- 第一轮stdout输出：`artifacts/kilo_code_stdout_sample-2.attempt-1.jsonl`
- 第二轮命令：
```shell
kilo run --auto -m alibaba-coding-plan-cn/qwen3.7-plus --format json -s ses_0ed4389d7ffe8ad96D6gXGfIre "电脑"
```
- 第二轮stdout输出：`artifacts/kilo_code_stdout_sample-2.attempt-2.jsonl`
- 第三轮命令：
```shell
kilo run --auto -m alibaba-coding-plan-cn/qwen3.7-plus --format json -s ses_0ed4389d7ffe8ad96D6gXGfIre "写代码、写文章、处理数据"
```
- 第三轮stdout输出：`artifacts/kilo_code_stdout_sample-2.attempt-3.jsonl`
- 第四轮命令：
```shell
kilo run --auto -m alibaba-coding-plan-cn/qwen3.7-plus --format json -s ses_0ed4389d7ffe8ad96D6gXGfIre "既有面向学术界的论文，也有面向公众的软件、教程等等，也有给公司内部团队用的产品/报告"
```
- 第四轮stdout输出：`artifacts/kilo_code_stdout_sample-2.attempt-4.jsonl`
