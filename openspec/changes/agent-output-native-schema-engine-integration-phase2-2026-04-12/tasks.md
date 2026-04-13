## 1. OpenSpec Artifacts

- [x] 1.1 Create proposal, design, and spec artifacts for native schema dispatch integration.
- [x] 1.2 Capture the Claude/Codex dispatch contract and audit expectations in delta specs.

## 2. Engine Dispatch Integration

- [x] 2.1 Add a shared helper for resolving the run-scoped output schema relpath from command-builder options.
- [x] 2.2 Update Claude headless command defaults and start/resume builder logic to inject `--json-schema`.
- [x] 2.3 Update Codex start/resume builder logic to inject `--output-schema`.
- [x] 2.4 Preserve passthrough/harness command ownership and existing start/resume structure.

## 3. Validation

- [x] 3.1 Update builder/profile tests to assert native schema flags and Claude `json` output mode.
- [x] 3.2 Add adapter-level audit tests so first-attempt spawn-command snapshots show injected schema flags.
- [x] 3.3 Run targeted pytest suites and `mypy`, then verify OpenSpec apply/status output.
