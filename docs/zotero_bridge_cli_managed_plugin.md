# Zotero Bridge CLI Managed Plugin

Skill Runner includes the Zotero Bridge CLI bundle as a managed plugin submodule:

```text
plugins/zotero-bridge-cli-bundle
```

The bundle provides `manifest.json`, platform binaries under `bin/`, the global wrapper skill at `skills/zotero-bridge-cli/`, and `profile.template.json`.

## Bootstrap Behavior

During agent layout bootstrap, Skill Runner reads the bundle manifest and installs the current platform binary into the managed prefix:

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

## Global Wrapper Skill

Bootstrap syncs the bundled wrapper skill into managed agent homes:

```text
<AGENT_HOME>/.codex/skills/zotero-bridge-cli
<AGENT_HOME>/.claude/skills/zotero-bridge-cli
<AGENT_HOME>/.gemini/skills/zotero-bridge-cli
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
