## Why

The current converter implementation is tightly shaped around Skill-Runner run inputs (zip + run_dir artifacts), which makes direct interactive use by users less natural. We need a dual-mode upgrade so users can convert an existing local skill directory interactively, while preserving Skill-Runner execution compatibility.

## What Changes

- Upgrade `skill-converter-agent` to support both input modes:
  - direct source skill directory mode (interactive-first)
  - zip package mode (Skill-Runner compatible)
- Refactor conversion logic into a shared core module used by both modes, avoiding duplicated behavior.
- Keep output as a complete install-ready skill package, including `references/file_protocol.md`.
- Ensure `SKILL.md` patch output explicitly points to `references/file_protocol.md` for schema/runner generation guidance.
- Add tests covering both modes and parity checks to ensure both paths produce equivalent package contracts.

## Capabilities

### New Capabilities
- `skill-converter-dual-mode`: Provide dual invocation paths (directory + zip) for the converter skill with shared conversion semantics.

### Modified Capabilities
- None.

## Impact

- Converter code structure changes: split wrapper IO handling from conversion core.
- Skill assets and prompts updated to document/guide both usage modes.
- Additional tests for mode parity and interactive-friendly directory path handling.
- Documentation updates for how to use converter inside Skill-Runner and as a regular interactive agent skill.
