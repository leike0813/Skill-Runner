## 1. Change Artifacts
- [x] 1.1 Create proposal, design, and spec deltas for enabling Claude in agent harness

## 2. Runtime Fix
- [x] 2.1 Update `agent_harness/runtime.py` to accept `claude` in the supported engine set
- [x] 2.2 Keep Claude on the shared non-codex harness path without new engine-specific injection logic

## 3. Validation
- [x] 3.1 Add runtime regression tests for Claude start/resume in harness
- [x] 3.2 Add CLI smoke coverage for Claude engine syntax
- [x] 3.3 Run targeted pytest and mypy
