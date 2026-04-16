# Design

## Canonical payload truth

For compat-schema engines such as Codex:

- CLI and live engine output may use compat payloads.
- Output convergence MUST canonicalize compat payloads back into runner canonical form before:
  - branch selection
  - target schema validation
  - repair round decisions
  - outcome projection

This preserves engine compatibility while keeping orchestrator logic anchored to the canonical runner contract.

## Bubble model source of truth

The current e2e bubble behavior is the reference implementation:

- in bubble mode, assistant intermediate messages and assistant process rows join the same draft bubble
- draft bubbles show the latest item when collapsed
- promoting a family to final removes the draft bubble generation and replaces it with an independent final bubble

Management UI and the shared model must converge to that behavior; e2e must not be regressed.

## Folded revisions

`assistant.message.superseded` continues to be an orchestration/FCMP/chat signal only.

`assistant_revision` is rendered as:

- an inline folded revision placeholder
- positioned where the superseded final originally appeared
- expandable to reveal the old final content

Winner-only visibility still applies:

- the latest winner remains the only primary-visible final in the family
- superseded finals stay visible only as folded revision history

## Repair generations

Repair-family rendering uses `(attempt, message_family_id, generation)`:

- generation starts at `0`
- each supersede increments the family generation
- new assistant intermediate/process rows after supersede start a fresh draft bubble generation

This prevents later assistant commentary from being folded into an earlier repaired final.
