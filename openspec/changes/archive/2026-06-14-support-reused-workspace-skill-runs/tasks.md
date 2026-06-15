## 1. OpenSpec and Docs

- [x] 1.1 Validate the OpenSpec change artifacts.
- [x] 1.2 Add workspace reuse and file namespace documentation under `docs/`.
- [x] 1.3 Update API and run artifact docs for `runtime_options.workspace` and actual result/input-manifest paths.

## 2. Persistence and Layout

- [x] 2.1 Add store schema fields and accessors for workspace identity, namespace, actual paths, and lineage tokens.
- [x] 2.2 Add workspace namespace allocation utilities using the safe segment rule.
- [x] 2.3 Add a run layout resolver that returns run-scoped paths for result, input manifest, state, dispatch, and audit files.

## 3. API and Orchestration

- [x] 3.1 Parse and validate `runtime_options.workspace` in job create/upload flows.
- [x] 3.2 Create normal runs with new workspace metadata and reuse runs with inherited workspace metadata.
- [x] 3.3 Route terminal result, request input manifest, state, dispatch, and attempt audit writes through the layout resolver.
- [x] 3.4 Update read paths, bundle generation, and diagnostics to prefer persisted actual paths with legacy fallback.

## 4. Cache

- [x] 4.1 Extend cache key construction with optional workspace lineage token.
- [x] 4.2 Persist and propagate workspace output tokens through normal completion and cache-hit binding.
- [x] 4.3 Ensure reused-workspace requests do not hit cache across different upstream workspace lineage.

## 5. Tests

- [x] 5.1 Add unit tests for safe segment and namespace allocation.
- [x] 5.2 Add cache key tests for workspace lineage tokens.
- [x] 5.3 Add API/integration tests for A -> B -> C workspace reuse and repeated skill namespaces.
- [x] 5.4 Add regression tests for actual result path reads, bundle inclusion, fallback exclusion, and legacy fixed-path reads.
- [x] 5.5 Run the targeted validation suite for the changed areas.
