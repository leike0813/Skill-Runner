## 1. Shared Conversion Core Refactor

- [ ] 1.1 Extract current conversion logic from `scripts/convert_skill.py` into a reusable core module (analyze/materialize/validate/report)
- [ ] 1.2 Define a normalized conversion context model used by both directory mode and zip mode
- [ ] 1.3 Keep output contract unchanged for core artifacts (`converted_skill.zip`, `conversion_report.json`, converted skill dir)
- [ ] 1.4 Add compatibility wrapper so existing zip-based entry path keeps working during refactor

## 2. Directory Mode Support

- [ ] 2.1 Add source mode selector (`source_type=directory|zip` or equivalent CLI flags) to converter entrypoint
- [ ] 2.2 Implement directory loader with canonical path validation and source root resolution
- [ ] 2.3 Ensure directory mode supports interactive-first ambiguity handling
- [ ] 2.4 Ensure directory mode can still run in non-interactive/batch mode with explicit defaults

## 3. Zip Mode Compatibility and Safety

- [ ] 3.1 Preserve current zip extraction and zip-slip safety checks
- [ ] 3.2 Route zip mode through the shared conversion core
- [ ] 3.3 Verify no behavior regressions in generated contracts compared with pre-refactor output

## 4. SKILL.md and Reference Contract Consistency

- [ ] 4.1 Ensure both modes patch `SKILL.md` with the same Skill Runner execution guidance block
- [ ] 4.2 Ensure both modes always include `references/file_protocol.md` in converted output
- [ ] 4.3 Ensure patched `SKILL.md` explicitly points to `references/file_protocol.md`

## 5. Mode Parity Guarantees

- [ ] 5.1 Add deterministic fixture where equivalent source content is converted via directory and zip modes
- [ ] 5.2 Assert semantic parity for generated `assets/runner.json` and the three schema files
- [ ] 5.3 Assert parity for required guidance reference in patched `SKILL.md`

## 6. Tests and Validation

- [ ] 6.1 Extend unit tests to cover directory mode success/failure paths
- [ ] 6.2 Keep/extend zip mode tests to ensure backward compatibility
- [ ] 6.3 Add parity tests for directory vs zip output contracts
- [ ] 6.4 Run mypy and targeted pytest suites for converter-related modules

## 7. Documentation and Usage Updates

- [ ] 7.1 Update converter `SKILL.md` usage examples to include directory mode and zip mode flows
- [ ] 7.2 Add concise docs on when to use interactive directory mode vs zip mode
- [ ] 7.3 Document any new CLI flags/parameters introduced for dual-mode support

