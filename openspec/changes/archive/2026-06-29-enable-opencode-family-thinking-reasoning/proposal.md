# Enable OpenCode-family Thinking Reasoning

## Why

OpenCode-family engines can emit explicit reasoning rows in JSONL stdout, but the shared parser currently only handles text, tool use, and turn markers. Kilo also requires `--thinking` to emit reasoning rows, and OpenCode command defaults likewise do not request thinking output.

Without a shared contract, OpenCode and Kilo can silently omit reasoning process events even though the runtime protocol already supports `agent.reasoning` and `assistant.reasoning`.

## What Changes

- Enable `--thinking` in OpenCode and Kilo command profile defaults.
- Parse OpenCode-family `type=reasoning` rows in the shared parser core.
- Emit reasoning as process events that project into RASP and FCMP reasoning events.
- Keep reasoning token counts as turn completion usage metadata.

## Impact

- OpenCode and Kilo runs expose reasoning rows when the CLI/model emits them.
- OpenCode-family parser behavior is governed from one shared implementation.
- Final assistant response parsing remains unchanged; reasoning text is not mixed into final output.
