# Runtime Stream Protocol (RASP/FCMP)

## 1. Overview

Skill Runner runtime observability now uses two protocol layers:

- `RASP/1.0` (Runtime Agent Stream Protocol): backend runtime events.
- `FCMP/1.0` (Frontend Conversation Message Protocol): frontend-facing conversation events translated from RASP.

RASP keeps full raw evidence. FCMP optimizes readability for UI.

## 2. RASP Envelope

Each `run_event` payload follows:

```json
{
  "protocol_version": "rasp/1.0",
  "run_id": "run-xxx",
  "seq": 12,
  "ts": "2026-02-22T12:34:56.000000",
  "source": {
    "engine": "codex",
    "parser": "codex_ndjson",
    "confidence": 0.95
  },
  "event": {
    "category": "agent",
    "type": "agent.message.final"
  },
  "data": {},
  "correlation": {},
  "attempt_number": 2,
  "raw_ref": {
    "attempt_number": 2,
    "stream": "stdout",
    "byte_from": 1024,
    "byte_to": 2048,
    "encoding": "utf-8"
  }
}
```

Categories: `lifecycle | agent | interaction | tool | artifact | diagnostic | raw`

## 3. FCMP Envelope

Each `chat_event` payload follows:

```json
{
  "protocol_version": "fcmp/1.0",
  "run_id": "run-xxx",
  "seq": 5,
  "ts": "2026-02-22T12:34:56.000000",
  "engine": "codex",
  "type": "assistant.message.final",
  "data": {},
  "meta": {
    "attempt": 2
  },
  "raw_ref": null
}
```

Common FCMP types:
- `conversation.started`
- `assistant.message.final`
- `user.input.required`
- `conversation.completed`
- `conversation.failed`
- `diagnostic.warning`
- `raw.stdout` / `raw.stderr`

## 4. Attempt & Cursor

- `attempt_number`:
  - `auto`: always `1`
  - `interactive`: initial request is `1`, each reply increments attempt.
- `cursor`: resume stream from next `run_event.seq`.

SSE API:
- `GET /v1/jobs/{request_id}/events?cursor=...&stdout_from=...&stderr_from=...`
- `GET /v1/management/runs/{request_id}/events?...`

History API:
- `GET /v1/jobs/{request_id}/events/history`
- `GET /v1/management/runs/{request_id}/events/history`

## 5. Raw Evidence Jump

Use `raw_ref` + logs range API:

- `GET /v1/jobs/{request_id}/logs/range?stream=stdout&byte_from=...&byte_to=...`
- `GET /v1/management/runs/{request_id}/logs/range?...`

## 6. Audit Artifacts

Attempt-scoped files are written into `data/runs/<run_id>/.audit/`:

- `meta.N.json`
- `stdin.N.log`
- `stdout.N.log`
- `stderr.N.log`
- `pty-output.N.log`
- `fs-before.N.json`
- `fs-after.N.json`
- `fs-diff.N.json`

Run-level aggregated files:

- `events.jsonl`
- `parser_diagnostics.jsonl`
- `fcmp_events.jsonl`
- `protocol_metrics.json`

`fd-trace.N.log` is not persisted.

## 7. Raw Suppression Rule

RASP preserves raw events completely. FCMP translator suppresses duplicate raw echo blocks when:

- raw line equals assistant message line
- same stream
- contiguous block length `>= 3`

Suppression emits:
- `diagnostic.warning` with code `RAW_DUPLICATE_SUPPRESSED`

## 8. Adapter Boundary and Command Parameter Sources

Engine-specific responsibilities are owned by `EngineAdapter`:

- start/resume command construction
- runtime stream parsing (`stdout`/`stderr`/`pty`) to normalized parser output
- session handle extraction semantics

`runtime_event_protocol` is engine-agnostic and only does:

- call adapter parser output
- assemble RASP events
- translate to FCMP events
- apply FCMP raw suppression and protocol metrics

Command parameters have two explicit sources:

- API execution path (`job_orchestrator -> adapter.run`):
  - inject default args from `server/assets/configs/engine_command_profiles.json`
  - merge rule: explicit invocation args override same-key profile defaults
- Harness path (`agent_harness`):
  - never inject profile defaults
  - only use user passthrough args plus minimal resume context (`session_id`, `message`)
  - `--translate` is view-only for harness output shaping and is never forwarded to engine CLI

## 9. Interactive Completion Gate (`__SKILL_DONE__`)

- Completion marker key is fixed: `__SKILL_DONE__` (uppercase).
- In `interactive` mode, completion is dual-track:
  - strong evidence: marker is found (payload or raw stream evidence);
  - soft evidence: marker is missing, but current turn output passes `output schema` validation.
- Optional ask_user hints should use non-JSON structured payload (recommended YAML block, e.g. `<ASK_USER_YAML> ... </ASK_USER_YAML>`).
- ask_user hints are enrichment-only and MUST NOT be used as lifecycle control predicates.
- If interactive turn finishes by soft evidence, backend records warning:
  - `INTERACTIVE_COMPLETED_WITHOUT_DONE_MARKER`
- If interactive turn has no completion evidence, backend enters `waiting_user` and waits for reply/resume.
- `runner.json.max_attempt` (optional, `>=1`) is interactive-only:
  - when `attempt_number >= max_attempt` and no completion evidence exists in that turn, run fails with:
  - `INTERACTIVE_MAX_ATTEMPT_EXCEEDED`
- In `auto` mode, completion is output-validation-first and does not require done marker.
- `__SKILL_DONE__` is a control marker only and MUST be removed before output schema validation.
- Output schema validation is performed only on business fields (marker excluded).
