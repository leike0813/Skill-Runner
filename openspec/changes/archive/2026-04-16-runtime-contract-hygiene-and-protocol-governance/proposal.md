# runtime-contract-hygiene-and-protocol-governance-2026-04-16

## Why

Runtime protocol semantics are now mostly stable, but the machine-readable contracts still carry drift:

- `session_fcmp_invariants.yaml` currently contains malformed list structure and duplicate rule ids.
- `runtime_contract.schema.json` still accepts legacy completion-state aliases on the canonical write path.
- parser capability differences are real, but they are only implicit in implementation and tests.
- `diagnostic.warning` now carries more governance meaning than a bare code, yet its taxonomy is still partly ad hoc.

These issues make the protocol surface harder to treat as the single source of truth for upcoming golden fixtures and mock/integration infrastructure.

## What Changes

- Repair runtime SSOT hygiene in invariants/ordering/schema so the contracts themselves are trustworthy.
- Add a machine-readable parser capability matrix for current engines.
- Stabilize `diagnostic.warning` taxonomy fields for protocol and parser governance.
- Stop new canonical audit/protocol writes from emitting legacy completion-state aliases while keeping read compatibility.

## Impact

- No new FCMP/RASP public event types.
- No HTTP API changes.
- Small runtime behavior tightening only where protocol hygiene requires it.
- Better contract quality for future golden-fixture work.
