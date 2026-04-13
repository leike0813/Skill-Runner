## 1. OpenSpec Change Artifacts

- [x] 1.1 Add proposal/design/tasks for the phase 4 pending-source cutover slice.
- [x] 1.2 Add delta specs for `interactive-run-lifecycle`, `interactive-engine-turn-protocol`, `interactive-decision-policy`, and `interactive-job-api`.

## 2. Runtime Implementation

- [x] 2.1 Make valid pending JSON the only rich-data source for canonical `PendingInteraction`.
- [x] 2.2 Replace legacy waiting enrichment with a default pending fallback builder.
- [x] 2.3 Remove or stop using YAML / runtime-stream / direct-payload waiting enrichment helpers from the orchestration path.
- [x] 2.4 Preserve interactive soft completion and existing final-branch failure behavior.

## 3. Validation

- [x] 3.1 Update unit tests for pending projection, legacy fallback, and interactive waiting semantics.
- [x] 3.2 Run targeted pytest for the affected runtime surface.
- [x] 3.3 Run mypy for touched orchestration, interaction lifecycle, and observability files.
