## 1. OpenSpec Artifacts

- [x] 1.1 Add the change proposal and output-json-repair delta spec.

## 2. Runtime Implementation

- [x] 2.1 Remove previous-candidate injection from schema repair prompt construction.
- [x] 2.2 Keep repair audit `repair_prompt_or_summary` aligned with the actual prompt sent to the adapter.

## 3. Validation

- [x] 3.1 Add or update focused convergence tests for the reduced repair prompt.
- [x] 3.2 Run targeted pytest for output convergence and agent output protocol contracts.
- [x] 3.3 Run OpenSpec status and validation for the change.
