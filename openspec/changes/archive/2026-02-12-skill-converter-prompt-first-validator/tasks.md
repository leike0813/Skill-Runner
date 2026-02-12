## 1. Prompt-First Workflow Refactor

- [x] 1.1 Rewrite `skills/skill-converter-agent/SKILL.md` into staged conversion flow (parse -> classify -> decide -> convert -> validate)
- [x] 1.2 Encode fixed three-state classification in instructions (`not_convertible`, `convertible_with_constraints`, `ready_for_auto`)
- [x] 1.3 Define explicit mode policy in `SKILL.md` for interactive confirmation vs auto progression
- [x] 1.4 Ensure `not_convertible` branch halts and returns failure reason only

## 2. Script Scope Reduction

- [x] 2.1 Remove conversion logic scripts (`convert_skill.py`, `converter_core.py`) from active skill execution path
- [x] 2.2 Keep only final validator execution entry script in `skills/skill-converter-agent/scripts/`
- [x] 2.3 Ensure skill asset references no longer depend on removed conversion scripts

## 3. Embedded Validator Implementation

- [x] 3.1 Add embedded validator module inside skill package with install-contract checks equivalent to `SkillPackageValidator`
- [x] 3.2 Implement final validator script that validates converted directory/zip and returns structured pass/fail JSON
- [x] 3.3 Ensure embedded validator has no import dependency on `server/services` at runtime
- [x] 3.4 Preserve checks for identity consistency, schema references, required metadata, version parseability, and zip path safety

## 4. Output Contract and References

- [x] 4.1 Ensure successful conversion output still includes complete install-ready package artifacts
- [x] 4.2 Ensure `references/file_protocol.md` is bundled in generated package
- [x] 4.3 Ensure patched/generated `SKILL.md` explicitly points to `references/file_protocol.md`

## 5. Tests and Parity Validation

- [x] 5.1 Replace converter script behavior tests with prompt-first contract tests
- [x] 5.2 Add tests for three-state classification branch expectations and output semantics
- [x] 5.3 Add tests verifying `not_convertible` returns failure reason only and no package output
- [x] 5.4 Add parity tests comparing embedded validator outcomes against project `SkillPackageValidator` on shared fixtures
- [x] 5.5 Run mypy and targeted pytest suites for converter skill and embedded validator

## 6. Documentation and OpenSpec Sync

- [x] 6.1 Update converter usage docs to describe prompt-first flow and validator-only scripting
- [x] 6.2 Document runtime behavior for interactive mode vs auto mode in converter skill docs
- [x] 6.3 Update OpenSpec artifact checkboxes/status during implementation progress
