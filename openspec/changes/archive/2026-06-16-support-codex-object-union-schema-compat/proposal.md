## Why

Some valid skill output contracts need a top-level object with `oneOf` or `anyOf` branches, typically discriminated by a `kind` field. Skill Runner should keep requiring a top-level object schema, while Codex still needs a transport schema that avoids unsupported top-level union constructs.

## What Changes

- Keep the package-level output schema contract strict: the schema root must declare `type: object`.
- Support `type: object` plus `oneOf`/`anyOf` as a valid business output contract.
- Preserve canonical schema truth while deriving a Codex-compatible flat object schema for transport.
- Canonicalize Codex flat payloads back to the selected original branch using a stable `const` discriminator.
- Inject `__SKILL_DONE__` into object-union branches during final wrapper materialization so `additionalProperties: false` branches remain valid.

## Capabilities

### New Capabilities

### Modified Capabilities

- `engine-structured-output-compat-pipeline`: Codex compatibility translation and payload canonicalization support object-union output schemas.
- `run-output-schema-materialization`: final wrapper materialization preserves object-union semantics while adding the completion marker to every branch.
- `skill-package-validation-schema`: object-union output schemas are valid only when the root still declares `type: object`; pure top-level unions remain invalid.

## Impact

- Affected code: structured output pipeline, output schema materialization, schema validation tests.
- Affected engines: Codex compatibility transport only; canonical schema validation and other engines remain unchanged.
- No public API or dependency changes.
