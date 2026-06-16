## Decisions

1. **Required schema set**
   `output` is the only required schema for upload/install and runtime execution preparation. `input` and `parameter` are optional.

2. **Fallback behavior**
   Schema resolution continues to use the existing `resolve_schema_asset` behavior: prefer `runner.json.schemas.<key>`, then fall back to `assets/<key>.schema.json`.

3. **Optional schema diagnostics**
   If `input` or `parameter` is explicitly declared but cannot be resolved and no fallback exists, validation logs a warning and treats that schema as absent. This warning is not exposed through a new API field.

4. **Validation when optional schema exists**
   If an optional schema resolves to a file, it is still validated against its service meta-schema. Invalid optional schema content remains a package validation error.

5. **Runtime preparation**
   Runtime preparation checks only that `output` schema resolves. Input and parameter validation continue to run only when those schemas resolve.

## Alternatives Considered

- Reject explicit bad optional schema declarations. This would catch authoring mistakes earlier but would not match the runtime's optional-schema behavior.
- Make all schemas optional. This conflicts with the structured output contract and output schema materialization.

## Risks

- A skill author may miss a typo in an optional schema declaration because it becomes a warning, not a hard failure. The validation log is retained to make that diagnosable without blocking schema-free skills.
