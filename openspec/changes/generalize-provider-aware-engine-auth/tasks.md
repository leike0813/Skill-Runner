## OpenSpec

- [x] Create change directory and `.openspec.yaml`
- [x] Write `proposal.md`
- [x] Write `design.md`
- [x] Add delta specs for shared provider-aware contracts

## Documentation

- [x] Update `docs/api_reference.md` jobs request guidance to recommend `engine + provider_id + model`
- [x] Update engine model/auth import/auth session API documentation to use provider-aware wording
- [x] Preserve explicit compatibility notes for legacy `opencode` `provider/model` usage

## Validation

- [x] Cross-check shared change wording against current implementation
- [x] Cross-check qwen change boundary so shared behavior is no longer owned by qwen docs
- [x] Run `openspec validate --changes --json`
