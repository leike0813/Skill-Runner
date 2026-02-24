## 1. Patcher Refactor

- [x] 1.1 Refactor `server/services/skill_patcher.py` to modular patch plan pipeline
- [x] 1.2 Add template registry/loader for 5 runtime patch templates
- [x] 1.3 Add artifact placeholder rendering for `{artifact_lines}`
- [x] 1.4 Add dynamic output schema module integration
- [x] 1.5 Remove legacy completion contract file dependency

## 2. Dynamic Output Schema

- [x] 2.1 Add `server/services/skill_patch_output_schema.py`
- [x] 2.2 Cover `anyOf/oneOf`, arrays, object-required hints, artifact fields
- [x] 2.3 Ensure marker `### Output Schema Specification` is stable

## 3. Integration

- [x] 3.1 Update `server/adapters/codex_adapter.py` patch call context
- [x] 3.2 Update `server/adapters/gemini_adapter.py` patch call context
- [x] 3.3 Update `server/adapters/iflow_adapter.py` patch call context
- [x] 3.4 Update `agent_harness/skill_injection.py` to reuse `patch_skill_md`

## 4. OpenSpec

- [x] 4.1 Add capability `skill-patch-modular-injection`
- [x] 4.2 Modify `interactive-engine-turn-protocol` patch injection requirements
- [x] 4.3 Modify `ephemeral-skill-upload-and-run` where patch behavior is referenced
- [x] 4.4 Add cross-link follow-up from interactive-47 to interactive-48

## 5. Tests

- [x] 5.1 Add `tests/unit/test_skill_patcher_pipeline.py`
- [x] 5.2 Add `tests/unit/test_skill_patch_output_schema.py`
- [x] 5.3 Update `tests/unit/test_skill_patcher.py`
- [x] 5.4 Update `tests/unit/test_agent_harness_runtime.py`
- [x] 5.5 Update adapter patch invocation tests

## 6. Validation

- [x] 6.1 Run `tests/unit/test_skill_patcher.py`
- [x] 6.2 Run `tests/unit/test_skill_patcher_pipeline.py`
- [x] 6.3 Run `tests/unit/test_skill_patch_output_schema.py`
- [x] 6.4 Run `tests/unit/test_agent_harness_runtime.py`
- [x] 6.5 Run adapter and protocol regression tests
