## 1. OpenSpec Change Artifacts

- [x] 1.1 Add proposal/design/tasks for the phase 5 completion-gate tightening slice.
- [x] 1.2 Add delta specs for `interactive-run-lifecycle`, `interactive-decision-policy`, `interactive-engine-turn-protocol`, and `interactive-job-api`.

## 2. Runtime And SSOT Alignment

- [x] 2.1 Make the interactive lifecycle code explicitly evaluate `final -> pending -> soft completion -> waiting fallback`.
- [x] 2.2 Preserve soft completion as a compatibility path with the existing warning codes.
- [x] 2.3 Preserve default waiting fallback as the last compatibility path without restoring legacy enrichment.
- [x] 2.4 Update runtime contract descriptions and main docs to describe the conservative phase-5 model.

## 3. Validation

- [x] 3.1 Add or update tests for pending-branch waiting, soft-completion compatibility, and default waiting fallback ordering.
- [x] 3.2 Run targeted pytest for orchestrator/protocol/observability surfaces touched by the phase.
- [x] 3.3 Run mypy for the touched orchestration, audit, protocol, and observability files.
