## Context

CodeBuddy Code provides headless stream JSON, exact-session resume, project skills, structured output and explicit MCP configuration. Its CLI and Python SDK also retain account state outside Skill Runner. Reusing host login or fixing a network environment on the server would break isolation and make domestic and international services indistinguishable.

This integration models one codebuddy engine with two virtual providers. The selected provider_id determines authentication, network routing, persistent CLI state, session continuation and model discovery. CodeBuddy output maps to existing Runtime/FCMP/RASP semantics; no new protocol event name is introduced.

Normative precedence is: machine contracts > delta specs > this design > the detailed artifact plan > tasks summaries.

## Goals / Non-Goals

### Goals

- Register a complete profile-driven engine after its adapter and auth path are usable.
- Offer explicit codebuddy-cn and codebuddy-global entry points.
- Keep raw credentials out of normal persistence, logs, audits, bundles, probes and APIs.
- Isolate SDK login, CLI state, model discovery, workspaces and MCP sources.
- Parse exit-zero errors and malformed rows without losing later valid terminal events.
- Preserve caller-controlled cache behavior.

### Non-Goals

- iOA, enterprise domain, custom endpoint, API key, apiKeyHelper or client credentials.
- Host login, keyring, configuration or MCP reuse.
- Inline TUI, worktree, tmux, sandbox, server or ACP modes.
- Multi-tenant credential ownership, external KMS or credential identity in cache keys.
- A static model manifest or new FCMP/RASP events.

## Decisions

### D1. Virtual provider is the routing authority

codebuddy-cn maps to SDK/runtime environment internal; codebuddy-global maps to public. A CodeBuddy job MUST provide one through engine_options.provider_id. Arbitrary environment and base URL input is rejected before cache lookup and process launch. Provider identity is retained through auth recovery and resume.

### D2. Credentials live in a provider-keyed service vault

The store is <data_dir>/engine_credentials/codebuddy.json; directory mode is 0700, file mode is 0600, and updates use atomic same-directory replacement. Public projections contain only missing|present|expired and timestamps. JWT expiry is advisory rather than cryptographic verification. Replacing or deleting one provider credential rotates only that provider's persistent config/session directory.

### D3. The official SDK runs only in an isolated worker

codebuddy-agent-sdk==0.3.205 is imported by a helper process. It starts with temporary HOME/XDG/config roots and a whitelisted environment because the SDK transport merges os.environ. Its first protocol message contains only the browser URL; the token crosses a private pipe and worker stdout is not persisted. Cancel, timeout and failure terminate descendants and clean temporary state; stderr is redacted before logging.

The generic runtime exposes oauth_proxy/auth_code_or_url and starting -> waiting_user -> succeeded|failed|expired|canceled. Only one active session is allowed per provider.

### D4. CLI state and models are provider scoped

Stable directories are <agent_home>/.codebuddy-runtime/codebuddy-cn/ and .../codebuddy-global/. Probe, start and resume share the selected directory. Each authenticated provider runs codebuddy --version and codebuddy --help. The catalog parses the --model “Currently supported” section, produces provider-qualified IDs, records environment/version/time/status/error/raw path, and preserves last-known-good data on failure. With no successful snapshot the list is empty, but model omission remains valid.

### D5. Run configuration is system owned

Every run materializes CODEBUDDY.md, .codebuddy/settings.json, .codebuddy/mcp.json and .codebuddy/skills/<skill-id>/. Settings disable updates, hooks, untrusted frontmatter hooks and automatic project MCP loading. First-release skill/runtime input cannot override them.

### D6. Command construction is explicit and symmetric

Each attempt is a fresh subprocess at cwd=run_dir. Start uses -p --output-format stream-json --permission-mode bypassPermissions; resume adds -r <session-id>. Both include managed settings, project-only setting sources, strict MCP, optional inline JSON schema and optional model. Unsupported flags are never emitted. The adapter removes inherited CodeBuddy credential/routing variables before injecting vault token, environment and config directory; runtime env options cannot override them.

### D7. MCP has one generated source

The registry renders mcpServers with explicit transport type fields and the existing secret resolver. An empty registry still writes an empty mcpServers object; both command paths always use --mcp-config and --strict-mcp-config.

### D8. CodeBuddy owns framing and terminal semantics

A stateful framer handles JSONL, repairs historical physical newlines inside strings, preserves byte ranges, reports malformed/over-limit/unterminated rows, and resynchronizes at independent valid events. Live and terminal parsing share it.

The first valid system.init supplies the session handle; repeated init on resume is valid. Thinking/text/tool blocks reuse an engine-neutral mapper shared with Claude, while framing, auth and terminal rules remain CodeBuddy-owned. Success requires a non-error success result; error result, is_error=true, or missing terminal result fails even with exit code zero. result.structured_output enters the shared pipeline.

### D9. Central activation occurs last

Machine schemas may recognize CodeBuddy early. Its parser capability remains in the contract's pre-activation declaration until the profile and parser exist; only then may it move into the active parser set. Active engine keys, adapter, install/upgrade, auth bootstrap, model lifecycle, API and UI are enabled together only after auth/catalog/adapter work is usable.

### D10. Cache remains caller controlled

The integration neither forces no_cache nor adds account/credential generation to cache keys. Existing provider/model engine options remain identity inputs. Relogin under the same provider can therefore reuse cache unless the caller sets no_cache=true; documentation must state this risk.

## Risks / Trade-offs

- The vault is service-level and single-instance; tenant isolation needs a future KMS-backed design.
- CLI help is account/version dependent; LKG retention is non-destructive but not necessarily fresh.
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

- A dedicated international test account is still an external release prerequisite.
- CLI 2.118.2 is only the investigation/golden baseline; production versions are recorded dynamically.
