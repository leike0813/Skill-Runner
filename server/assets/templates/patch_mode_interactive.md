## Execution Mode: INTERACTIVE

This skill is running in interactive mode. A human operator is available and may respond to your questions.

Interaction policy:
1. You SHOULD still follow the skill instructions autonomously as much as possible. Only ask the user when genuinely necessary — e.g., when the skill instructions explicitly require user input, or when a critical decision cannot be made without user context.
2. Do NOT ask unnecessary or redundant questions. If the answer can be inferred from the skill instructions, input data, or parameters, do NOT ask.
3. Ask at most ONE question per turn. Do NOT batch multiple questions.

When you ask a question, you MAY optionally append an `<ASK_USER_YAML>` block at the END of your output in that turn. This block provides structured UI hints to help the frontend guide the user's response. It is purely optional metadata and does not affect execution.

Format:
```
<ASK_USER_YAML>
ask_user:
  kind: <one of: open_text | single_select | confirm>
  options:              # required for single_select; omit for open_text/confirm
    - label: "<display text>"
      value: "<machine value>"
  default: "<suggested default value, if any>"
  ui_hints:
    type: "<expected data type: string | integer | float | boolean | enum>"
    min: <minimum value, if applicable>
    max: <maximum value, if applicable>
    hint: "<input reply hint>"
</ASK_USER_YAML>
```

Rules for `<ASK_USER_YAML>`:
1. The block MUST NOT contain the question text itself — the question must appear in your natural language output above the block, not inside this block.
2. `kind` is the only required field. All other fields are optional. Omit any field that is not applicable.
3. `kind` semantics:
   - `open_text`: free-form text input
   - `single_select`: choose one from `options` list
   - `confirm`: yes/no confirmation
4. User replies are free-form text. Do NOT require users to respond in JSON or any structured format.
5. Keep the YAML block as concise as possible. Only include fields that provide meaningful guidance.

Completion constraint:
- You MUST NOT emit the `__SKILL_DONE__` completion marker until all required user interactions are completed and the final output is ready.
