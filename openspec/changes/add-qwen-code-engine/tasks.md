## OpenSpec

- [x] Create change directory and `.openspec.yaml`
- [x] Rewrite `proposal.md` to match the landed qwen implementation
- [x] Rewrite `design.md` to reflect static manifest, top-level CLI contract, and shared provider-aware auth
- [x] Sync delta specs with current qwen behavior

## Implementation

### Engine Package

- [x] Create `server/engines/qwen/adapter/` directory structure
- [x] Implement `QwenExecutionAdapter`
- [x] Implement `QwenCommandBuilder`
- [x] Implement `QwenStreamParser` (phase-1 stable parse only)
- [x] Implement `QwenConfigComposer`
- [x] Create `adapter_profile.json` with managed CLI / model catalog / import rules
- [x] Create config files (`bootstrap.json`, `default.json`, `enforced.json`)
- [x] Create model files (`manifest.json`, `models_seed.json`, versioned snapshot`)
- [x] Create `qwen_config_schema.json`

### Central Registration

- [x] Add `qwen` to `ENGINE_KEYS`
- [x] Register `QwenExecutionAdapter`
- [x] Register `QwenAuthDetector`

### Agent Harness Integration

- [x] Add `qwen` to skill injection targets
- [x] Verify `.qwen/skills/` layout and injection support

### Authentication System

- [x] Create `server/engines/qwen/auth/` directory structure
- [x] Create `auth_providers.json` with `qwen-oauth`, `coding-plan-china`, `coding-plan-global`
- [x] Implement provider registry
- [x] Create `auth_strategy.yaml`
- [x] Implement `qwen_oauth_proxy_flow.py`
- [x] Implement `coding_plan_flow.py`
- [x] Implement `cli_delegate_flow.py`
- [x] Implement `runtime_handler.py`
- [x] Wire qwen into shared provider-aware auth strategy / bootstrap / UI / import selection
- [x] Align OAuth import file name to `oauth_creds.json`

### Management / Bootstrap / Docs

- [x] Add qwen to managed install / upgrade / bootstrap defaults
- [x] Add qwen to engine status / management / UI surfaces
- [x] Update this change to remove stale `runtime_probe` / old CLI wording
- [x] Update API reference to document current qwen-facing behavior

## Testing

- [x] Add/update unit tests for qwen adapter, auth import, auth strategy, management/UI integration
- [x] Run targeted pytest suites and ensure they pass
- [x] Run focused mypy checks for touched implementation files

## Future Enhancements

- [ ] Implement live streaming parser
- [ ] Add `stream_event` incremental parsing
- [ ] Add `tool_call` / MCP process-event extraction
- [ ] Introduce richer qwen-specific auth detection patterns if needed
