## Output Format Contract

Your final output MUST strictly comply with the following rules:

1. The final output MUST be a single, valid JSON object — no markdown fences, no prose before or after, no extra text.
2. The JSON object MUST conform to the output schema defined below.
3. After emitting the final JSON output, you MUST immediately stop. Do NOT output any further text, explanation, or additional JSON.
4. Do NOT wrap the output JSON in markdown code fences (``` ```). Emit the raw JSON object directly.

Completion marker rules:
- The first key-value pair of the output JSON MUST be `"__SKILL_DONE__": true`. This is the completion signal that indicates the task is finished.
- The key must be exactly `__SKILL_DONE__` (uppercase, double underscores on both sides).
- The value MUST be the boolean `true`, not the string `"true"`.
- Do NOT emit `"__SKILL_DONE__": true` more than once. Only the first occurrence is valid; later ones are ignored.
