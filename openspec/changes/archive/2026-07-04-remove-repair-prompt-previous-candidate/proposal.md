# Remove Repair Prompt Previous Candidate

## Why

Schema repair reruns resume the same engine session, so the invalid assistant output is already present near the end of session context. Repeating `Previous candidate` inside the repair prompt adds token cost without adding information, and it also duplicates potentially large or noisy invalid output in repair audit summaries.

## What Changes

- Remove the `Previous candidate` section from schema repair prompts.
- Keep validation errors, execution-mode branch instructions, no-explanation/no-fence instructions, and target output contract details.
- Keep repair reruns handle-gated and session-reusing.
- Keep `.audit/output_repair.<attempt>.jsonl` and `repair_prompt_or_summary`, but store the actual reduced prompt.

## Capabilities

### Modified Capabilities

- `output-json-repair`

## Impact

- Runtime prompt construction changes only inside `run_output_convergence_service`.
- No HTTP API, FCMP/RASP event, runtime schema, event type, or audit filename changes.
- Targeted convergence tests lock the reduced prompt behavior.
