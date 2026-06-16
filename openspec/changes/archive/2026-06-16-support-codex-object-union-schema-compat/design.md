## Overview

The canonical target output schema remains the single source of truth. When a skill declares `type: object` with `oneOf` or `anyOf`, runtime materialization keeps that union in the canonical schema and injects `__SKILL_DONE__` into each object branch. Codex then receives a derived flat object schema that merges branch fields and uses a discriminator to recover the original branch.

## Decisions

- Pure top-level unions without `type: object` remain invalid package output schemas.
- Object-union support is limited to object branches with a stable discriminator field whose branch schemas use distinct `const` values.
- `__SKILL_DONE__` is ignored when detecting business discriminators.
- Codex transport keeps all merged fields required because that is the existing compat convention; branch-inactive fields are nullable placeholders.
- If no stable discriminator exists, the pipeline does not guess a branch. The payload will remain subject to normal canonical validation and fail diagnostically if it cannot satisfy the canonical schema.

## Implementation Notes

- Materialization should add `__SKILL_DONE__` at the wrapper root and inside each object branch under `oneOf` or `anyOf`.
- Compat translation should distinguish outer final/pending unions from business unions. Only a union containing both `__SKILL_DONE__: true` and `__SKILL_DONE__: false` branches is treated as the interactive state union.
- Object-union translation should merge root properties with selected branch properties, convert the discriminator to an enum, and make branch-specific properties nullable.
- Canonicalization should first resolve final/pending by `__SKILL_DONE__`; for final object-union schemas it should select the branch by discriminator and project only fields allowed by the root plus selected branch.

## Risks

- Ambiguous unions without discriminators cannot be flattened safely. This change intentionally avoids silent branch guessing.
- Branches using `additionalProperties: false` require completion marker injection into each branch to avoid rejecting otherwise valid final payloads.
