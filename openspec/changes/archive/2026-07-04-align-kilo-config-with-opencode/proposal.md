# Align Kilo Config With OpenCode

## Why

Kilo Code is forked from OpenCode and accepts the same core runtime config concepts, but Skill Runner currently ships minimal Kilo config assets and a placeholder schema. This leaves Kilo without the same managed provider timeout, permission, and UI shell hardening that OpenCode already has.

## What Changes

- Align Kilo bootstrap/default/enforced config assets with OpenCode-compatible config semantics.
- Keep Kilo-specific config identity: `https://app.kilo.ai/config.json`, `.kilo/kilo.jsonc`, and a Kilo default model.
- Add Kilo UI shell default/enforced config assets so inline TUI sessions are permission-denied like OpenCode.
- Expand the local Kilo config schema enough to validate OpenCode-compatible provider, permission, skills, tools, MCP, and Kilo-specific fields.

## Capabilities

### Modified Capabilities

- `engine-runtime-config-layering`
- `engine-command-profile-defaults`
- `ui-engine-management`

## Impact

- Kilo runtime config composition and UI shell bootstrap become more consistent with OpenCode.
- OpenCode behavior and config assets remain unchanged.
- No HTTP API, auth API, model registry API, or runtime event contract changes.
