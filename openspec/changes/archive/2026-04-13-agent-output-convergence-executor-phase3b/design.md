# Design

## Core model

Phase 3B implements the phase-3A governance model with one orchestrator-owned
`output convergence executor`.

- `attempt_number` remains the user-visible outer unit.
- `internal_round_index` is the attempt-internal repair rerun counter.
- repair reruns are only legal when a session handle already exists.
- deterministic parse repair is an in-loop parse-normalization step, not a separate
  fallback classifier.

## Repair loop

For each attempt:

1. Collect the initial raw output and any structured candidate.
2. Run deterministic parse repair for the current round.
3. Validate the repaired candidate against the attempt target contract.
4. If valid, resolve to:
   - `final` for auto or interactive final branch
   - `pending` for interactive pending branch
5. Otherwise, if a session handle exists and rounds remain, rerun via adapter resume with
   `__repair_round_index >= 1`.
6. If no session handle exists, or rounds are exhausted, mark repair `skipped` or
   `exhausted` and fall back to legacy lifecycle handling without another deterministic
   parse pass.

## Attempt target contract

- `auto` attempts target the final wrapper schema.
- `interactive` attempts target the union schema:
  - final branch: `__SKILL_DONE__ = true`
  - pending branch: `__SKILL_DONE__ = false + message + ui_hints`

Interactive pending branches become the formal waiting source in phase 3B.

## Legacy ask-user removal

`<ASK_USER_YAML>` is no longer a formal runtime output protocol in phase 3B.

- interactive prompts instruct the agent to emit pending/final JSON only
- legacy ask-user blocks may still appear in model output as invalid legacy samples
- they do not directly trigger `waiting_user`
- they are treated as repair inputs and, if unrecoverable, fall through to legacy
  non-JSON fallback handling

## Audit and events

- Precreate `.audit/output_repair.<attempt>.jsonl` in attempt audit setup.
- Emit repair orchestrator events:
  - `diagnostic.output_repair.started`
  - `diagnostic.output_repair.round.started`
  - `diagnostic.output_repair.round.completed`
  - `diagnostic.output_repair.converged`
  - `diagnostic.output_repair.exhausted`
  - `diagnostic.output_repair.skipped`
- Record, per round:
  - whether raw candidate existed
  - whether deterministic repair ran and succeeded
  - whether schema validation succeeded
  - which branch was resolved
  - which fallback path was selected when applicable

## Integration constraints

- `base_execution_adapter` must suppress first-attempt prompt/argv audit writes and first
  attempt global prefix when `__repair_round_index >= 1`.
- repair reruns must use resume semantics with an existing session handle.
- repair events remain orchestrator-only and must not translate into FCMP.
