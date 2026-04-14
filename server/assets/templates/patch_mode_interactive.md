## Execution Mode: INTERACTIVE

This skill is running in interactive mode. A human operator is available and may respond when needed.

Interaction policy:
1. Proceed autonomously whenever possible. Only pause for user input when the task genuinely requires it.
2. Ask at most one question per turn.
3. The runtime contract for interactive mode is JSON-only.

Interactive output contract:
1. Every turn MUST return exactly one JSON object.
2. If the task is complete, return the final branch with `__SKILL_DONE__ = true` and the required result fields.
3. If you need user input before the task can continue, return the pending branch described below.
{interactive_pending_contract_block}
4. Do not wrap the JSON in Markdown fences.
5. Do not output explanations before or after the JSON object.
