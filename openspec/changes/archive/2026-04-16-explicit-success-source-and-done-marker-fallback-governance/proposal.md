## Why

Run `a22b5caa-4760-468f-9dc0-20ab9452e480` exposed three gaps in the current output-completion governance:

1. Claude can successfully deliver structured output via `result.success.structured_output`, but that path is not formalized as a generic adapter capability.
2. The successful completion source is not explicit, so audit metadata can misleadingly report `DONE_MARKER_FOUND` even when business success came from accepted structured output.
3. Done-marker scanning still participates in ordinary completion reasoning instead of acting as a final compatibility fallback.

## What Changes

- Introduce a generic adapter capability for success-result structured output extraction.
- Add explicit success-source metadata through convergence, outcome, audit, and terminal/result payloads.
- Reuse the existing final message chain to surface accepted structured-output success through `RASP -> FCMP -> CHAT`.
- Demote done-marker handling to a true final fallback that only accepts explicit `__SKILL_DONE__ = true`.

## Impact

- No new public FCMP/RASP event types.
- Existing final events gain explicit structured-output origin metadata.
- Audit/result metadata becomes machine-readable for real success provenance.
- Done-marker behavior changes from normal success input to compatibility fallback only.
