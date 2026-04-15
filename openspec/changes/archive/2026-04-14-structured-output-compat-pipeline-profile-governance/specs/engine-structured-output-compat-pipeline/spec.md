## ADDED Requirements

### Requirement: Runtime MUST expose a fixed structured-output compatibility pipeline

The runtime MUST provide a shared structured-output pipeline that is invoked from adapter execution paths rather than from engine-local ad hoc helpers.

#### Scenario: engine uses canonical passthrough
- **WHEN** an engine profile declares canonical passthrough / noop structured-output behavior
- **THEN** the pipeline MUST return the canonical machine schema artifact unchanged
- **AND** it MUST return the canonical prompt summary unchanged
- **AND** parsed payload canonicalization MUST be a no-op

#### Scenario: engine uses compatibility translation
- **WHEN** an engine profile declares compatibility translation
- **THEN** the pipeline MUST be allowed to materialize engine-compatible schema and prompt artifacts derived from the canonical schema
- **AND** command builders and prompt injection MUST consume those derived artifacts through the same pipeline entrypoint

### Requirement: Canonical target schema MUST remain the single source of truth

Canonical `.audit/contracts/target_output_schema.json` MUST remain the machine-truth contract even when an engine requires a translated transport artifact.

#### Scenario: compat artifact is derived from canonical schema
- **WHEN** runtime materializes an engine-specific compatibility artifact
- **THEN** the compatibility artifact MUST be derived from the canonical target output schema
- **AND** it MUST NOT replace or overwrite `.audit/contracts/target_output_schema.json`
- **AND** it MUST remain a transport/audit asset rather than the contract SSOT

#### Scenario: Codex compatibility artifact uses supported subset transport
- **WHEN** runtime materializes a Codex compatibility schema for an interactive run
- **THEN** the root schema MUST remain a JSON object
- **AND** the compatibility schema MUST avoid unsupported top-level union transport features
- **AND** inactive branch fields MAY be represented through explicit nullable placeholders rather than by changing the canonical branch semantics

### Requirement: Parsed structured payloads MUST canonicalize before orchestration consumption

If an engine emits a compatibility transport shape, the runtime MUST canonicalize that payload back to the canonical final/pending contract before orchestration consumes the result.

#### Scenario: compatibility final payload becomes canonical final payload
- **WHEN** a compatibility transport payload represents a final branch
- **THEN** runtime MUST return the canonical final payload shape
- **AND** it MUST strip inactive compatibility placeholders that are not part of the canonical contract

#### Scenario: compatibility pending payload becomes canonical pending payload
- **WHEN** a compatibility transport payload represents a pending branch
- **THEN** runtime MUST return the canonical pending payload shape with `__SKILL_DONE__ = false`, `message`, and `ui_hints`
- **AND** it MUST NOT leak transport-only null placeholders into orchestration-visible payloads
