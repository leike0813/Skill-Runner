## Why

Zotero-facing skills need a stable way for agents to talk to the host Zotero library through the Zotero Bridge CLI. Today the runner has no managed deployment path for that CLI or its wrapper skill, so each run would need ad hoc local materialization or manual host setup. That is brittle for cascaded skill execution and does not fit the request-scoped `runtime_options.env` secret path used for endpoint and bearer token values.

## What Changes

- Add the Zotero Bridge CLI bundle as a repository submodule at `plugins/zotero-bridge-cli-bundle`.
- During managed agent bootstrap/layout initialization, install the platform-specific `zotero-bridge` executable into the managed prefix bin directory.
- Verify the bundled binary SHA256 before installing it.
- Sync the bundled `zotero-bridge-cli` wrapper skill into each managed agent home global skill directory.
- Install a managed well-known bridge profile under the agent cache and expose it through `ZOTERO_BRIDGE_PROFILE`.
- Keep endpoint, token, and connection mode out of profile files; callers provide them through `runtime_options.env`.
- Document local and Docker deployment behavior.

## Capabilities

### New Capabilities
- `zotero-bridge-cli-managed-plugin`: Defines the submodule bundle, managed CLI install, wrapper skill sync, and managed profile behavior.

### Modified Capabilities
- `runtime-environment-parity`: Extends managed prefix semantics to non-engine plugin CLIs that must be available to agent subprocesses through PATH.
- `engine-adapter-runtime-contract`: Requires managed profile environment defaults to be visible to agent subprocesses while request-specific connection secrets remain run-local.
- `local-deploy-bootstrap`: Clarifies local and Docker bootstrap behavior for the managed Zotero Bridge plugin.

## Impact

- Repository: adds a Git submodule under `plugins/`.
- Bootstrap: `AgentCliManager.ensure_layout()` also ensures Zotero Bridge CLI/profile/global skill state.
- Runtime env: agent subprocesses receive `ZOTERO_BRIDGE_PROFILE`; endpoint/token/mode are still supplied by request-scoped `runtime_options.env`.
- Docker: image build includes the `plugins/` directory so container bootstrap can install the CLI.
- Tests/docs: add focused unit coverage and integration documentation.
