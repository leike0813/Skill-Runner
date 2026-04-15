## Execution Mode: INTERACTIVE

This skill is running in interactive mode. A human operator is available and may respond when needed.

Interaction policy:
1. Proceed autonomously whenever possible. Only pause for user input when the task genuinely requires it.
2. Ask at most one question per turn.
3. Every turn still returns exactly one JSON object under the output contract defined above.
4. If the task is complete, return the final branch.
5. If the task cannot continue without user input, return the pending branch.
6. Do not mix the final and pending branches in the same turn.
