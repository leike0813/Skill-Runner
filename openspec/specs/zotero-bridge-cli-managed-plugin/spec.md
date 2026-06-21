# zotero-bridge-cli-managed-plugin Specification

## Purpose
定义 Zotero Bridge CLI bundle 的受管插件安装、wrapper skill 全局同步与 managed profile 环境注入约束。
## Requirements
### Requirement: Zotero Bridge CLI bundle MUST be managed as a plugin submodule

The repository SHALL include the Zotero Bridge CLI bundle as a Git submodule at `plugins/zotero-bridge-cli-bundle` using `https://github.com/leike0813/Zotero-Skills.git` and branch `host-bridge/zotero-bridge-cli-bundle`.

#### Scenario: bundle files are available to bootstrap
- **WHEN** deployment/bootstrap code needs the Zotero Bridge bundle
- **THEN** it can read `manifest.json`, `bin/`, `skills/zotero-bridge-cli/`, and `profile.template.json` from `plugins/zotero-bridge-cli-bundle`

### Requirement: Bootstrap MUST install Zotero Bridge CLI into the managed PATH

The system SHALL install the current platform's `zotero-bridge` executable from the bundle manifest into the managed prefix bin directory after verifying the declared SHA256.

#### Scenario: POSIX platform install
- **WHEN** the manifest contains an entry for the current Linux platform
- **THEN** bootstrap copies the declared binary to `<SKILL_RUNNER_NPM_PREFIX>/bin/zotero-bridge`
- **AND** the installed file is executable
- **AND** agent subprocess PATH resolution can find `zotero-bridge`
- **AND** agent subprocess env includes `ZOTERO_BRIDGE_BIN=<SKILL_RUNNER_NPM_PREFIX>/bin/zotero-bridge`

#### Scenario: Windows platform install
- **WHEN** the manifest contains a `win32-x64` entry
- **THEN** bootstrap copies the declared executable to `<SKILL_RUNNER_NPM_PREFIX>/bin/zotero-bridge.exe`
- **AND** writes `<SKILL_RUNNER_NPM_PREFIX>/bin/zotero-bridge.cmd` as a command shim
- **AND** agent subprocess env includes `ZOTERO_BRIDGE_BIN=<SKILL_RUNNER_NPM_PREFIX>/bin/zotero-bridge.exe`

#### Scenario: sha256 mismatch fails fast
- **WHEN** the bundled binary content does not match the manifest SHA256
- **THEN** bootstrap fails the Zotero Bridge install step before writing the managed executable

### Requirement: Bootstrap MUST install the wrapper skill globally for managed agents

The system SHALL sync the bundled `skills/zotero-bridge-cli/` wrapper skill into each managed agent home global skill directory for Codex, Claude, Gemini, Qwen, and OpenCode.

#### Scenario: wrapper skill is available globally
- **WHEN** managed layout initialization completes
- **THEN** each supported agent global skill directory contains `zotero-bridge-cli/SKILL.md`
- **AND** the skill content comes from the bundle rather than from a run-local generated copy

### Requirement: Managed profile MUST avoid fixed endpoint and token values

The system SHALL install a managed Zotero Bridge profile under the agent cache and expose its path through `ZOTERO_BRIDGE_PROFILE`, while leaving request-specific connection values to `runtime_options.env`.

#### Scenario: profile contains only env indirection
- **WHEN** bootstrap writes the managed bridge profile
- **THEN** the profile does not contain a fixed bearer token
- **AND** does not persist a fixed request endpoint
- **AND** keeps `tokenEnv=ZOTERO_BRIDGE_TOKEN`
- **AND** records that endpoint and connection mode are supplied by `ZOTERO_BRIDGE_ENDPOINT` and `ZOTERO_BRIDGE_CONNECTION_MODE`

#### Scenario: request supplies connection env locally
- **WHEN** a Zotero skill run needs bridge access
- **THEN** the caller supplies `ZOTERO_BRIDGE_ENDPOINT`, `ZOTERO_BRIDGE_TOKEN`, and optionally `ZOTERO_BRIDGE_CONNECTION_MODE` through `runtime_options.env`
- **AND** those raw values follow the runtime env secret vault/redaction path
