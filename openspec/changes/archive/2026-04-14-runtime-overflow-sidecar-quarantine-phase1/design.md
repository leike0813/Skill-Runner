## Context

The current ingress sanitizer intentionally stops retaining oversized non-message NDJSON rows in
live memory after the first 4096 bytes. That protects parser hot paths, but unrecoverable rows are
currently replaced by a runtime diagnostic stub with no surviving copy of the original line. Recent
Claude failures showed that this makes postmortem analysis difficult because neither `stdout.log`
nor `io_chunks` contains the original oversized row anymore.

This change keeps the existing sanitized live-path semantics and adds a narrow sidecar preservation
path for overflow evidence only.

## Goals / Non-Goals

**Goals:**

- Preserve the original decoded text of overflowed non-message NDJSON lines in attempt-scoped audit
  sidecars.
- Keep oversized rows off the downstream parser hot path after overflow is detected.
- Keep the design simple: attempt-local index plus one raw file per overflow line.
- Reuse existing buffered audit writer patterns where possible.

**Non-Goals:**

- Replaying sidecar rows back into live parser, lifecycle, or session-handle recovery.
- Changing the `4096` byte threshold, overflow warning codes, or public event types.
- Introducing aggregated blob stores, compression, offset indexes, or automatic cleanup.

## Decisions

### 1. Preserve overflow evidence through sidecar quarantine, not by widening the hot path

Once a non-message NDJSON line overflows, the sanitizer will continue using its retained prefix for
repair/substitution decisions, but it will also stream the full decoded logical line into a
sidecar raw file. Downstream parser and audit hot paths continue consuming only the repaired row or
diagnostic stub.

Rationale:

- Preserves debuggability without reintroducing large-row pressure into parser/live publication.
- Keeps the live-path contract stable for existing consumers and tests.

Alternative considered:

- Feed the original oversized line back into parser through a lazy read path. Rejected for this
  phase because it couples preservation with behavior changes and adds more maintenance surface.

### 2. Use attempt-scoped index + per-overflow raw file

Each overflow line gets:

- one index row in `.audit/overflow_index.<attempt>.jsonl`
- one raw sidecar file under `.audit/overflow_lines/<attempt>/<overflow_id>.ndjson`

Rationale:

- Very easy to inspect manually.
- No offset arithmetic or partial-corruption recovery logic.
- Keeps write logic local and understandable.

Alternative considered:

- One aggregated blob file plus offsets. Rejected because it is harder to maintain and does not buy
  enough value for expected overflow frequency.

### 3. Stream overflow sidecars incrementally after the overflow threshold is crossed

The sanitizer enters a quarantine mode the first time a line crosses the overflow threshold:

- retained prefix remains bounded for repair
- the original decoded line is streamed to a dedicated raw sidecar writer
- only limited previews remain in memory (`head_preview` and `tail_preview`)

Rationale:

- Avoids rebuilding the whole logical line in memory merely to persist it later.
- Matches the requirement that oversized rows must not become a new parser/performance hazard.

### 4. Expose only minimal sidecar references in diagnostics

Overflow diagnostics may include `overflow_id` and `raw_relpath`, but no large body excerpts beyond
short previews. Full raw text remains only in the sidecar raw file.

Rationale:

- Makes debugging practical without bloating audit rows or protocol surfaces.
- Avoids accidentally reintroducing oversized content into normal runtime artifacts.

## Risks / Trade-offs

- [More audit files per run] -> Accept a small increase in file count because overflow rows should
  remain rare, and the simpler format is easier to inspect and maintain.
- [Decoded-text sidecar is not byte-exact raw subprocess output] -> Document that the sidecar stores
  the runtime ingress decoded text truth for the logical line, not a binary byte blob.
- [Extra async writers add cleanup work] -> Reuse the existing buffered audit writer pattern and
  drain the sidecar writers alongside stdout/stderr/io_chunks in adapter finalization.
