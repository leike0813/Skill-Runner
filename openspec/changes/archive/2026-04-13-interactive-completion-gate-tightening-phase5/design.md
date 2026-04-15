# Design

## Core model

Phase 5 keeps the phase-4 waiting-source cutover and phase-3B convergence model
intact. It only formalizes the completion gate order for interactive attempts.

For every interactive attempt, lifecycle normalization follows this order:

1. explicit final branch
2. explicit pending branch
3. soft completion compatibility path
4. default waiting fallback

## Explicit branches remain the formal contract

- final branch:
  - JSON object
  - `__SKILL_DONE__ = true`
  - business output passes schema and artifact validation
- pending branch:
  - JSON object
  - `__SKILL_DONE__ = false`
  - contains non-empty `message`
  - contains object-shaped `ui_hints`

These two branches remain the only formal interactive output contract.

## Soft completion remains compatibility-only

Soft completion is still allowed in phase 5, but it is explicitly secondary to
the final/pending branches.

Soft completion applies only when:

- no valid final branch resolved
- no valid pending branch resolved
- structured business output exists
- output schema is valid after removing any done marker field
- artifact validation still passes

When soft completion is used, runtime continues to emit the existing warning
surface:

- `INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER`
- `INTERACTIVE_SOFT_COMPLETION_SCHEMA_TOO_PERMISSIVE` when applicable

## Waiting fallback remains compatibility-only

If an interactive attempt does not resolve a valid final/pending branch and does
not satisfy soft completion, runtime may still enter `waiting_user`.

That fallback keeps the phase-4 rule:

- fallback waiting uses only the default pending payload
- no legacy YAML / runtime-stream / direct-payload enrichment is restored

Schema-invalid structured output continues to emit
`INTERACTIVE_OUTPUT_EXTRACTED_BUT_SCHEMA_INVALID`.

## Non-goals

- do not remove soft completion
- do not remove waiting fallback
- do not rename or retire existing warning/diagnostic codes
- do not change HTTP / FCMP / RASP external shapes
- do not perform the future hard-cut legacy removal in this phase
