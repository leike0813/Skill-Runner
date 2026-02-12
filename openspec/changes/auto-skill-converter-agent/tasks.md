## 1. Conversion Pipeline Skeleton

- [ ] 1.1 Add converter skill directory scaffold under `skills/` with `SKILL.md` and `assets/` placeholders
- [ ] 1.2 Implement analysis phase entrypoint to load source skill package and collect metadata snapshot
- [ ] 1.3 Implement materialization phase entrypoint to write patched/generated output package
- [ ] 1.4 Define converter runtime options (interactive mode, non-interactive mode, strict validation mode)

## 2. Source Package Loading and Safety

- [ ] 2.1 Implement source package loader supporting directory input and zip input
- [ ] 2.2 Enforce path safety checks during zip extraction (no absolute path, no traversal)
- [ ] 2.3 Enforce single top-level skill directory constraint for archive inputs
- [ ] 2.4 Add normalized internal model for source identity (`skill_id`, frontmatter name, runner id if present)

## 3. Interactive Decision Flow

- [ ] 3.1 Implement ambiguity detector for missing/inconsistent metadata
- [ ] 3.2 Implement interactive question templates for unresolved identity and schema assumptions
- [ ] 3.3 Implement non-interactive fallback path using provided defaults/policies
- [ ] 3.4 Record user decisions and applied defaults into conversion context for reproducibility

## 4. SKILL.md Patching

- [ ] 4.1 Implement bounded patch strategy that preserves original domain instructions
- [ ] 4.2 Add/patch Skill Runner execution contract block (execution assumptions, output conventions, failure behavior)
- [ ] 4.3 Ensure patched `SKILL.md` explicitly references `references/file_protocol.md` for schema/runner generation guidance
- [ ] 4.4 Detect and warn on conflicting legacy instructions instead of silent overwrite
- [ ] 4.5 Add regression fixtures for markdown variants (with/without frontmatter, custom sections)

## 5. AutoSkill Assets Generation

- [ ] 5.1 Implement `assets/runner.json` generator from identity + policy templates
- [ ] 5.2 Implement `assets/input.schema.json` generator with conservative defaults
- [ ] 5.3 Implement `assets/parameter.schema.json` generator with conservative defaults
- [ ] 5.4 Implement `assets/output.schema.json` generator aligned to artifacts contract conventions
- [ ] 5.5 Ensure generated schema paths and runner schema references are self-consistent

## 6. Output Validation and Reporting

- [ ] 6.1 Reuse/install-parity validation rules to validate converted package structure
- [ ] 6.2 Fail conversion on non-recoverable contract errors with actionable messages
- [ ] 6.3 Emit `conversion_report.json` with patched/created files, warnings, errors, and applied defaults
- [ ] 6.4 Add warning taxonomy (`inferred-default`, `identity-normalized`, `conflict-detected`, etc.)

## 7. Packaging and Integration Path

- [ ] 7.1 Produce install-ready package layout compatible with `/v1/skill-packages/install`
- [ ] 7.2 Copy `docs/file_protocol.md` into generated package as `references/file_protocol.md`
- [ ] 7.3 Add optional output packaging step (zip) for direct API upload workflow
- [ ] 7.4 Add end-to-end conversion fixture that can be installed without mandatory manual edits

## 8. Tests and Documentation

- [ ] 8.1 Add unit tests for analyzer/materializer and identity resolution branches
- [ ] 8.2 Add unit tests for `SKILL.md` patch behavior and conflict warning generation
- [ ] 8.3 Add unit/integration test to assert `references/file_protocol.md` exists in successful conversion output
- [ ] 8.4 Add unit/integration test to assert `SKILL.md` includes reference to `references/file_protocol.md`
- [ ] 8.5 Add integration tests for successful conversion and expected failure cases
- [ ] 8.6 Update docs with converter usage (interactive flow, non-interactive flow, output handoff to install API)
