# run-store-modularization Delta

## MODIFIED Requirements

### Requirement: Run store MUST persist logical run and physical workspace separately
Run store metadata MUST distinguish logical run identity from physical workspace identity.

#### Scenario: Request-bound run stores workspace layout
- **WHEN** a request is bound to a newly allocated run
- **THEN** the run record stores `run_id`, `workspace_id`, `workspace_dir`, `workspace_namespace`, `result_path`, and `input_manifest_path`
- **AND** downstream lifecycle stages use the persisted layout instead of deriving a path from `run_id`.

#### Scenario: Reuse request stores source workspace identity
- **WHEN** a request reuses a previous workspace
- **THEN** the new run stores the source request's `workspace_id` and `workspace_dir`
- **AND** stores its own namespace and actual runner-owned paths.

### Requirement: Cleanup MUST respect workspace references
Cleanup MUST delete a physical workspace only after no remaining run references it.

#### Scenario: Earlier reused run expires first
- **GIVEN** two run records reference the same `workspace_id` or `workspace_dir`
- **WHEN** cleanup deletes one run record
- **THEN** the physical workspace remains.

#### Scenario: Last workspace reference is deleted
- **WHEN** cleanup deletes the last run record referencing a workspace
- **THEN** the physical workspace may be removed.
