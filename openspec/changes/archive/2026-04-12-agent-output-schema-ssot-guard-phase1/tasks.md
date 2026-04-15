## 1. OpenSpec Change Artifacts

- [ ] 1.1 Create proposal.md for the JSON-only SSOT guard slice with modified capability mapping.
- [ ] 1.2 Create design.md that fixes the same-attempt repair, union schema, and legacy deprecation boundaries.
- [ ] 1.3 Add delta specs for `interactive-engine-turn-protocol`, `interactive-run-lifecycle`, `interactive-decision-policy`, `output-json-repair`, and `skill-patch-modular-injection`.

## 2. Machine Contract and Guard Surface

- [ ] 2.1 Add `server/contracts/invariants/agent_output_protocol_invariants.yaml` with `auto_final_contract`, `interactive_union_contract`, `repair_loop`, `audit_requirements`, and `legacy_deprecations`.
- [ ] 2.2 Add `tests/common/agent_output_protocol_contract.py` to load and validate the new contract shape.
- [ ] 2.3 Add `tests/unit/test_agent_output_protocol_contract.py` to guard final-marker, union-branch, repair-loop, and legacy-deprecation semantics.

## 3. ask_user Contract Repositioning

- [ ] 3.1 Rewrite `server/contracts/schemas/ask_user.schema.yaml` so it documents `ui_hints` capability vocabulary instead of `<ASK_USER_YAML>` protocol structure.
- [ ] 3.2 Add a light test that confirms the file is now vocabulary-oriented and no longer shaped as an ask-user wrapper protocol.

## 4. Validation

- [ ] 4.1 Run the new output protocol guard tests.
- [ ] 4.2 Re-run existing invariant suites (`test_session_invariant_contract.py`, `test_session_state_model_properties.py`, `test_fcmp_mapping_properties.py`) to confirm no forced semantic drift.
- [ ] 4.3 Re-run any lightweight ask-user/schema guard test added in this slice.
