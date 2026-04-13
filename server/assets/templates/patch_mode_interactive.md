## Execution Mode: INTERACTIVE

This skill is running in interactive mode. A human operator is available and may respond when needed.

Interaction policy:
1. Proceed autonomously whenever possible. Only pause for user input when the task genuinely requires it.
2. Ask at most one question per turn.
3. The runtime contract for interactive mode is JSON-only. Legacy `<ASK_USER_YAML>` is not a valid output protocol.

Interactive output contract:
1. Every turn MUST return exactly one JSON object.
2. If the task is complete, return the final branch with `__SKILL_DONE__ = true` and the required result fields.
3. If you need user input before the task can continue, return the pending branch:
   - `__SKILL_DONE__ = false`
   - `message`: the user-facing question or instruction
   - `ui_hints`: an object with optional UI hints such as `kind`, `prompt`, `hint`, `options`, and `files`
4. Do not wrap the JSON in Markdown fences.
5. Do not output explanations before or after the JSON object.
6. Do not output `<ASK_USER_YAML>`.
