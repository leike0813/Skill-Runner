## Summary

Unify skill schema requirement rules across package validation, temporary skill uploads, and runtime preparation:

- `output` schema is required.
- `input` and `parameter` schemas are optional.
- Existing canonical fallback resolution remains unchanged.
- Missing optional schema declarations do not block validation; explicit bad optional declarations without fallback are diagnostic warnings.

## Motivation

The current implementation applies different schema requirements in different layers:

- Runtime input/parameter validation is already conditional on schema presence.
- Runtime preparation currently blocks execution unless all three schemas exist.
- Package upload/install validation requires all three schemas.
- Built-in skill registry does not enforce any schema files.

This creates inconsistent behavior for otherwise valid skills that have structured outputs but no typed inputs or parameters.

## Impact

- Skill packages without `input.schema.json` or `parameter.schema.json` can be installed or used as temporary skills.
- Skills without `output.schema.json` continue to fail package validation and runtime preparation.
- Existing packages with all three schema files keep the same behavior.
- Invalid optional schema files still fail validation when present.
