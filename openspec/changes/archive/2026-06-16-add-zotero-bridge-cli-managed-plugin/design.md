## Context

The runner already owns a managed runtime profile with an agent cache, agent home, npm prefix, and subprocess PATH construction. Engine CLIs are installed under the managed prefix, and `AgentCliManager.ensure_layout()` is the common local/container bootstrap hook. Zotero Bridge should follow the same deployment boundary: a managed executable on PATH plus global agent skill instructions, not per-run copies.

The bundle comes from `https://github.com/leike0813/Zotero-Skills.git` on branch `host-bridge/zotero-bridge-cli-bundle`. It contains:

- `manifest.json`
- platform binaries under `bin/<platform>/`
- `skills/zotero-bridge-cli/`
- `profile.template.json`

## Goals / Non-Goals

**Goals:**
- Make `zotero-bridge` available through managed PATH after local or Docker bootstrap.
- Keep wrapper skill installation global to managed agent homes.
- Use bundle manifest platform entries and SHA256 before installing a binary.
- Provide a managed `ZOTERO_BRIDGE_PROFILE` path to agent subprocesses.
- Keep endpoint, token, and connection mode outside static profiles and rely on `runtime_options.env`.
- Keep the installer idempotent.

**Non-Goals:**
- Registering a Zotero MCP server.
- Materializing run-local CLI shims or run-local wrapper skill copies.
- Storing fixed bridge endpoint or bearer token in engine profiles, settings, audit, or bundle files.
- Providing unsupported platform binaries beyond those present in the bundle manifest.

## Decisions

1. **Use the managed prefix bin directory as the CLI registration point.**  
   POSIX installs `zotero-bridge` into `<npm_prefix>/bin`. Windows installs `zotero-bridge.exe` into `<npm_prefix>/bin` and writes a `zotero-bridge.cmd` shim. The runtime profile already prepends managed bin directories to PATH.

2. **Install from the bundle manifest, not hard-coded paths.**  
   The installer reads `manifest.json`, maps the current OS/arch to a platform key, verifies `sha256`, and copies the declared binary. Unsupported platforms are skipped with a warning instead of failing all engine bootstrap.

3. **Sync wrapper skills globally.**  
   The source directory `skills/zotero-bridge-cli/` is copied to each managed agent home skill directory:
   - `.codex/skills/zotero-bridge-cli`
   - `.claude/skills/zotero-bridge-cli`
   - `.gemini/skills/zotero-bridge-cli`
   - `.qwen/skills/zotero-bridge-cli`
   - `.opencode/skills/zotero-bridge-cli`

4. **Sanitize the managed profile.**  
   The installed profile is derived from `profile.template.json` but does not persist fixed `endpoint` or `connectionMode`. It keeps `auth.tokenEnv=ZOTERO_BRIDGE_TOKEN` and records env names for endpoint and connection mode discovery.

5. **Expose only the profile path globally.**  
   `RuntimeProfile.build_subprocess_env()` sets `ZOTERO_BRIDGE_PROFILE` to the managed profile path. Request-specific `ZOTERO_BRIDGE_ENDPOINT`, `ZOTERO_BRIDGE_TOKEN`, and `ZOTERO_BRIDGE_CONNECTION_MODE` are injected through `runtime_options.env` and remain run-local.

## Risks / Trade-offs

- [Risk] Unsupported host platforms do not get a CLI binary. Mitigation: bootstrap logs a warning and still installs profile/skills where possible.
- [Risk] The upstream wrapper skill text may mention run-local fallbacks. Mitigation: the runner does not create such shims; managed PATH remains the effective path.
- [Risk] Profile schema support for env indirection is owned by the CLI. Mitigation: the CLI already supports env overrides; the managed profile avoids fixed secrets and documents required env names.
