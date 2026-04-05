## 1. Capability Mapping

- [x] 1.1 Audit the three qwen engine-specific specs and confirm every still-valid requirement has a shared capability destination.
- [x] 1.2 Align the migration map in proposal/design with the actual shared capability set that will absorb qwen auth, parser, and UI shell requirements.

## 2. Shared Spec Consolidation

- [x] 2.1 Update `engine-auth-strategy-policy` and `engine-auth-observability` so qwen auth requirements live under shared provider-aware auth capabilities.
- [x] 2.2 Update `engine-adapter-runtime-contract`, `engine-runtime-config-layering`, and `interactive-run-observability` so qwen parser and UI shell asset requirements live under shared runtime capabilities.
- [x] 2.3 Update `ui-engine-inline-terminal` so qwen UI shell security behavior is represented as inline-terminal session policy rather than a standalone qwen capability.

## 3. Engine-Specific Capability Removal

- [x] 3.1 Add REMOVED delta specs for `engine-auth-qwen`, `qwen-stream-parser`, and `qwen-ui-shell-security` with explicit Reason and Migration guidance.
- [x] 3.2 Verify no active or planned change still needs to write new requirements against the removed qwen-specific capabilities.

## 4. Validation And Follow-Up

- [x] 4.1 Validate the change artifacts with OpenSpec and confirm the change is apply-ready.
- [x] 4.2 During sync/archive, remove the three qwen-specific main specs after their shared replacements have been merged.
