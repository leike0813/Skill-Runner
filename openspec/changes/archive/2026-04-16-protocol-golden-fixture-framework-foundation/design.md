# Design: Protocol Golden Fixture Framework Foundation

## Decision

The first golden-fixture change only builds the framework skeleton. It does not yet import a broad real-run corpus.

The golden fixture framework is anchored to existing protocol SSOT:

- `session_fcmp_invariants.yaml`
- `runtime_event_ordering_contract.yaml`
- `runtime_contract.schema.json`
- `runtime_parser_capabilities.yaml`

## Fixture Layers

The framework supports exactly three layers:

1. `parser_only`
2. `protocol_core`
3. `outcome_core`

This prevents fixture sprawl across UI and end-to-end artifacts before the protocol core is stable.

## Contract Shape

Each fixture declares:

- identity: `fixture_id`, `layer`, `engine`
- source provenance: `source`, optional `source_run_id`
- capability gating: `capability_requirements`
- inputs
- expected semantic outputs
- normalization directives

The contract is intentionally shallow. It validates top-level structure and leaves inner semantic fragments flexible so that assertions remain semantic rather than byte-for-byte snapshots.

## Capability Gating

Capability gating reads directly from `runtime_parser_capabilities.yaml`. A fixture may require one or more capability paths such as:

- `semantic_turn_markers.failed`
- `generic_error_governance`

If an engine does not advertise all required capabilities, the fixture loader marks it unsupported instead of treating the mismatch as a protocol failure.

## Normalization

The normalizer strips unstable protocol fields such as:

- timestamps
- global/local sequence numbers
- raw byte offsets
- run/request identifiers
- volatile correlation metadata

This allows golden assertions to remain stable while still checking canonical protocol semantics.

## Raw Evidence vs Golden Corpus

`tests/fixtures/auth_detection_samples/` remains a raw evidence corpus.

`tests/fixtures/protocol_golden/` becomes a normalized golden corpus.

The framework includes a bridge helper so later changes can derive golden fixtures from raw evidence without collapsing both corpora into the same directory or contract.
