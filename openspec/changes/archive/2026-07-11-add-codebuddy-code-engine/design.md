## Context

CodeBuddy Code provides headless stream JSON, exact-session resume, project skills, structured output and explicit MCP configuration. Its CLI and Python SDK also retain account state outside Skill Runner. Reusing host login or fixing a network environment on the server would break isolation and make domestic and international services indistinguishable.

This integration models one codebuddy engine with two virtual providers. The selected provider_id determines authentication, network routing, persistent CLI state, session continuation and selection from the provider-qualified static model manifest. CodeBuddy output maps to existing Runtime/FCMP/RASP semantics; no new protocol event name is introduced.

Normative precedence is: machine contracts > delta specs > this design > the detailed artifact plan > tasks summaries.

## Goals / Non-Goals

### Goals

- Register a complete profile-driven engine after its adapter and auth path are usable.
- Offer explicit codebuddy-cn and codebuddy-global entry points.
- Keep raw credentials out of normal persistence, logs, audits, bundles and APIs.
- Isolate SDK login, CLI state, workspaces and MCP sources.
- Parse exit-zero errors and malformed rows without losing later valid terminal events.
- Preserve caller-controlled cache behavior.

### Non-Goals

- iOA, enterprise domain, custom endpoint, API key, apiKeyHelper or client credentials.
- Host login, keyring, configuration or MCP reuse.
- Worktree, tmux, server or ACP modes. CodeBuddy inline TUI remains constrained by the existing UI-shell sandbox and lifecycle.
- Multi-tenant credential ownership, external KMS or credential identity in cache keys.
- Runtime model probing or new FCMP/RASP events.

## Decisions

### D1. Virtual provider is the routing authority

codebuddy-cn maps to SDK/runtime environment internal; codebuddy-global maps to public. A CodeBuddy job MUST provide one through engine_options.provider_id. Arbitrary environment and base URL input is rejected before cache lookup and process launch. Provider identity is retained through auth recovery and resume.

### D2. Credentials live in a provider-keyed service vault

The store is <data_dir>/engine_credentials/codebuddy.json; directory mode is 0700, file mode is 0600, and updates use atomic same-directory replacement. Public projections contain only missing|present|expired and timestamps. JWT expiry is advisory rather than cryptographic verification. Replacing or deleting one provider credential rotates only that provider's persistent config/session directory.

### D3. The official SDK runs only in an isolated worker

codebuddy-agent-sdk==0.3.205 is imported by a helper process. It starts with temporary HOME/XDG/config roots and a whitelisted environment because the SDK transport merges os.environ. Its first protocol message contains only the browser URL; the token crosses a private pipe and worker stdout is not persisted. Cancel, timeout and failure terminate descendants and clean temporary state; stderr is redacted before logging.

The generic runtime exposes oauth_proxy/auth_code_or_url and starting -> waiting_user -> succeeded|failed|expired|canceled. Only one active session is allowed per provider.

Missing or expired credentials fail before CLI launch with an engine-neutral high-confidence auth signal. Runtime 401/login-required evidence is detected from redacted stdout, stderr, and their combined text. Both paths reuse the canonical waiting-auth orchestration. Browser completion persists only the selected provider credential and automatically issues one resume ticket: an existing handle resumes its exact session/provider, while a preflight failure without a handle starts a new attempt. Failure, cancel, and timeout never requeue the job.

### D4. CLI state is provider scoped and models use an engine-local static manifest

Stable directories are <agent_home>/.codebuddy-runtime/codebuddy-cn/ and .../codebuddy-global/. Start and resume share the selected provider directory. Model discovery does not execute CodeBuddy or depend on credentials: the generic model registry reads `server/engines/codebuddy/models/manifest.json` and its pinned snapshot, whose model IDs and metadata are provider qualified. Both providers may expose the same raw model without collision, provider/model mismatches fail closed, and model omission remains valid.

### D5. Run configuration is system owned

Every run materializes CODEBUDDY.md, .codebuddy/settings.json, .codebuddy/mcp.json and .codebuddy/skills/<skill-id>/. Settings disable updates, hooks, untrusted frontmatter hooks and automatic project MCP loading. First-release skill/runtime input cannot override them.

### D6. Command construction is explicit and symmetric

Each attempt is a fresh subprocess at cwd=run_dir. Start uses -p --output-format stream-json --permission-mode bypassPermissions; resume adds -r <session-id>. Both include managed settings, project-only setting sources, strict MCP, optional inline JSON schema and optional model. Unsupported flags are never emitted. The adapter removes inherited CodeBuddy credential/routing variables before injecting vault token, environment and config directory; runtime env options cannot override them.

Headless execution and inline TUI share one CodeBuddy-owned managed-environment builder. It canonicalizes the explicit provider, clears inherited managed variables, checks credential state, and injects only the selected token, network environment, and provider-partitioned CLI state directory. Missing and expired states map to stable auth reason codes without exposing credential material.

### D7. MCP has one generated source

The registry renders mcpServers with explicit transport type fields and the existing secret resolver. An empty registry still writes an empty mcpServers object; both command paths always use --mcp-config and --strict-mcp-config.

### D8. CodeBuddy owns framing and terminal semantics

A stateful framer handles JSONL, repairs historical physical newlines inside strings, preserves byte ranges, reports malformed/over-limit/unterminated rows, and resynchronizes at independent valid events. Live and terminal parsing share it.

The live path consumes complete framed records incrementally and keeps only the state required for session identity, tool correlation, and terminal detection. The credential redactor releases complete physical records after equal-byte masking rather than retaining a fixed 8 KiB overlap, so semantic FCMP/RASP/chat events remain live without weakening cross-chunk secret matching.

The first valid system.init supplies the session handle; repeated init on resume is valid. Thinking/text/tool blocks reuse an engine-neutral mapper shared with Claude, while framing, auth and terminal rules remain CodeBuddy-owned. Success requires a non-error success result; error result, is_error=true, or missing terminal result fails even with exit code zero. result.structured_output enters the shared pipeline.

A parser-inferred missing-terminal failure applies only when output capture itself completed. If the fail-closed redaction/capture layer terminates the process, its `OUTPUT_REDACTION_FAILED` reason outranks any missing-terminal inference and raw output remains discarded.

### D9. Central activation occurs last

Machine schemas may recognize CodeBuddy early. Its parser capability remains in the contract's pre-activation declaration until the profile and parser exist; only then may it move into the active parser set. Active engine keys, adapter, install/upgrade, auth bootstrap, static model manifest, API and UI are enabled together only after auth and adapter work are usable.

### D10. Cache remains caller controlled

The integration neither forces no_cache nor adds account/credential generation to cache keys. Existing provider/model engine options remain identity inputs. Relogin under the same provider can therefore reuse cache unless the caller sets no_cache=true; documentation must state this risk.

### D11. CodeBuddy job UI belongs to the built-in example client

The existing `e2e_client` `/skills/{skill_id}/run` flow is the only browser-facing job launcher changed here. It derives provider choices from engine detail metadata, requires an explicit CodeBuddy provider, filters models by provider, and still submits through `POST /v1/jobs`. Management UI remains an engine administration surface and gains no job launcher, partial, or internal run endpoint.

### D12. Kilo reuses OpenCode MCP rendering

Kilo's native configuration accepts the same top-level `mcp` object and server payload shapes as OpenCode. The shared registry renderer therefore maps both engines to `mcp`; Kilo does not fork or copy an engine-specific renderer. Skill and runtime configuration remain unable to supply any MCP root directly.

### D13. Default installation and model probing follow confirmed availability

The default managed bootstrap set is exactly `opencode,codex`; Claude, Qwen, Kilo, and CodeBuddy remain selectable through explicit CLI, environment, or management actions. Gemini stays outside the active engine catalog as a deprecated sealed implementation, so explicit subsets and `all` reject or exclude it rather than installing it. Kilo model probing is allowed only when the latest status probe confirms `present=true` with no probe error. Absent or unknown status is a normal skip, not a background warning. A successful managed Kilo install refreshes status before scheduling one catalog refresh.

### D14. CodeBuddy TUI is provider explicit and session local

The existing UI-shell start route accepts an optional provider_id. CodeBuddy requires an explicit canonical provider whose managed credential is present; all other engines reject a supplied provider so it cannot be silently ignored. The provider picker is derived from management auth-provider metadata, starts empty, and never automatically launches after login.

The CodeBuddy interactive command uses no print, stream-output, or CLI permission-mode flags. It loads project settings only. Profile-driven session config writes `.codebuddy/settings.json` with Plan as the default mode, `deny=["*"]`, bypass/auto/subagent restrictions, and disabled hooks, untrusted hooks, automatic project MCP, updates, suggestions, and memory. A session-local empty `mcpServers` file is passed with strict MCP flags. The generic UI-shell manager consumes an engine-neutral launch plan; provider validation and credential environment construction remain engine-local.

## Risks / Trade-offs

- The vault is service-level and single-instance; tenant isolation needs a future KMS-backed design.
- A pinned manifest can lag provider-side model changes and therefore requires an explicit repository update when the supported list changes.
- Historical malformed traces are provenance-unverified and fixtures must say so.
- Hard worker cancellation favors bounded cleanup over preserving an ambiguous SDK transport.
- Cross-account cache reuse is an accepted, documented product trade-off.

## Migration Plan

1. Land contracts, umbrella artifacts and detailed plan without active registration.
2. Land provider/vault/auth/model components.
3. Land workspace/command/MCP/framer/parser and verify Claude mapper behavior.
4. Atomically enable registries, API/UI, harness, fixtures and docs.
5. Run strict OpenSpec, focused, runtime SSOT, golden and manual gates.

Rollback disables active registration and UI first while leaving the vault untouched. Credential deletion remains an explicit operator action.

## Open Questions

- CLI 2.118.2 is only the investigation/golden baseline; production versions are recorded dynamically.
