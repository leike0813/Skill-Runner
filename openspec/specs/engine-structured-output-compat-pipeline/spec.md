# engine-structured-output-compat-pipeline Specification

## Purpose
TBD - created by archiving change output-contract-prompt-injection-ssot-governance-2026-04-15. Update Purpose after archive.
## Requirements
### Requirement: Structured output governance MUST define canonical truth and engine-effective transport separately
系统 MUST 将 canonical target output schema 与 engine transport compat schema 分离治理。

#### Scenario: canonical schema remains SSOT
- **WHEN** runtime materializes target output schema
- **THEN** canonical `.audit/contracts/target_output_schema.json` MUST remain the only machine truth
- **AND** compat schema MUST 被视为 engine transport artifact，而不是 canonical truth

### Requirement: Structured output pipeline MUST render prompt contract text from the engine-effective schema
系统 MUST 从 engine-effective schema 渲染最终 prompt contract 文本，确保 CLI schema 注入与 agent-visible contract 不漂移。

#### Scenario: render prompt contract for compat engine
- **WHEN** 某引擎启用 compat translate
- **THEN** prompt contract text MUST 从 compat schema 派生
- **AND** canonical schema 的差异 MUST 由 pipeline 负责吸收，而不是由下游模板自行解释

#### Scenario: render prompt contract for canonical engine
- **WHEN** 某引擎未启用 compat translate
- **THEN** prompt contract text MUST 直接从 canonical schema 派生

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

### Requirement: Codex compatibility translation MUST support discriminated object-union final schemas

When the canonical final schema is an object schema containing `oneOf` or `anyOf` object branches, the Codex compatibility pipeline MUST derive a flat object transport schema from that union without changing the canonical schema.

#### Scenario: Object-union final schema becomes flat Codex transport
- **GIVEN** the canonical final schema has `type=object`
- **AND** it contains `oneOf` or `anyOf` object branches
- **AND** the branches share a discriminator field with distinct `const` values
- **WHEN** Codex compatibility artifacts are materialized
- **THEN** the effective Codex schema is a single object schema
- **AND** it does not contain top-level `oneOf`, `anyOf`, or `allOf`
- **AND** it contains the merged branch fields
- **AND** branch-inactive fields are nullable placeholders
- **AND** the discriminator field exposes the allowed branch values

#### Scenario: Interactive state union remains distinct from business object union
- **GIVEN** the canonical schema contains an outer final/pending union using `__SKILL_DONE__`
- **AND** the final branch contains a business object union
- **WHEN** Codex compatibility artifacts are materialized
- **THEN** the pipeline treats the outer union as the execution state union
- **AND** it treats the final branch union as the business output union

### Requirement: Codex compatibility payloads MUST canonicalize back to the selected object-union branch

Codex flat transport payloads for object-union final schemas MUST be projected back to the branch selected by the discriminator before orchestration consumes them.

#### Scenario: Final payload selects a business branch
- **GIVEN** a Codex flat final payload contains a discriminator value
- **AND** that value matches one canonical object-union branch
- **WHEN** the payload is canonicalized
- **THEN** runtime returns the canonical final payload for that branch
- **AND** it strips fields that only belong to inactive branches
- **AND** it preserves `__SKILL_DONE__=true`

#### Scenario: Ambiguous object union is not guessed
- **GIVEN** an object-union schema has no stable distinct `const` discriminator
- **WHEN** Codex payload canonicalization cannot select a branch
- **THEN** runtime MUST NOT silently guess a branch
- **AND** downstream canonical validation remains responsible for reporting the contract violation

