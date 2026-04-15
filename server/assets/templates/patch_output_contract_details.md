### Output Contract Details

{schema_artifact_block}#### Final Branch Contract

- Return the final branch when the requested task is fully concluded.
- Set `__SKILL_DONE__` to `true`.
- Include the required result fields defined below.
- Do not emit pending-only interaction fields unless engine-specific compatibility rules below explicitly require placeholder values.

#### Field-Level Schema Details

The final branch fields must conform to the following schema:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
{field_rows}{additional_properties_block}

#### Final Branch Example

```json
{example_json}
```

{pending_branch_block}{compatibility_note_block}
