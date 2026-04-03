## 1. Change Artifacts
- [x] 1.1 Create proposal/design/spec deltas for adapter-profile-command-defaults-unification

## 2. Contract Migration
- [x] 2.1 Add required `command_defaults` to adapter profile schema and loader
- [x] 2.2 Populate `command_defaults` in all engine adapter profiles

## 3. Runtime Refactor
- [x] 3.1 Migrate adapters and builders to `AdapterProfile.command_defaults`
- [x] 3.2 Remove `engine_command_profile.py`, registry hooks, and per-engine `config/command_profile.json`
- [x] 3.3 Migrate UI shell capability provider to adapter profile defaults

## 4. Validation
- [x] 4.1 Update docs and tests for the new command defaults contract
- [x] 4.2 Run targeted pytest and mypy validation
