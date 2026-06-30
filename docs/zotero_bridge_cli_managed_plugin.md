# Zotero Bridge CLI Managed Plugin

Skill Runner manages the Zotero Bridge CLI bundle as a managed plugin. The
runtime resolves the bundle from the managed cache first, then falls back to the
built-in bundle shipped with the service:

```text
<SKILL_RUNNER_AGENT_CACHE_DIR>/plugin-bundles/zotero-bridge-cli-bundle
plugins/zotero-bridge-cli-bundle
```

The bundle provides `manifest.json`, platform binaries under `bin/`, the global wrapper skill at `skills/zotero-bridge-cli/`, and `assets/profile.template.json`.

## Automatic Bundle Updates

Skill Runner checks the configured Git branch in the background after service
startup and stores validated bundle versions under:

```text
<SKILL_RUNNER_AGENT_CACHE_DIR>/plugin-bundles/zotero-bridge-cli-bundle/versions/<commit>
```

The project-level defaults are defined in `server/config.py`:

```text
repository=https://github.com/leike0813/zotero-agents
branch=host-bridge/zotero-bridge-cli-bundle
interval_sec=86400
startup_delay_sec=30
timeout_sec=30
```

The updater validates the bundle manifest, wrapper skill, profile template, and
current platform binary SHA256 before activating a version. Update failures do
not block service startup or agent runs. The runtime keeps using the previous
active managed bundle, or the built-in fallback when no managed bundle is active.

Update status is recorded at:

```text
<SKILL_RUNNER_AGENT_CACHE_DIR>/plugin-bundles/zotero-bridge-cli-bundle/state.json
```

`scripts/skill-runnerctl doctor --json`, `preflight --json`, and `status --json`
include this state as read-only diagnostics.

## Bootstrap Behavior

During agent layout bootstrap, Skill Runner reads the resolved bundle manifest and installs the current platform binary into the managed prefix:

```text
<SKILL_RUNNER_NPM_PREFIX>/bin/zotero-bridge
```

On Windows, bootstrap installs:

```text
<SKILL_RUNNER_NPM_PREFIX>/bin/zotero-bridge.exe
<SKILL_RUNNER_NPM_PREFIX>/bin/zotero-bridge.cmd
```

The binary hash must match the manifest `sha256`. A mismatch fails the install step before the managed executable is written.

Local deployment uses the prefix prepared by `scripts/skill-runnerctl`. Docker deployment uses `/opt/cache/skill-runner/npm/bin`, which is already on PATH in the image.

Agent subprocess environments include the absolute managed executable path:

```text
ZOTERO_BRIDGE_BIN=<SKILL_RUNNER_NPM_PREFIX>/bin/zotero-bridge
```

On Windows, the value points at `<SKILL_RUNNER_NPM_PREFIX>/bin/zotero-bridge.exe`.

## Global Wrapper Skill

Bootstrap syncs the bundled wrapper skill into managed agent homes:

```text
<AGENT_HOME>/.codex/skills/zotero-bridge-cli
<AGENT_HOME>/.claude/skills/zotero-bridge-cli
<AGENT_HOME>/.qwen/skills/zotero-bridge-cli
<AGENT_HOME>/.opencode/skills/zotero-bridge-cli
```

Agents should invoke the CLI by command name:

```bash
zotero-bridge
```

Skill Runner does not create a run-local CLI shim or run-local copy of this wrapper skill.

## Managed Profile And Request Env

Bootstrap installs a managed bridge profile under the agent cache:

```text
<SKILL_RUNNER_AGENT_CACHE_DIR>/zotero-bridge/bridge-profile.json
```

Agent subprocess environments include:

```text
ZOTERO_BRIDGE_PROFILE=<managed profile path>
```

The managed profile does not store a fixed endpoint or bearer token. Request callers provide connection values through `runtime_options.env`:

```json
{
  "runtime_options": {
    "env": {
      "ZOTERO_BRIDGE_ENDPOINT": "https://bridge.example/bridge/v1",
      "ZOTERO_BRIDGE_TOKEN": "<request-scoped-token>",
      "ZOTERO_BRIDGE_CONNECTION_MODE": "remote"
    }
  }
}
```

Raw token values follow the runtime env secret vault/redaction path and must not be printed, saved, echoed, or copied into engine profiles, audit files, bundles, or logs.

## Backend-Observed Plugin Address

When a local plugin needs the agent to call back into the plugin host, it can ask Skill Runner which client address the backend observes:

```http
GET /v1/runtime/network/client-address
```

Example response:

```json
{
  "client_ip": "203.0.113.10"
}
```

The plugin can combine that address with its pinned bridge port and pass the resulting endpoint through `runtime_options.env`:

```json
{
  "runtime_options": {
    "env": {
      "ZOTERO_BRIDGE_ENDPOINT": "http://203.0.113.10:<pinned-port>/bridge/v1",
      "ZOTERO_BRIDGE_TOKEN": "<request-scoped-token>",
      "ZOTERO_BRIDGE_CONNECTION_MODE": "remote"
    }
  }
}
```

The endpoint reflects the backend-observed request peer address and does not interpret untrusted forwarding headers.
