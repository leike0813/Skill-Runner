# Add Runtime Preamble Prompt

## Why

Clients sometimes need to provide per-run context that should appear at the beginning of an agent session without editing a skill package. Today the only prompt override path is internal and replaces the whole prompt for repair/reply flows, so exposing it would bypass server-owned skill, engine, safety, and output-schema instructions.

## What Changes

- Add public `runtime_options.preamble_prompt` as a constrained run-scoped preamble.
- Inject the preamble only into the first attempt's initial prompt.
- Store only a redacted descriptor in request records and audit snapshots, while keeping the raw preamble in request-scoped secret storage for execution.
- Include the preamble content hash in cache keys.
- Keep internal `__prompt_override` semantics unchanged.

## Capabilities

### Modified Capabilities

- `runtime-env-options`
- `engine-adapter-runtime-contract`
- `run-audit-contract`
- `run-state-contract`
- `skill-patch-modular-injection`

## Impact

- Adds a new public runtime option accepted by `/jobs` requests.
- Changes cache key version because preamble content affects engine output.
- Does not change external run, auth, model, FCMP, or RASP response shapes.
