# Design

## Contract Hygiene

`session_fcmp_invariants.yaml` and `runtime_event_ordering_contract.yaml` remain the primary machine-readable SSOT for runtime behavior. This change repairs their structure and clarifies precedence that is already present in implementation:

- `waiting_auth` may coexist with semantic `agent.turn_failed` evidence.
- `agent.turn_failed` remains evidence-only when canonical state is `waiting_auth`.
- waiting/non-terminal states must never emit terminal result projection.

The goal is not new behavior; it is making the contract itself loadable, unique-id clean, and implementation-aligned.

## Parser Capability Matrix

A new invariant document records stable parser capabilities per engine:

- semantic turn markers
- generic error governance
- auth signal snapshot
- structured payload extraction
- process event extraction
- run handle extraction
- parser confidence reporting

This contract is descriptive and machine-readable. It is used to:

- distinguish common protocol expectations from engine-specific expectations
- prevent future tests from inferring parser capability from implementation details
- support later golden-fixture design without committing to a fixture schema in this change

## Diagnostic Warning Taxonomy

`diagnostic.warning` continues to be the single warning event type, but the payload contract becomes more explicit:

- `severity`
- `pattern_kind`
- `source_type`
- `authoritative`

Current rule:

- warnings are non-terminal and non-state-driving
- parser/engine/schema compatibility warnings emit `authoritative=false`
- raw evidence is still retained independently

This change only stabilizes the vocabulary and normalizes currently loose parser/unknown-engine warnings into the same taxonomy.

## Legacy Completion-State Compatibility

`lifecycle.completion.state` keeps read compatibility for historical aliases such as:

- `awaiting_user_input`
- `awaiting_auth`

But new writes must emit canonical names:

- `waiting_user`
- `waiting_auth`

Protocol normalization continues to accept both, but new audit materialization must stop producing the old aliases.
