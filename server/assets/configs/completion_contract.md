## Runtime Completion Contract (Injected by Skill Runner)

You MUST strictly follow the task scope defined by this skill package and runtime input.

Completion marker rules:
1. The only allowed marker key is `__SKILL_DONE__` (uppercase only).
2. If final output is a JSON object, include `"__SKILL_DONE__": true` inside that final JSON.
3. If final output is not a JSON object, emit exactly one extra JSON object line:
   `{"__SKILL_DONE__": true}`
4. Do not wrap the done marker in markdown code fences.
5. After the first done marker appears, stop output immediately and do not emit extra content.
6. If multiple done markers appear in one turn, only the first one is valid and later ones are ignored.

Execution-mode guardrails:
- In `interactive` mode, do not emit done marker before all required user interactions are completed.
- In `auto` mode, never ask user for clarification or decisions.
