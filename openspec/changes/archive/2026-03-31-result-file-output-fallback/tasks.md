## 1. OpenSpec Artifacts

- [x] 1.1 Add proposal, design, and delta specs for result-file output fallback

## 2. Runtime Fallback Implementation

- [x] 2.1 Add a run-lifecycle helper that scans the run workspace for the declared/default result JSON file
- [x] 2.2 Integrate result-file fallback into lifecycle normalization without overriding waiting_user or waiting_auth paths
- [x] 2.3 Extend the runner manifest schema to allow `entrypoint.result_json_filename`

## 3. Regression Coverage

- [x] 3.1 Add orchestrator tests for fallback success, invalid result files, multi-candidate selection, and waiting-state exclusions
- [x] 3.2 Add skill package validator coverage for `entrypoint.result_json_filename`
