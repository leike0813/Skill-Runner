# Unit Test Audit Report - Skill Runner Project

**Generated:** 2026-04-15 15:26:22
**Total Unit Test Files:** 196
**Total Test Functions:** 1316
**Total Lines of Test Code:** 45,631

---

## 1. Executive Summary

### Key Statistics

| Metric | Value |
|--------|-------|
| Total unit test files | 196 |
| Total test functions | 1316 |
| Total lines of test code | 45,631 |
| Average tests per file | 6.7 |
| Average lines per file | 233 |

### Distribution by Category

| Category | Files | Tests | % of Tests |
|----------|-------|-------|------------|
| orchestration/core | 24 | 238 | 18.1% |
| platform/infrastructure | 37 | 197 | 15.0% |
| adapter | 14 | 181 | 13.8% |
| ui/routes | 8 | 173 | 13.1% |
| auth_detection | 32 | 135 | 10.3% |
| runtime_protocols | 27 | 101 | 7.7% |
| skill_management | 13 | 93 | 7.1% |
| cli/harness | 7 | 64 | 4.9% |
| misc/structural | 14 | 53 | 4.0% |
| config/settings | 11 | 50 | 3.8% |
| engine_management | 8 | 20 | 1.5% |
| structured_output | 1 | 11 | 0.8% |

### Distribution by Importance

| Importance | Tests | % of Tests | Description |
|------------|-------|------------|-------------|
| P0 (Critical) | 92 | 7.0% | Core security, critical path, contract enforcement |
| P1 (High) | 672 | 51.1% | Important functionality, error handling, edge cases |
| P2 (Normal) | 545 | 41.4% | Standard functionality, configuration, formatting |
| P3 (Low) | 7 | 0.5% | Minor/cosmetic tests |

### Distribution by Test Type

| Type | Tests | % of Tests |
|------|-------|------------|
| functional | 1096 | 83.3% |
| contract | 107 | 8.1% |
| structural | 59 | 4.5% |
| regression | 53 | 4.0% |
| security | 1 | 0.1% |
| property | 0 | 0.0% |
| governance | 0 | 0.0% |

### Key Findings

1. **Strong functional test coverage**: 83% of tests are functional tests, covering the main execution paths across all major subsystems.
2. **Good contract test density**: 8% of tests validate API/output contracts, ensuring interface stability.
3. **Security boundary testing present**: Tests exist for zip-slip protection, path traversal prevention, integrity manifest verification, and auth session enforcement.
4. **Governance tests enforce architectural constraints**: Import boundary tests prevent coupling between runtime and orchestration layers.
5. **Adapter tests form the largest category**: 14 adapter test files with 181 tests covering 6+ engine adapters (Claude, Codex, Gemini, iFlow, OpenCode, Qwen).

### Recommendations

1. **Increase property-based testing**: Currently minimal. Consider adding property tests for state machines, protocol parsers, and output coalescers.
2. **Add regression test suites**: Currently limited to deprecation enforcement. Add regression tests for known bug patterns.
3. **Upgrade P2 structural tests**: Many structural/import boundary tests could be elevated to P1 as they prevent architectural regression.
4. **Consolidate small test files**: Several files with 1-2 tests could be merged (e.g., `test_engine_interaction_gate.py` with related engine tests).
5. **Add integration-style tests**: Current tests are predominantly unit-level. Cross-component integration tests would improve confidence.
6. **Expand test coverage for chat replay subsystem**: Only 5 files with 18 tests for chat replay/Fcmp features.

---

## 2. Per-File Audit Details

This section lists all 196 unit test files with their test cases, categorized by subsystem.

### Category: adapter

#### `test_adapter_command_profiles.py`

- **Test cases:** 21
- **Lines:** 755

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_codex_api_start_command_applies_profile_defaults` | Tests default codex api start command applies profile s | Default configuration | functional | P0 |
| `test_codex_harness_start_command_passthrough_without_profile` | Tests codex harness start command passthrough without profile | Standard scenario | functional | P1 |
| `test_codex_harness_start_command_does_not_inject_output_schema` | Tests output codex harness start command does not inject  schema | Standard scenario | contract | P1 |
| `test_codex_start_command_fallbacks_full_auto_to_yolo_when_landlock_disabled` | Tests fallback for codex start command s full auto to yolo when landlock disabled | Fallback path | functional | P0 |
| `test_codex_harness_passthrough_full_auto_fallbacks_to_yolo_when_landlock_disabled` | Tests fallback for codex harness passthrough full auto s to yolo when landlock disabled | Fallback path | functional | P1 |
| `test_codex_resume_command_fallbacks_full_auto_to_yolo_when_probe_unavailable` | Tests fallback for codex resume command s full auto to yolo when probe unavailable | Fallback path | functional | P0 |
| `test_gemini_start_command_profile_can_be_disabled` | Tests gemini start command profile can be disabled | Standard scenario | functional | P1 |
| `test_codex_resume_command_preserves_profile_flags` | Tests codex resume command preserves profile flags | Standard scenario | functional | P1 |
| `test_codex_start_command_injects_output_schema_when_available` | Tests output codex start command injects  schema when available | Standard scenario | contract | P1 |
| `test_codex_start_command_skips_output_schema_when_profile_disabled` | Tests output codex start command skips  schema when profile disabled | Standard scenario | contract | P2 |
| `test_codex_resume_command_does_not_inject_output_schema_when_available` | Tests output codex resume command does not inject  schema when available | Standard scenario | contract | P1 |
| `test_iflow_harness_resume_command_uses_passthrough_only` | Tests iflow harness resume command uses passthrough only | Standard scenario | functional | P1 |
| `test_opencode_start_command_includes_run_format_and_model` | Tests model opencode start command includes run format and | Standard scenario | functional | P0 |
| `test_opencode_harness_resume_command_uses_session_and_passthrough_flags` | Tests session opencode harness resume command uses  and passthrough flags | Standard scenario | functional | P1 |
| `test_qwen_start_command_uses_headless_stream_json_flags` | Tests stream handling for qwen start command uses headless  json flags | Standard scenario | functional | P0 |
| `test_qwen_resume_command_uses_resume_flag_and_prompt` | Tests qwen resume command uses resume flag and prompt | Standard scenario | functional | P1 |
| `test_claude_start_command_uses_profile_command_defaults` | Tests default claude start command uses profile command s | Default configuration | functional | P0 |
| `test_claude_start_command_injects_json_schema_when_available` | Tests schema claude start command injects json  when available | Standard scenario | contract | P1 |
| `test_claude_passthrough_start_command_does_not_inject_json_schema` | Tests schema claude passthrough start command does not inject json | Standard scenario | contract | P1 |
| `test_claude_start_command_skips_json_schema_when_profile_disabled` | Tests schema claude start command skips json  when profile disabled | Standard scenario | contract | P2 |
| `test_claude_resume_command_injects_json_schema_when_available` | Tests schema claude resume command injects json  when available | Standard scenario | contract | P1 |

**Assessment:** Comprehensive coverage with 21 test functions.

#### `test_adapter_common_components.py`

- **Test cases:** 12
- **Lines:** 389

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_prompt_builder_common_resolves_template_and_context` | Tests prompt builder common resolves template and context | Standard scenario | functional | P1 |
| `test_resolve_template_text_prefers_engine_prompt_over_common` | Tests resolve template text prefers engine prompt over common | Standard scenario | functional | P1 |
| `test_resolve_template_text_falls_back_to_common_prompt` | Tests resolve template text falls back to common prompt | Standard scenario | functional | P2 |
| `test_normalize_prompt_file_path_for_windows_and_posix` | Tests normalize prompt file path for windows and posix | Standard scenario | functional | P2 |
| `test_normalize_prompt_file_input_context_only_updates_file_sources` | Tests update of normalize prompt file input context only  file sources | Standard scenario | functional | P1 |
| `test_session_codec_common_helpers` | Tests session codec common helpers | Standard scenario | functional | P1 |
| `test_run_folder_validator_common_accepts_minimal_execution_contract` | Validates acceptance of run folder validator common  minimal execution contract | Contract verification | contract | P1 |
| `test_run_folder_validator_common_rejects_missing_schema_file` | Validates rejection of run folder validator common  missing schema file | Missing required field | contract | P1 |
| `test_claude_default_prompt_template_is_used_and_includes_skill_dir` | Tests default claude  prompt template is used and includes skill dir | Default configuration | functional | P1 |
| `test_claude_prompt_builder_uses_common_prompt_when_engine_prompt_missing` | Tests claude prompt builder uses common prompt when engine prompt missing | Missing required field | functional | P2 |
| `test_claude_default_prompt_template_avoids_sandbox_first_when_probe_unavailable` | Tests default claude  prompt template avoids sandbox first when probe unavailable | Default configuration | functional | P1 |
| `test_prompt_render_context_exposes_engine_relative_dirs` | Tests prompt render context exposes engine relative dirs | Standard scenario | functional | P1 |

**Assessment:** Comprehensive coverage with 12 test functions.

#### `test_adapter_component_contracts.py`

- **Test cases:** 1
- **Lines:** 95

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_engine_execution_adapter_component_contracts` | Tests engine execution adapter component contracts | Contract verification | contract | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_adapter_failfast.py`

- **Test cases:** 19
- **Lines:** 870

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_capture_process_output_timeout_classified` | Tests timeout for capture process output  classified | Timeout scenario | functional | P0 |
| `test_capture_process_output_auth_required_classified` | Tests auth capture process output  required classified | Standard scenario | functional | P0 |
| `test_capture_process_output_low_confidence_auth_does_not_override_nonzero_exit` | Tests auth capture process output low confidence  does not override nonzero exit | Override behavior | functional | P1 |
| `test_capture_process_output_auth_required_early_exit_on_blocking_idle` | Tests auth capture process output  required early exit on blocking idle | Standard scenario | functional | P0 |
| `test_capture_process_output_auth_probe_retries_after_throttled_chunk_completion` | Tests auth capture process output  probe retries after throttled chunk completion | Standard scenario | functional | P1 |
| `test_capture_process_output_auth_required_does_not_depend_on_live_diagnostic_publish` | Tests auth capture process output  required does not depend on live diagnostic publish | Standard scenario | functional | P1 |
| `test_capture_process_output_stream_writes_logs_during_run` | Tests stream handling for capture process output  writes logs during run | Standard scenario | functional | P1 |
| `test_incremental_utf8_text_decoder_matches_one_shot_decode_for_split_multibyte_and_invalid_bytes` | Tests incremental utf8 text decoder matches one shot decode for split multibyte and invalid bytes | Invalid input | functional | P1 |
| `test_capture_process_output_uses_incremental_utf8_decoding_for_logs_and_live_stream` | Tests stream handling for capture process output uses incremental utf8 decoding for logs and live | Standard scenario | functional | P1 |
| `test_capture_process_output_auth_probe_uses_recent_window_and_low_frequency` | Tests auth capture process output  probe uses recent window and low frequency | Standard scenario | functional | P2 |
| `test_capture_process_output_bounded_audit_drain_does_not_block_return` | Tests audit capture process output bounded  drain does not block return | Standard scenario | functional | P1 |
| `test_timeout_terminates_process_group_and_returns_promptly` | Tests return value for timeout terminates process group and  promptly | Timeout scenario | functional | P0 |
| `test_auth_completed_resume_revalidates_run_folder_before_execute` | Validates auth completed resume re run folder before execute | Standard scenario | functional | P1 |
| `test_runtime_dependencies_probe_success_wraps_command` | Tests probe runtime dependencies  success wraps command | Success scenario | functional | P1 |
| `test_runtime_dependencies_probe_success_wraps_normalized_command` | Tests probe runtime dependencies  success wraps normalized command | Success scenario | functional | P1 |
| `test_runtime_dependencies_probe_failure_falls_back_and_warns` | Tests failure handling for runtime dependencies probe  falls back and warns | Failure scenario | functional | P1 |
| `test_normalize_windows_npm_cmd_shim_rewrites` | Tests normalize windows npm cmd shim rewrites | Standard scenario | functional | P1 |
| `test_normalize_windows_npm_cmd_shim_non_windows_noop` | Tests normalize windows npm cmd shim non windows noop | Standard scenario | functional | P2 |
| `test_normalize_windows_npm_cmd_shim_parse_failure_fallback` | Tests fallback for normalize windows npm cmd shim parse failure | Failure scenario | functional | P2 |

**Assessment:** Comprehensive coverage with 19 test functions.

#### `test_adapter_io_chunks_journal.py`

- **Test cases:** 4
- **Lines:** 291

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_capture_process_output_writes_io_chunks_journal` | Tests output capture process  writes io chunks journal | Standard scenario | functional | P1 |
| `test_capture_process_output_sanitizes_oversized_ndjson_before_io_chunks` | Tests output capture process  sanitizes oversized ndjson before io chunks | Standard scenario | functional | P1 |
| `test_capture_process_output_preserves_oversized_qwen_assistant_message_in_io_chunks` | Tests output capture process  preserves oversized qwen assistant message in io chunks | Standard scenario | functional | P2 |
| `test_capture_process_output_quarantines_unrepairable_overflow_into_sidecar` | Tests output capture process  quarantines unrepairable overflow into sidecar | Standard scenario | functional | P1 |

**Assessment:** Adequate coverage with 4 test functions.

#### `test_adapter_live_stream_emission.py`

- **Test cases:** 21
- **Lines:** 1091

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_ndjson_live_session_keeps_split_chunk_offsets_stable` | Tests session ndjson live  keeps split chunk offsets stable | Standard scenario | functional | P2 |
| `test_ndjson_live_session_ignores_invalid_json_and_routes_multiple_streams` | Tests stream handling for ndjson live session ignores invalid json and routes multiple s | Invalid input | functional | P1 |
| `test_repair_truncated_json_line_closes_string_and_containers` | Tests repair truncated json line closes string and containers | Standard scenario | functional | P1 |
| `test_ndjson_live_session_repairs_overflowed_line_and_resyncs` | Tests session ndjson live  repairs overflowed line and resyncs | Standard scenario | functional | P1 |
| `test_ndjson_ingress_sanitizer_repairs_oversized_line_and_resyncs` | Tests sync ndjson ingress sanitizer repairs oversized line and res | Standard scenario | functional | P1 |
| `test_ndjson_ingress_sanitizer_substitutes_unrepairable_line_with_runtime_diagnostic` | Tests ndjson ingress sanitizer substitutes unrepairable line with runtime diagnostic | Standard scenario | functional | P1 |
| `test_ndjson_live_session_preserves_oversized_exempt_reasoning_line` | Tests session ndjson live  preserves oversized exempt reasoning line | Standard scenario | functional | P2 |
| `test_ndjson_ingress_sanitizer_preserves_oversized_exempt_assistant_message` | Tests ndjson ingress sanitizer preserves oversized exempt assistant message | Standard scenario | functional | P2 |
| `test_codex_live_session_keeps_raw_ref_stable_for_split_ndjson_line` | Tests session codex live  keeps raw ref stable for split ndjson line | Standard scenario | functional | P2 |
| `test_opencode_live_session_keeps_raw_ref_stable_for_split_ndjson_line` | Tests session opencode live  keeps raw ref stable for split ndjson line | Standard scenario | functional | P2 |
| `test_live_runtime_emitter_publishes_intermediate_then_final_on_exit` | Tests emission of live runtime ter publishes intermediate then final on exit | Standard scenario | functional | P2 |
| `test_live_runtime_emitter_coalesces_raw_stderr_blocks` | Tests emission of live runtime ter coalesces raw stderr blocks | Standard scenario | functional | P2 |
| `test_live_runtime_emitter_consumes_run_handle_immediately_and_warns_on_change` | Tests emission of live runtime ter consumes run handle immediately and warns on change | Standard scenario | functional | P2 |
| `test_live_runtime_emitter_delays_raw_until_finish_for_terminal_semantic_only_parser` | Tests emission of live runtime ter delays raw until finish for terminal semantic only parser | Standard scenario | functional | P2 |
| `test_live_runtime_emitter_suppresses_claude_raw_stdout_when_semantics_consume_rows` | Tests emission of live runtime ter suppresses claude raw stdout when semantics consume rows | Standard scenario | functional | P2 |
| `test_live_runtime_emitter_projects_pending_display_for_claude_final_and_chat_replay` | Tests emission of live runtime ter projects pending display for claude final and chat replay | Standard scenario | functional | P2 |
| `test_live_runtime_emitter_uses_claude_result_text_only_as_fallback_message` | Tests fallback for live runtime emitter uses claude result text only as  message | Fallback path | functional | P2 |
| `test_live_runtime_emitter_does_not_emit_claude_result_text_when_structured_output_exists` | Tests emission of live runtime ter does not emit claude result text when structured output exists | Standard scenario | structural | P2 |
| `test_live_runtime_emitter_repairs_overflowed_claude_tool_result_and_resyncs` | Tests sync live runtime emitter repairs overflowed claude tool result and res | Standard scenario | functional | P1 |
| `test_live_runtime_emitter_preserves_oversized_claude_assistant_message` | Tests emission of live runtime ter preserves oversized claude assistant message | Standard scenario | functional | P2 |
| `test_live_runtime_emitter_emits_qwen_process_events_and_single_final` | Tests emission of live runtime ter emits qwen process events and single final | Standard scenario | functional | P2 |

**Assessment:** Comprehensive coverage with 21 test functions.

#### `test_adapter_parsing.py`

- **Test cases:** 20
- **Lines:** 352

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_gemini_parse_output_from_envelope` | Tests output gemini parse  from envelope | Standard scenario | functional | P1 |
| `test_gemini_parse_output_from_text` | Tests output gemini parse  from text | Standard scenario | functional | P1 |
| `test_codex_parse_output_from_stream_event` | Tests stream handling for codex parse output from  event | Standard scenario | functional | P1 |
| `test_codex_parse_output_from_raw_text` | Tests output codex parse  from raw text | Standard scenario | functional | P1 |
| `test_codex_runtime_stream_detects_logged_out_reauth_signal_high_confidence` | Detects codex runtime stream  logged out reauth signal high confidence | Standard scenario | functional | P0 |
| `test_iflow_parse_output_from_code_fence` | Tests output iflow parse  from code fence | Standard scenario | functional | P1 |
| `test_iflow_parse_output_from_raw_text` | Tests output iflow parse  from raw text | Standard scenario | functional | P1 |
| `test_gemini_parse_output_strict_json_without_repair` | Tests output gemini parse  strict json without repair | Standard scenario | functional | P2 |
| `test_opencode_parse_output_from_stream_text_event` | Tests stream handling for opencode parse output from  text event | Standard scenario | functional | P1 |
| `test_claude_parse_output_from_stream_result_event` | Tests stream handling for claude parse output from  result event | Standard scenario | functional | P1 |
| `test_claude_build_start_command_uses_stream_json_output_flags` | Tests stream handling for claude build start command uses  json output flags | Standard scenario | functional | P0 |
| `test_claude_runtime_stream_detects_not_logged_in_auth_signal` | Detects claude runtime stream  not logged in auth signal | Standard scenario | functional | P0 |
| `test_claude_runtime_stream_detects_not_logged_in_auth_signal_from_ndjson_login_prompt` | Detects claude runtime stream  not logged in auth signal from ndjson login prompt | Standard scenario | functional | P0 |
| `test_claude_runtime_stream_extracts_run_handle_and_semantic_process_events` | Tests extraction of claude runtime stream  run handle and semantic process events | Standard scenario | functional | P1 |
| `test_claude_runtime_stream_result_echo_does_not_create_default_assistant_message` | Tests stream handling for claude runtime  result echo does not create default assistant message | Default configuration | functional | P2 |
| `test_claude_runtime_stream_uses_result_text_as_fallback_only_without_body_or_structured_output` | Tests fallback for claude runtime stream uses result text as  only without body or structured output | Fallback path | structural | P2 |
| `test_claude_runtime_stream_structured_output_without_body_does_not_emit_result_fallback_message` | Tests fallback for claude runtime stream structured output without body does not emit result  message | Fallback path | structural | P2 |
| `test_claude_runtime_stream_emits_sandbox_diagnostics_without_losing_success` | Tests stream handling for claude runtime  emits sandbox diagnostics without losing success | Success scenario | functional | P1 |
| `test_claude_runtime_stream_distinguishes_sandbox_policy_violation` | Tests stream handling for claude runtime  distinguishes sandbox policy violation | Standard scenario | functional | P1 |
| `test_claude_build_resume_command_uses_resume_flag` | Tests claude build resume command uses resume flag | Standard scenario | functional | P1 |

**Assessment:** Comprehensive coverage with 20 test functions.

#### `test_adapter_profile_loader.py`

- **Test cases:** 6
- **Lines:** 614

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_load_adapter_profile_success` | Tests load adapter profile success | Success scenario | functional | P1 |
| `test_load_adapter_profile_defaults_missing_command_features_to_disabled` | Tests default load adapter profile s missing command features to disabled | Missing required field | functional | P2 |
| `test_load_adapter_profile_engine_mismatch` | Tests load adapter profile engine mismatch | Standard scenario | functional | P1 |
| `test_validate_adapter_profiles_fail_fast` | Tests validate adapter profiles fail fast | Standard scenario | functional | P1 |
| `test_load_adapter_profile_fails_when_config_path_missing` | Tests configuration load adapter profile fails when  path missing | Missing required field | functional | P1 |
| `test_load_adapter_profile_fails_when_credential_target_is_absolute` | Tests load adapter profile fails when credential target is absolute | Standard scenario | functional | P1 |

**Assessment:** Adequate coverage with 6 test functions.

#### `test_claude_adapter.py`

- **Test cases:** 2
- **Lines:** 108

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_execute_persists_first_attempt_spawn_command_with_json_schema` | Tests schema execute persists first attempt spawn command with json | Standard scenario | contract | P1 |
| `test_execute_skips_json_schema_when_materialized_schema_is_missing` | Tests schema execute skips json  when materialized schema is missing | Missing required field | contract | P2 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_codex_adapter.py`

- **Test cases:** 16
- **Lines:** 518

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_execute_constructs_correct_command` | Tests execute constructs correct command | Standard scenario | functional | P0 |
| `test_parse_output_valid_ask_user_envelope` | Tests output parse  valid ask user envelope | Standard scenario | functional | P1 |
| `test_parse_output_invalid_ask_user_payload_returns_error` | Tests return value for parse output invalid ask user payload  error | Invalid input | functional | P2 |
| `test_extract_session_handle_from_thread_started` | Tests session extract  handle from thread started | Standard scenario | functional | P1 |
| `test_extract_session_handle_missing_thread_started_raises` | Tests that exception is raised for extract session handle missing thread started | Missing required field | functional | P1 |
| `test_parse_runtime_stream_keeps_latest_turn_only` | Tests stream handling for parse runtime  keeps laturn only | Standard scenario | functional | P1 |
| `test_parse_runtime_stream_maps_turn_complete_usage_payload` | Tests stream handling for parse runtime  maps turn complete usage payload | Standard scenario | functional | P1 |
| `test_construct_config_excludes_runtime_interactive_options` | Tests configuration construct  excludes runtime interactive options | Standard scenario | functional | P1 |
| `test_construct_config_allows_harness_profile_override` | Tests configuration construct  allows harness profile override | Override behavior | functional | P1 |
| `test_construct_config_downgrades_sandbox_when_probe_unavailable` | Tests configuration construct  downgrades sandbox when probe unavailable | Standard scenario | functional | P0 |
| `test_construct_config_prefers_runner_declared_skill_config` | Tests configuration construct  prefers runner declared skill config | Standard scenario | functional | P1 |
| `test_setup_environment_validates_run_folder_contract` | Validates setup environment  run folder contract | Contract verification | contract | P1 |
| `test_execute_resume_command_thread_id_before_prompt` | Tests execute resume command thread id before prompt | Standard scenario | functional | P1 |
| `test_run_interactive_reply_rebuilds_config_and_environment_setup` | Tests building of run interactive reply re config and environment setup | Standard scenario | functional | P1 |
| `test_execute_interactive_command_includes_auto_flags` | Tests auto mode execute interactive command includes  flags | Standard scenario | functional | P1 |
| `test_execute_persists_first_attempt_spawn_command_with_output_schema` | Tests output execute persists first attempt spawn command with  schema | Standard scenario | contract | P1 |

**Assessment:** Comprehensive coverage with 16 test functions.

#### `test_gemini_adapter.py`

- **Test cases:** 27
- **Lines:** 867

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_construct_config_includes_engine_default_layer` | Tests configuration construct  includes engine default layer | Default configuration | functional | P1 |
| `test_construct_config_prefers_runner_declared_skill_config` | Tests configuration construct  prefers runner declared skill config | Standard scenario | functional | P1 |
| `test_run_prompt_generation_strict_files` | Tests run prompt generation strict files | Standard scenario | functional | P1 |
| `test_run_missing_file_strict` | Tests run missing file strict | Missing required field | functional | P1 |
| `test_run_persists_first_attempt_prompt_to_request_input` | Tests input run persists first attempt prompt to request | Standard scenario | functional | P1 |
| `test_run_does_not_persist_prompt_after_first_attempt` | Tests run does not persist prompt after first attempt | Standard scenario | functional | P2 |
| `test_run_first_attempt_prompt_override_still_gets_global_prefix` | Tests run first attempt prompt override still gets global prefix | Override behavior | functional | P1 |
| `test_run_non_first_attempt_prompt_override_does_not_get_global_prefix` | Tests run non first attempt prompt override does not get global prefix | Override behavior | functional | P2 |
| `test_run_repair_round_prompt_override_skips_first_attempt_audit_and_prefix` | Tests audit run repair round prompt override skips first attempt  and prefix | Override behavior | functional | P2 |
| `test_build_start_and_resume_command_use_first_attempt_effective_prompt` | Tests build start and resume command use first attempt effective prompt | Standard scenario | functional | P1 |
| `test_run_persists_first_attempt_prompt_to_fallback_when_request_input_invalid` | Tests fallback for run persists first attempt prompt to  when request input invalid | Invalid input | functional | P2 |
| `test_extract_session_handle_missing_session_id_raises` | Tests that exception is raised for extract session handle missing session id | Missing required field | functional | P1 |
| `test_extract_session_handle_from_json_body` | Tests session extract  handle from json body | Standard scenario | functional | P1 |
| `test_extract_session_handle_from_plain_text_fallback` | Tests fallback for extract session handle from plain text | Fallback path | functional | P1 |
| `test_parse_runtime_stream_falls_back_to_stdout_json_lines` | Tests stream handling for parse runtime  falls back to stdout json lines | Standard scenario | functional | P1 |
| `test_parse_runtime_stream_parses_pretty_json_from_stdout` | Tests parsing of parse runtime stream  pretty json from stdout | Standard scenario | functional | P1 |
| `test_parse_runtime_stream_prefers_split_stream_over_pty_duplicate` | Tests stream handling for parse runtime  prefers split stream over pty duplicate | Duplicate operation | functional | P1 |
| `test_parse_runtime_stream_falls_back_to_pty_json_lines` | Tests stream handling for parse runtime  falls back to pty json lines | Standard scenario | functional | P1 |
| `test_parse_runtime_stream_coalesces_large_raw_stderr_blocks` | Tests stream handling for parse runtime  coalesces large raw stderr blocks | Standard scenario | functional | P2 |
| `test_parse_runtime_stream_uses_latest_response_frame` | Tests stream handling for parse runtime  uses laresponse frame | Standard scenario | functional | P1 |
| `test_live_session_assistant_message_keeps_raw_ref` | Tests session live  assistant message keeps raw ref | Standard scenario | functional | P1 |
| `test_parse_runtime_stream_detects_oauth_code_prompt` | Detects parse runtime stream  oauth code prompt | Standard scenario | functional | P0 |
| `test_parse_output_valid_ask_user_envelope` | Tests output parse  valid ask user envelope | Standard scenario | functional | P1 |
| `test_parse_output_invalid_ask_user_payload_returns_error` | Tests return value for parse output invalid ask user payload  error | Invalid input | functional | P2 |
| `test_execute_resume_command_contains_resume_flag` | Tests execute resume command contains resume flag | Standard scenario | functional | P1 |
| `test_execute_interactive_command_includes_yolo` | Tests execute interactive command includes yolo | Standard scenario | functional | P1 |
| `test_execute_auto_command_includes_yolo` | Tests auto mode execute  command includes yolo | Standard scenario | functional | P1 |

**Assessment:** Comprehensive coverage with 27 test functions.

#### `test_iflow_adapter.py`

- **Test cases:** 20
- **Lines:** 453

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_construct_config_maps_model_and_merges_iflow_config` | Tests configuration construct  maps model and merges iflow config | Standard scenario | functional | P1 |
| `test_construct_config_uses_engine_default_when_no_overrides` | Tests configuration construct  uses engine default when no overrides | Default configuration | structural | P1 |
| `test_construct_config_skill_overrides_engine_default` | Tests configuration construct  skill overrides engine default | Default configuration | functional | P1 |
| `test_construct_config_prefers_runner_declared_skill_config` | Tests configuration construct  prefers runner declared skill config | Standard scenario | functional | P1 |
| `test_extract_session_handle_from_execution_info` | Tests session extract  handle from execution info | Standard scenario | functional | P1 |
| `test_extract_session_handle_missing_session_id_raises` | Tests that exception is raised for extract session handle missing session id | Missing required field | functional | P1 |
| `test_parse_runtime_stream_extracts_session_id_from_execution_info_and_cleans_message` | Tests extraction of parse runtime stream  session id from execution info and cleans message | Standard scenario | functional | P1 |
| `test_parse_runtime_stream_extracts_session_id_from_pty_when_stdout_missing` | Tests extraction of parse runtime stream  session id from pty when stdout missing | Missing required field | functional | P1 |
| `test_parse_runtime_stream_prefers_split_stream_over_pty_duplicate` | Tests stream handling for parse runtime  prefers split stream over pty duplicate | Duplicate operation | functional | P1 |
| `test_parse_runtime_stream_uses_pty_fallback_when_split_empty` | Tests fallback for parse runtime stream uses pty  when split empty | Empty input | functional | P1 |
| `test_parse_runtime_stream_keeps_latest_round_text` | Tests stream handling for parse runtime  keeps laround text | Standard scenario | functional | P1 |
| `test_parse_runtime_stream_channel_drift_correction_diagnostics` | Tests stream handling for parse runtime  channel drift correction diagnostics | Standard scenario | functional | P1 |
| `test_live_session_assistant_message_keeps_raw_ref` | Tests session live  assistant message keeps raw ref | Standard scenario | functional | P1 |
| `test_parse_runtime_stream_keeps_resume_stderr_line_as_raw_when_execution_info_consumed` | Tests stream handling for parse runtime  keeps resume stderr line as raw when execution info consumed | Standard scenario | functional | P2 |
| `test_parse_output_valid_ask_user_envelope` | Tests output parse  valid ask user envelope | Standard scenario | functional | P1 |
| `test_parse_output_invalid_ask_user_payload_returns_error` | Tests return value for parse output invalid ask user payload  error | Invalid input | functional | P2 |
| `test_setup_environment_validates_run_folder_contract` | Validates setup environment  run folder contract | Contract verification | contract | P1 |
| `test_execute_resume_command_contains_resume_flag` | Tests execute resume command contains resume flag | Standard scenario | functional | P1 |
| `test_execute_interactive_command_includes_yolo_and_thinking` | Tests execute interactive command includes yolo and thinking | Standard scenario | functional | P1 |
| `test_execute_auto_command_includes_yolo_and_thinking` | Tests auto mode execute  command includes yolo and thinking | Standard scenario | functional | P1 |

**Assessment:** Comprehensive coverage with 20 test functions.

#### `test_opencode_adapter.py`

- **Test cases:** 7
- **Lines:** 191

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_construct_config_auto_mode_uses_engine_default_and_enforced` | Tests configuration construct  auto mode uses engine default and enforced | Default configuration | functional | P1 |
| `test_construct_config_model_from_request_overrides_default_and_skill` | Tests configuration construct  model from request overrides default and skill | Default configuration | functional | P1 |
| `test_construct_config_prefers_runner_declared_skill_config` | Tests configuration construct  prefers runner declared skill config | Standard scenario | functional | P1 |
| `test_construct_config_interactive_mode_sets_question_allow` | Tests configuration construct  interactive mode sets question allow | Standard scenario | functional | P1 |
| `test_construct_config_enforced_provider_timeout_disables_runtime_override` | Tests timeout for construct config enforced provider  disables runtime override | Timeout scenario | functional | P2 |
| `test_parse_runtime_stream_keeps_latest_step_only` | Tests stream handling for parse runtime  keeps lastep only | Standard scenario | functional | P1 |
| `test_parse_runtime_stream_emits_turn_markers_and_process_events` | Tests stream handling for parse runtime  emits turn markers and process events | Standard scenario | functional | P1 |

**Assessment:** Adequate coverage with 7 test functions.

#### `test_qwen_adapter.py`

- **Test cases:** 5
- **Lines:** 190

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_qwen_config_composer_merges_default_skill_runtime_and_enforced` | Tests configuration qwen  composer merges default skill runtime and enforced | Default configuration | functional | P1 |
| `test_qwen_parse_runtime_stream_detects_oauth_waiting_from_stderr_banner` | Detects qwen parse runtime stream  oauth waiting from stderr banner | Standard scenario | functional | P0 |
| `test_qwen_live_session_remains_stdout_pty_ndjson_only` | Tests session qwen live  remains stdout pty ndjson only | Standard scenario | functional | P2 |
| `test_qwen_parse_runtime_stream_extracts_run_handle_process_events_and_turn_markers` | Tests extraction of qwen parse runtime stream  run handle process events and turn markers | Standard scenario | functional | P1 |
| `test_qwen_live_session_emits_process_events_and_dedupes_final_result_text` | Tests session qwen live  emits process events and dedupes final result text | Standard scenario | functional | P1 |

**Assessment:** Adequate coverage with 5 test functions.

### Category: auth_detection

#### `test_antigravity_local_callback_server.py`

- **Test cases:** 2
- **Lines:** 50

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_antigravity_local_callback_server_success` | Tests antigravity local callback server success | Success scenario | functional | P1 |
| `test_antigravity_local_callback_server_missing_state` | Tests state of antigravity local callback server missing | Missing required field | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_auth_callback_listener_registry.py`

- **Test cases:** 2
- **Lines:** 47

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_callback_listener_registry_start_and_stop` | Tests listing callback ener registry start and stop | Standard scenario | functional | P1 |
| `test_callback_listener_registry_unknown_channel` | Tests listing callback ener registry unknown channel | Standard scenario | functional | P2 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_auth_callback_state_store.py`

- **Test cases:** 3
- **Lines:** 32

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_callback_state_store_register_resolve_consume` | Tests state of callback  store register resolve consume | Standard scenario | functional | P1 |
| `test_callback_state_store_is_channel_scoped` | Tests state of callback  store is channel scoped | Standard scenario | functional | P1 |
| `test_callback_state_store_unregister_keeps_consumed_marker` | Tests state of callback  store unregister keeps consumed marker | Standard scenario | functional | P2 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_auth_detection_audit_persistence.py`

- **Test cases:** 1
- **Lines:** 64

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_write_attempt_audit_artifacts_persists_auth_detection_and_diagnostic` | Tests auth write attempt audit artifacts persists  detection and diagnostic | Standard scenario | functional | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_auth_detection_codex.py`

- **Test cases:** 3
- **Lines:** 71

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_codex_auth_detection_matches_missing_bearer_fixture` | Tests auth codex  detection matches missing bearer fixture | Missing required field | functional | P0 |
| `test_codex_auth_detection_matches_refresh_token_reauth_fixture` | Tests auth codex  detection matches refresh token reauth fixture | Standard scenario | functional | P0 |
| `test_codex_auth_detection_matches_logged_out_access_token_fixture` | Tests auth codex  detection matches logged out access token fixture | Standard scenario | functional | P0 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_auth_detection_gemini.py`

- **Test cases:** 2
- **Lines:** 48

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_gemini_auth_detection_matches_missing_auth_method_fixture` | Tests auth gemini  detection matches missing auth method fixture | Missing required field | functional | P0 |
| `test_gemini_auth_detection_matches_oauth_prompt_diagnostic` | Tests auth gemini  detection matches oauth prompt diagnostic | Standard scenario | functional | P0 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_auth_detection_iflow.py`

- **Test cases:** 1
- **Lines:** 27

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_iflow_auth_detection_matches_oauth_expired_fixture` | Tests auth iflow  detection matches oauth expired fixture | Standard scenario | functional | P0 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_auth_detection_lifecycle_integration.py`

- **Test cases:** 10
- **Lines:** 1026

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_high_confidence_auth_detection_overrides_waiting_user` | Tests auth high confidence  detection overrides waiting user | Override behavior | functional | P0 |
| `test_low_confidence_auth_detection_is_audited_without_forcing_waiting_auth` | Tests auth low confidence  detection is audited without forcing waiting auth | Standard scenario | functional | P1 |
| `test_low_confidence_auth_signal_does_not_translate_terminal_failure_to_auth_required` | Tests failure handling for low confidence auth signal does not translate terminal  to auth required | Failure scenario | functional | P1 |
| `test_high_confidence_auth_detection_with_selection_survives_nonzero_exit` | Tests auth high confidence  detection with selection survives nonzero exit | Standard scenario | functional | P0 |
| `test_opencode_high_confidence_auth_with_null_detection_provider_uses_model_prefix_for_waiting_auth` | Tests auth opencode high confidence  with null detection provider uses model prefix for waiting auth | Standard scenario | functional | P1 |
| `test_codex_refresh_token_reauth_high_confidence_enters_waiting_auth` | Tests auth codex refresh token re high confidence enters waiting auth | Standard scenario | functional | P0 |
| `test_codex_logged_out_access_token_reauth_high_confidence_enters_waiting_auth` | Tests auth codex logged out access token re high confidence enters waiting auth | Standard scenario | functional | P0 |
| `test_qwen_oauth_waiting_banner_enters_waiting_auth_without_protocol_schema_failure` | Tests failure handling for qwen oauth waiting banner enters waiting auth without protocol schema | Failure scenario | contract | P0 |
| `test_claude_not_logged_in_login_prompt_enters_waiting_auth` | Tests auth claude not logged in login prompt enters waiting | Standard scenario | functional | P0 |
| `test_opencode_high_confidence_auth_with_unresolved_model_audits_reason_and_fails` | Tests auth opencode high confidence  with unresolved model audits reason and fails | Standard scenario | functional | P1 |

**Assessment:** Adequate coverage with 10 test functions.

#### `test_auth_detection_opencode.py`

- **Test cases:** 2
- **Lines:** 64

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_opencode_auth_detection_matches_fixture_matrix` | Tests auth opencode  detection matches fixture matrix | Standard scenario | functional | P0 |
| `test_auth_detection_manifest_matrix_stays_in_sync` | Tests auth detection manifest matrix stays in sync | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_auth_detection_rule_loader.py`

- **Test cases:** 7
- **Lines:** 291

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_auth_detection_rule_registry_loads_builtin_adapter_profiles` | Tests loading of auth detection rule registry  builtin adapter profiles | Standard scenario | functional | P1 |
| `test_auth_detection_rule_registry_rejects_duplicate_rule_ids` | Validates rejection of auth detection rule registry  duplicate rule ids | Duplicate operation | functional | P1 |
| `test_runtime_auth_detection_no_longer_reads_legacy_yaml_rule_packs` | Tests auth runtime  detection no longer reads legacy yaml rule packs | Standard scenario | structural | P3 |
| `test_runtime_chain_no_longer_uses_rule_based_detection_service` | Tests detection runtime chain no longer uses rule based ion service | Standard scenario | structural | P3 |
| `test_auth_detection_evidence_must_be_declared_in_profiles_not_parser_core` | Tests auth detection evidence must be declared in profiles not parser core | Standard scenario | functional | P1 |
| `test_auth_detection_profiles_and_common_fallback_are_single_source` | Tests fallback for auth detection profiles and common  are single source | Fallback path | functional | P1 |
| `test_common_fallback_must_not_duplicate_engine_high_patterns` | Tests fallback for common  must not duplicate engine high patterns | Fallback path | functional | P1 |

**Assessment:** Adequate coverage with 7 test functions.

#### `test_auth_driver_registry.py`

- **Test cases:** 2
- **Lines:** 34

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_auth_driver_registry_resolve_and_fallback` | Tests fallback for auth driver registry resolve and | Fallback path | functional | P1 |
| `test_auth_driver_registry_missing_raises` | Tests that exception is raised for auth driver registry missing | Missing required field | functional | P2 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_auth_import_service.py`

- **Test cases:** 9
- **Lines:** 177

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_get_import_spec_gemini_uses_profile_required_files` | Tests port get im spec gemini uses profile required files | Standard scenario | structural | P1 |
| `test_import_auth_files_opencode_openai_accepts_codex_auth_json` | Validates acceptance of import auth files opencode openai  codex auth json | Standard scenario | structural | P1 |
| `test_import_auth_files_gemini_requires_all_required_files` | Tests auth import  files gemini requires all required files | Standard scenario | structural | P1 |
| `test_import_auth_files_opencode_google_requires_google_entry` | Tests auth import  files opencode google requires google entry | Standard scenario | structural | P1 |
| `test_import_auth_files_opencode_replaces_only_selected_provider` | Tests auth import  files opencode replaces only selected provider | Standard scenario | structural | P1 |
| `test_get_import_spec_claude_uses_credentials_json` | Tests port get im spec claude uses credentials json | Standard scenario | structural | P1 |
| `test_get_import_spec_qwen_oauth_uses_oauth_creds_json` | Tests auth get import spec qwen o uses oauth creds json | Standard scenario | structural | P1 |
| `test_get_import_spec_qwen_coding_plan_rejects_import` | Validates rejection of get import spec qwen coding plan  import | Standard scenario | structural | P2 |
| `test_import_auth_files_qwen_oauth_writes_oauth_creds` | Tests auth import  files qwen oauth writes oauth creds | Standard scenario | structural | P1 |

**Assessment:** Adequate coverage with 9 test functions.

#### `test_auth_log_writer.py`

- **Test cases:** 3
- **Lines:** 36

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_auth_log_writer_oauth_proxy_layout` | Tests auth log writer oauth proxy layout | Standard scenario | functional | P1 |
| `test_auth_log_writer_cli_delegate_layout` | Tests auth log writer cli delegate layout | Standard scenario | functional | P1 |
| `test_noop_auth_log_writer_uses_ephemeral_paths_and_cleans_up` | Tests auth noop  log writer uses ephemeral paths and cleans up | Standard scenario | functional | P2 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_auth_session_starter.py`

- **Test cases:** 2
- **Lines:** 128

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_session_starter_codex_oauth_callback` | Tests session starter codex oauth callback | Standard scenario | functional | P0 |
| `test_session_starter_opencode_api_key_waiting_user` | Tests session starter opencode api key waiting user | Standard scenario | functional | P0 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_codex_oauth_proxy_flow.py`

- **Test cases:** 1
- **Lines:** 40

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_codex_oauth_proxy_flow_start_and_submit` | Tests auth codex o proxy flow start and submit | Standard scenario | functional | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_engine_auth_bootstrap.py`

- **Test cases:** 3
- **Lines:** 141

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_engine_auth_bootstrap_builds_bundle` | Tests building of engine auth bootstrap  bundle | Standard scenario | functional | P0 |
| `test_engine_auth_bootstrap_disables_windows_cli_delegate_without_pywinpty` | Tests auth engine  bootstrap disables windows cli delegate without pywinpty | Standard scenario | functional | P1 |
| `test_engine_auth_bootstrap_keeps_windows_cli_delegate_with_pywinpty` | Tests auth engine  bootstrap keeps windows cli delegate with pywinpty | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_engine_auth_driver_contracts.py`

- **Test cases:** 2
- **Lines:** 46

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_auth_driver_context_is_frozen_and_carries_transport_fields` | Tests auth driver context is frozen and carries transport fields | Standard scenario | functional | P1 |
| `test_auth_driver_result_defaults_and_optional_fields` | Tests auth driver result defaults and optional fields | Default configuration | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_engine_auth_driver_matrix_registration.py`

- **Test cases:** 1
- **Lines:** 117

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_driver_matrix_registration_and_method_resolution` | Tests driver matrix registration and method resolution | Standard scenario | functional | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_engine_auth_flow_manager.py`

- **Test cases:** 35
- **Lines:** 1483

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_engine_auth_flow_manager_codex_oauth_proxy_uses_protocol_flow` | Tests auth engine  flow manager codex oauth proxy uses protocol flow | Standard scenario | contract | P1 |
| `test_engine_auth_flow_manager_default_disables_persistent_auth_logs` | Tests auth engine  flow manager default disables persistent auth logs | Default configuration | functional | P2 |
| `test_engine_auth_flow_manager_opt_in_keeps_persistent_auth_logs` | Tests auth engine  flow manager opt in keeps persistent auth logs | Standard scenario | functional | P2 |
| `test_engine_auth_flow_manager_claude_callback_session_injects_run_scope_trust` | Tests session engine auth flow manager claude callback  injects run scope trust | Standard scenario | functional | P2 |
| `test_engine_auth_flow_manager_extract_auth_url_prefers_non_localhost` | Tests auth engine  flow manager extract auth url prefers non localhost | Standard scenario | functional | P2 |
| `test_engine_auth_flow_manager_start_delegates_to_session_starter` | Tests session engine auth flow manager start delegates to  starter | Standard scenario | functional | P2 |
| `test_engine_auth_flow_manager_codex_oauth_proxy_zero_cli` | Tests auth engine  flow manager codex oauth proxy zero cli | Standard scenario | functional | P2 |
| `test_engine_auth_flow_manager_codex_cli_delegate_uses_browser_login` | Tests auth engine  flow manager codex cli delegate uses browser login | Standard scenario | functional | P2 |
| `test_engine_auth_flow_manager_opencode_openai_cli_delegate_callback_shows_input` | Tests auth engine  flow manager opencode openai cli delegate callback shows input | Standard scenario | functional | P2 |
| `test_engine_auth_flow_manager_qwen_oauth_proxy_starts_and_completes` | Tests auth engine  flow manager qwen oauth proxy starts and completes | Standard scenario | functional | P2 |
| `test_engine_auth_flow_manager_qwen_cli_delegate_waits_for_api_key_prompt` | Tests auth engine  flow manager qwen cli delegate waits for api key prompt | Standard scenario | functional | P2 |
| `test_engine_auth_flow_manager_cancel_releases_lock_on_terminate_error` | Tests error handling for engine auth flow manager cancel releases lock on terminate | Error condition | functional | P1 |
| `test_engine_auth_flow_manager_codex_oauth_proxy_respects_configured_callback_base` | Tests auth engine  flow manager codex oauth proxy respects configured callback base | Standard scenario | functional | P2 |
| `test_engine_auth_flow_manager_openai_callback_state_once` | Tests state of engine auth flow manager openai callback  once | Standard scenario | functional | P2 |
| `test_engine_auth_flow_manager_cancel` | Tests cancellation engine auth flow manager | Cancellation request | functional | P1 |
| `test_engine_auth_flow_manager_ttl_expired` | Tests auth engine  flow manager ttl expired | Standard scenario | functional | P2 |
| `test_engine_auth_flow_manager_rejects_unsupported_engine` | Validates rejection of engine auth flow manager  unsupported engine | Standard scenario | functional | P2 |
| `test_engine_auth_flow_manager_gemini_oauth_proxy_uses_protocol_flow` | Tests auth engine  flow manager gemini oauth proxy uses protocol flow | Standard scenario | contract | P1 |
| `test_engine_auth_flow_manager_gemini_oauth_proxy_callback_state_once` | Tests state of engine auth flow manager gemini oauth proxy callback  once | Standard scenario | functional | P2 |
| `test_engine_auth_flow_manager_iflow_oauth_proxy_manual_success` | Tests auth engine  flow manager iflow oauth proxy manual success | Success scenario | functional | P2 |
| `test_engine_auth_flow_manager_iflow_oauth_proxy_callback_state_once` | Tests state of engine auth flow manager iflow oauth proxy callback  once | Standard scenario | functional | P2 |
| `test_engine_auth_flow_manager_respects_global_gate_conflict` | Tests conflict handling for engine auth flow manager respects global gate | Resource conflict | functional | P1 |
| `test_engine_auth_flow_manager_device_proxy_settles_active_before_new_start` | Tests auth engine  flow manager device proxy settles active before new start | Standard scenario | functional | P2 |
| `test_engine_auth_flow_manager_gemini_submit_success` | Tests auth engine  flow manager gemini submit success | Success scenario | functional | P2 |
| `test_engine_auth_flow_manager_gemini_already_authenticated_triggers_reauth` | Tests auth engine  flow manager gemini already authenticated triggers reauth | Standard scenario | functional | P2 |
| `test_engine_auth_flow_manager_iflow_submit_success` | Tests auth engine  flow manager iflow submit success | Success scenario | functional | P2 |
| `test_engine_auth_flow_manager_iflow_rejects_wrong_method` | Validates rejection of engine auth flow manager iflow  wrong method | Standard scenario | functional | P2 |
| `test_engine_auth_flow_manager_opencode_api_key_success` | Tests auth engine  flow manager opencode api key success | Success scenario | functional | P2 |
| `test_engine_auth_flow_manager_opencode_api_key_rejects_cli_delegate` | Validates rejection of engine auth flow manager opencode api key  cli delegate | Standard scenario | functional | P2 |
| `test_engine_auth_flow_manager_opencode_google_cleanup_failure` | Tests failure handling for engine auth flow manager opencode google cleanup | Failure scenario | functional | P1 |
| ... (5 more tests) | See source file | — | — | — |

**Assessment:** Comprehensive coverage with 35 test functions.

#### `test_engine_auth_manager_import_boundary.py`

- **Test cases:** 1
- **Lines:** 9

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_engine_auth_flow_manager_avoids_engine_bootstrap_imports` | Tests auth engine  flow manager avoids engine bootstrap imports | Standard scenario | structural | P2 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_engine_auth_strategy_schema.py`

- **Test cases:** 3
- **Lines:** 67

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_engine_auth_strategy_yaml_matches_schema` | Tests auth engine  strategy yaml matches schema | Standard scenario | contract | P1 |
| `test_engine_auth_strategy_schema_rejects_missing_required_fields` | Validates rejection of engine auth strategy schema  missing required fields | Missing required field | contract | P1 |
| `test_engine_auth_strategy_schema_accepts_session_behavior_extension` | Validates acceptance of engine auth strategy schema  session behavior extension | Standard scenario | contract | P2 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_engine_auth_strategy_service.py`

- **Test cases:** 8
- **Lines:** 144

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_strategy_service_exposes_ui_capabilities_from_policy` | Tests strategy service exposes ui capabilities from policy | Standard scenario | functional | P1 |
| `test_strategy_service_exposes_high_risk_capabilities_from_policy` | Tests strategy service exposes high risk capabilities from policy | Standard scenario | functional | P1 |
| `test_strategy_service_high_risk_helpers_resolve_runtime_and_conversation_methods` | Tests strategy service high risk helpers resolve runtime and conversation methods | Standard scenario | functional | P1 |
| `test_strategy_service_supports_start_requires_explicit_provider_for_opencode` | Tests port strategy service sups start requires explicit provider for opencode | Standard scenario | functional | P1 |
| `test_strategy_service_opencode_conversation_methods_use_provider_scope` | Tests strategy service opencode conversation methods use provider scope | Standard scenario | functional | P1 |
| `test_strategy_service_qwen_conversation_methods_use_provider_scope` | Tests strategy service qwen conversation methods use provider scope | Standard scenario | functional | P1 |
| `test_strategy_service_runtime_session_behavior_defaults_and_qwen_override` | Tests session strategy service runtime  behavior defaults and qwen override | Default configuration | functional | P1 |
| `test_strategy_service_raises_for_invalid_payload` | Tests that exception is raised for strategy service  for invalid payload | Invalid input | functional | P2 |

**Assessment:** Adequate coverage with 8 test functions.

#### `test_engine_interaction_gate.py`

- **Test cases:** 2
- **Lines:** 20

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_engine_interaction_gate_allows_single_active_session` | Tests session engine interaction gate allows single active | Standard scenario | functional | P1 |
| `test_engine_interaction_gate_rejects_conflicting_scope` | Validates rejection of engine interaction gate  conflicting scope | Resource conflict | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_gemini_local_callback_server.py`

- **Test cases:** 2
- **Lines:** 48

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_gemini_local_callback_server_success` | Tests gemini local callback server success | Success scenario | functional | P1 |
| `test_gemini_local_callback_server_missing_state` | Tests state of gemini local callback server missing | Missing required field | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_gemini_oauth_proxy_flow.py`

- **Test cases:** 3
- **Lines:** 94

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_gemini_oauth_proxy_flow_start_session` | Tests session gemini oauth proxy flow start | Standard scenario | functional | P2 |
| `test_gemini_oauth_proxy_flow_submit_input_writes_oauth_files` | Tests auth gemini o proxy flow submit input writes oauth files | Standard scenario | functional | P2 |
| `test_gemini_oauth_proxy_flow_rejects_state_mismatch` | Validates rejection of gemini oauth proxy flow  state mismatch | Standard scenario | functional | P2 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_iflow_local_callback_server.py`

- **Test cases:** 2
- **Lines:** 48

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_iflow_local_callback_server_success` | Tests iflow local callback server success | Success scenario | functional | P1 |
| `test_iflow_local_callback_server_missing_state` | Tests state of iflow local callback server missing | Missing required field | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_iflow_oauth_proxy_flow.py`

- **Test cases:** 3
- **Lines:** 87

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_iflow_oauth_proxy_flow_start_session` | Tests session iflow oauth proxy flow start | Standard scenario | functional | P2 |
| `test_iflow_oauth_proxy_flow_submit_input_writes_iflow_files` | Tests auth iflow o proxy flow submit input writes iflow files | Standard scenario | functional | P2 |
| `test_iflow_oauth_proxy_flow_rejects_state_mismatch` | Validates rejection of iflow oauth proxy flow  state mismatch | Standard scenario | functional | P2 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_oauth_openai_callback_routes.py`

- **Test cases:** 2
- **Lines:** 63

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_openai_callback_route_success` | Tests route openai callback  success | Success scenario | functional | P1 |
| `test_openai_callback_route_replay` | Tests route openai callback  replay | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_oauth_proxy_orchestrator.py`

- **Test cases:** 3
- **Lines:** 97

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_oauth_proxy_orchestrator_start_and_get` | Tests auth o proxy orchestrator start and get | Standard scenario | functional | P1 |
| `test_oauth_proxy_orchestrator_gemini_maps_to_auth` | Tests auth o proxy orchestrator gemini maps to auth | Standard scenario | functional | P1 |
| `test_oauth_proxy_orchestrator_iflow_maps_to_auth` | Tests auth o proxy orchestrator iflow maps to auth | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_openai_device_proxy_flow.py`

- **Test cases:** 2
- **Lines:** 98

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_openai_device_proxy_flow_start_session` | Tests session openai device proxy flow start | Standard scenario | functional | P1 |
| `test_openai_device_proxy_flow_poll_once_completes` | Tests openai device proxy flow poll once completes | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_openai_local_callback_server.py`

- **Test cases:** 3
- **Lines:** 67

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_openai_local_callback_server_success` | Tests openai local callback server success | Success scenario | functional | P2 |
| `test_openai_local_callback_server_missing_state` | Tests state of openai local callback server missing | Missing required field | functional | P1 |
| `test_openai_local_callback_server_callback_error` | Tests error handling for openai local callback server callback | Error condition | functional | P1 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_qwen_oauth_proxy_flow.py`

- **Test cases:** 10
- **Lines:** 356

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_qwen_oauth_proxy_flow_start_session_uses_pkce` | Tests session qwen oauth proxy flow start  uses pkce | Standard scenario | functional | P2 |
| `test_qwen_oauth_proxy_flow_start_session_reports_empty_body` | Tests session qwen oauth proxy flow start  reports empty body | Empty input | functional | P2 |
| `test_qwen_oauth_proxy_flow_start_session_reports_waf_block` | Tests session qwen oauth proxy flow start  reports waf block | Standard scenario | functional | P2 |
| `test_qwen_oauth_proxy_flow_start_session_wraps_url_error` | Tests error handling for qwen oauth proxy flow start session wraps url | Error condition | functional | P1 |
| `test_qwen_oauth_proxy_flow_poll_once_sends_code_verifier` | Tests auth qwen o proxy flow poll once sends code verifier | Standard scenario | functional | P2 |
| `test_qwen_oauth_proxy_flow_poll_once_handles_authorization_pending` | Tests handling of qwen oauth proxy flow poll once  authorization pending | Standard scenario | functional | P2 |
| `test_qwen_oauth_proxy_flow_poll_once_handles_slow_down_http_429` | Tests handling of qwen oauth proxy flow poll once  slow down http 429 | Standard scenario | functional | P2 |
| `test_qwen_oauth_proxy_flow_poll_once_rejects_success_without_access_token` | Validates rejection of qwen oauth proxy flow poll once  success without access token | Success scenario | functional | P2 |
| `test_qwen_oauth_proxy_flow_poll_once_persists_resource_url` | Tests auth qwen o proxy flow poll once persists resource url | Standard scenario | functional | P2 |
| `test_qwen_oauth_proxy_flow_poll_once_wraps_url_error` | Tests error handling for qwen oauth proxy flow poll once wraps url | Error condition | functional | P1 |

**Assessment:** Adequate coverage with 10 test functions.

### Category: cli/harness

#### `test_agent_cli_manager.py`

- **Test cases:** 28
- **Lines:** 610

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_ensure_layout_creates_default_config_files` | Tests creation of ensure layout  default config files | Default configuration | functional | P0 |
| `test_default_bootstrap_engines_come_from_global_config` | Tests configuration default bootstrap engines come from global | Default configuration | functional | P1 |
| `test_default_bootstrap_engines_respect_config_override` | Tests configuration default bootstrap engines respect  override | Default configuration | functional | P1 |
| `test_collect_claude_sandbox_status_reports_missing_dependencies` | Tests port collect claude sandbox status res missing dependencies | Missing required field | functional | P1 |
| `test_collect_codex_sandbox_status_reports_disabled_by_env` | Tests port collect codex sandbox status res disabled by env | Standard scenario | functional | P1 |
| `test_collect_codex_sandbox_status_reports_missing_bubblewrap_dependency` | Tests port collect codex sandbox status res missing bubblewrap dependency | Missing required field | functional | P1 |
| `test_collect_codex_sandbox_status_reports_runtime_unavailable_when_probe_fails` | Tests port collect codex sandbox status res runtime unavailable when probe fails | Standard scenario | functional | P1 |
| `test_collect_codex_sandbox_status_reports_available_when_smoke_probe_succeeds` | Tests port collect codex sandbox status res available when smoke probe succeeds | Standard scenario | functional | P1 |
| `test_collect_claude_sandbox_status_reports_available_when_smoke_probe_succeeds` | Tests port collect claude sandbox status res available when smoke probe succeeds | Standard scenario | functional | P1 |
| `test_collect_claude_sandbox_status_reports_runtime_unavailable_when_probe_fails` | Tests port collect claude sandbox status res runtime unavailable when probe fails | Standard scenario | functional | P1 |
| `test_ensure_layout_persists_claude_sandbox_probe_sidecar` | Tests probe ensure layout persists claude sandbox  sidecar | Standard scenario | functional | P1 |
| `test_ensure_layout_persists_codex_sandbox_probe_sidecar` | Tests probe ensure layout persists codex sandbox  sidecar | Standard scenario | functional | P1 |
| `test_import_credentials_whitelist_only` | Tests port im credentials whitelist only | Standard scenario | structural | P1 |
| `test_ensure_layout_migrates_legacy_iflow_settings` | Tests settings ensure layout migrates legacy iflow | Standard scenario | regression | P2 |
| `test_ensure_installed_uses_managed_presence_only` | Tests installation ensure ed uses managed presence only | Standard scenario | functional | P1 |
| `test_collect_auth_status_reports_global_fallback` | Tests fallback for collect auth status reports global | Fallback path | functional | P1 |
| `test_collect_auth_status_opencode_ready_requires_auth_json_only` | Tests auth collect  status opencode ready requires auth json only | Standard scenario | functional | P1 |
| `test_probe_resume_capability_success_and_profile_mapping` | Tests probe resume capability success and profile mapping | Success scenario | property | P1 |
| `test_probe_resume_capability_failure_keeps_resumable_profile` | Tests failure handling for probe resume capability  keeps resumable profile | Failure scenario | functional | P1 |
| `test_read_version_extracts_semver_from_prefixed_output` | Tests extraction of read version  semver from prefixed output | Standard scenario | functional | P2 |
| `test_read_version_returns_none_on_oserror` | Tests return value for read version  none on oserror | Error condition | functional | P2 |
| `test_resolve_managed_engine_command_prefers_windows_cmd` | Tests resolve managed engine command prefers windows cmd | Standard scenario | functional | P1 |
| `test_resolve_ttyd_command_prefers_windows_wrappers` | Tests resolve ttyd command prefers windows wrappers | Standard scenario | functional | P2 |
| `test_run_command_returns_failure_on_oserror` | Tests return value for run command  failure on oserror | Error condition | functional | P2 |
| `test_install_package_prefers_windows_npm_cmd` | Tests installation package prefers windows npm cmd | Standard scenario | functional | P2 |
| `test_resolve_npm_command_prefers_explicit_env_override_on_windows` | Tests resolve npm command prefers explicit env override on windows | Override behavior | functional | P2 |
| `test_install_package_returns_failure_on_oserror` | Tests return value for install package  failure on oserror | Error condition | functional | P2 |
| `test_import_credentials_uses_profile_rules_for_all_engines` | Tests port im credentials uses profile rules for all engines | Standard scenario | structural | P1 |

**Assessment:** Comprehensive coverage with 28 test functions.

#### `test_agent_harness_cli.py`

- **Test cases:** 7
- **Lines:** 315

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_cli_start_forwards_passthrough_without_translate` | Tests cli start forwards passthrough without translate | Standard scenario | functional | P2 |
| `test_cli_resume_joins_message_tokens` | Tests cli resume joins message tokens | Standard scenario | functional | P2 |
| `test_cli_direct_engine_syntax_forwards_passthrough` | Tests cli direct engine syntax forwards passthrough | Standard scenario | functional | P2 |
| `test_cli_direct_claude_syntax_forwards_passthrough` | Tests cli direct claude syntax forwards passthrough | Standard scenario | functional | P2 |
| `test_cli_claude_start_forwards_custom_model` | Tests model cli claude start forwards custom | Standard scenario | functional | P2 |
| `test_cli_direct_engine_without_passthrough_is_valid` | Tests cli direct engine without passthrough is valid | Standard scenario | functional | P2 |
| `test_cli_start_auto_flag_switches_to_auto_mode` | Tests auto mode cli start  flag switches to auto mode | Standard scenario | functional | P2 |

**Assessment:** Adequate coverage with 7 test functions.

#### `test_agent_harness_config.py`

- **Test cases:** 2
- **Lines:** 28

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_config_defaults_run_root_under_data_dir` | Tests configuration defaults run root under data dir | Default configuration | functional | P2 |
| `test_config_harness_run_root_env_override` | Tests configuration harness run root env override | Override behavior | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_agent_harness_container_wrapper.py`

- **Test cases:** 2
- **Lines:** 108

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_agent_harness_container_wrapper_uses_non_tty_exec_and_forwards_args_and_stdin` | Tests agent harness container wrapper uses non tty exec and forwards args and stdin | Standard scenario | functional | P1 |
| `test_agent_harness_container_wrapper_fails_when_api_is_not_running` | Tests agent harness container wrapper fails when api is not running | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_agent_harness_runtime.py`

- **Test cases:** 20
- **Lines:** 805

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_start_passthrough_translate_and_attempt_artifacts` | Tests start passthrough translate and attempt artifacts | Standard scenario | functional | P2 |
| `test_harness_registers_and_cleans_trust_for_codex` | Tests registration of harness  and cleans trust for codex | Standard scenario | functional | P2 |
| `test_harness_registers_trust_for_claude_and_bootstraps_git` | Tests registration of harness  trust for claude and bootstraps git | Standard scenario | functional | P2 |
| `test_harness_does_not_register_trust_for_iflow` | Tests trust harness does not register  for iflow | Standard scenario | functional | P2 |
| `test_run_selector_reuse_increments_attempt` | Tests run selector reuse increments attempt | Standard scenario | functional | P2 |
| `test_resume_uses_handle_and_inherits_translate_level` | Tests resume uses handle and inherits translate level | Standard scenario | functional | P2 |
| `test_harness_injects_project_and_fixture_skills` | Tests harness injects project and fixture skills | Standard scenario | functional | P2 |
| `test_resume_inherits_auto_mode_from_handle_metadata` | Tests auto mode resume inherits  mode from handle metadata | Standard scenario | functional | P2 |
| `test_resume_fallbacks_to_interactive_when_handle_mode_missing` | Tests fallback for resume s to interactive when handle mode missing | Missing required field | functional | P1 |
| `test_opencode_start_is_supported` | Tests port opencode start is suped | Standard scenario | functional | P2 |
| `test_claude_start_is_supported_without_codex_specific_injection` | Tests port claude start is suped without codex specific injection | Standard scenario | functional | P2 |
| `test_claude_start_accepts_custom_model` | Validates acceptance of claude start  custom model | Standard scenario | functional | P2 |
| `test_custom_model_rejected_for_non_claude_engine` | Tests model custom  rejected for non claude engine | Standard scenario | functional | P2 |
| `test_claude_resume_is_supported` | Tests port claude resume is suped | Standard scenario | functional | P2 |
| `test_engine_config_injection_failure_is_structured_error` | Tests error handling for engine config injection failure is structured | Error condition | structural | P1 |
| `test_conformance_report_contains_required_summary` | Tests port conformance re contains required summary | Standard scenario | functional | P2 |
| `test_translate_level3_waiting_user_suppresses_default_english_prompt` | Tests default translate level3 waiting user suppresses  english prompt | Default configuration | functional | P2 |
| `test_runtime_markers_wrap_translate_output_once` | Tests output runtime markers wrap translate  once | Standard scenario | functional | P2 |
| `test_run_command_requires_script_binary` | Tests run command requires script binary | Standard scenario | functional | P2 |
| `test_run_command_with_log_out_does_not_append_dev_null` | Tests run command with log out does not append dev null | Standard scenario | functional | P2 |

**Assessment:** Comprehensive coverage with 20 test functions.

#### `test_agent_manager_bootstrap.py`

- **Test cases:** 4
- **Lines:** 159

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_summarize_output_masks_sensitive_values` | Tests output summarize  masks sensitive values | Standard scenario | functional | P2 |
| `test_ensure_with_diagnostics_reports_partial_failure` | Tests failure handling for ensure with diagnostics reports partial | Failure scenario | functional | P1 |
| `test_ensure_with_diagnostics_honors_explicit_engine_subset` | Tests ensure with diagnostics honors explicit engine subset | Standard scenario | functional | P2 |
| `test_ensure_with_diagnostics_opencode_warmup_failure_is_warning_only` | Tests failure handling for ensure with diagnostics opencode warmup  is warning only | Failure scenario | functional | P1 |

**Assessment:** Adequate coverage with 4 test functions.

#### `test_cli_delegate_orchestrator.py`

- **Test cases:** 1
- **Lines:** 66

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_cli_delegate_orchestrator_start` | Tests cli delegate orchestrator start | Standard scenario | functional | P1 |

**Assessment:** Sparse coverage with 1 test function.

### Category: config/settings

#### `test_claude_config_composer.py`

- **Test cases:** 5
- **Lines:** 290

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_claude_config_composer_writes_headless_run_settings_with_run_local_sandbox` | Tests configuration claude  composer writes headless run settings with run local sandbox | Standard scenario | functional | P2 |
| `test_claude_config_composer_enables_1m_context_for_official_models` | Tests configuration claude  composer enables 1m context for official models | Standard scenario | functional | P2 |
| `test_claude_config_composer_custom_provider_1m_mode_uses_root_model_and_default_sonnet` | Tests configuration claude  composer custom provider 1m mode uses root model and default sonnet | Default configuration | functional | P2 |
| `test_claude_config_composer_merges_runtime_sandbox_allowwrite_with_headless_defaults` | Tests configuration claude  composer merges runtime sandbox allowwrite with headless defaults | Default configuration | functional | P2 |
| `test_claude_config_composer_disables_headless_sandbox_when_bootstrap_probe_unavailable` | Tests configuration claude  composer disables headless sandbox when bootstrap probe unavailable | Standard scenario | functional | P2 |

**Assessment:** Adequate coverage with 5 test functions.

#### `test_claude_custom_providers.py`

- **Test cases:** 5
- **Lines:** 100

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_claude_custom_provider_store_upsert_list_resolve_and_delete` | Tests store claude custom provider  upsert list resolve and delete | Standard scenario | functional | P2 |
| `test_claude_custom_provider_store_repairs_invalid_json` | Tests store claude custom provider  repairs invalid json | Invalid input | functional | P1 |
| `test_claude_custom_provider_store_resolves_explicit_1m_variant_and_returns_base_model` | Tests return value for claude custom provider store resolves explicit 1m variant and  base model | Standard scenario | functional | P2 |
| `test_claude_custom_provider_store_allows_1m_request_to_match_legacy_base_model` | Tests model claude custom provider store allows 1m request to match legacy base | Standard scenario | regression | P2 |
| `test_claude_custom_provider_store_does_not_match_base_request_to_1m_only_model` | Tests model claude custom provider store does not match base request to 1m only | Standard scenario | functional | P2 |

**Assessment:** Adequate coverage with 5 test functions.

#### `test_codex_config.py`

- **Test cases:** 4
- **Lines:** 76

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_ensure_config_exists` | Tests configuration ensure  exists | Standard scenario | functional | P2 |
| `test_update_profile_creates_new_profile` | Tests creation of update profile  new profile | Standard scenario | functional | P2 |
| `test_update_profile_preserves_comments` | Tests update profile preserves comments | Standard scenario | functional | P2 |
| `test_update_profile_writes_enforced_global_settings` | Tests settings update profile writes enforced global | Standard scenario | functional | P2 |

**Assessment:** Adequate coverage with 4 test functions.

#### `test_codex_config_fusion.py`

- **Test cases:** 6
- **Lines:** 175

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_fusion_precedence` | Tests fusion precedence | Standard scenario | functional | P2 |
| `test_deep_merge_behavior` | Tests merge of deep  behavior | Standard scenario | functional | P1 |
| `test_validation_failure` | Tests failure handling for validation | Failure scenario | functional | P1 |
| `test_custom_profile_falls_back_to_default_enforced_section` | Tests default custom profile falls back to  enforced section | Default configuration | functional | P2 |
| `test_engine_default_used_when_skill_and_runtime_missing` | Tests default engine  used when skill and runtime missing | Missing required field | functional | P1 |
| `test_extract_enforced_global_settings_from_top_level_tables` | Tests settings extract enforced global  from top level tables | Standard scenario | functional | P2 |

**Assessment:** Adequate coverage with 6 test functions.

#### `test_command_defaults.py`

- **Test cases:** 2
- **Lines:** 24

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_merge_cli_args_explicit_overrides_default_option_value` | Tests default merge cli args explicit overrides  option value | Default configuration | functional | P2 |
| `test_merge_cli_args_explicit_overrides_equals_style_option` | Tests merge of cli args explicit overrides equals style option | Override behavior | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_config.py`

- **Test cases:** 3
- **Lines:** 28

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_default_config_loading` | Tests configuration default  loading | Default configuration | functional | P1 |
| `test_config_singleton` | Tests configuration singleton | Standard scenario | functional | P1 |
| `test_path_resolution` | Tests path resolution | Standard scenario | functional | P2 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_config_contract_governance_guards.py`

- **Test cases:** 2
- **Lines:** 64

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_no_legacy_config_or_contract_path_references` | Tests configuration no legacy  or contract path references | Contract verification | structural | P0 |
| `test_server_code_reads_contracts_via_registry_layer` | Tests server code reads contracts via registry layer | Contract verification | contract | P0 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_config_generator.py`

- **Test cases:** 3
- **Lines:** 102

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_unknown_config_key_logs_warning` | Tests configuration unknown  key logs warning | Standard scenario | functional | P2 |
| `test_json_schema_config_accepts_claude_env_without_unknown_key_warning` | Validates acceptance of json schema config  claude env without unknown key warning | Standard scenario | contract | P2 |
| `test_json_schema_config_rejects_invalid_claude_permission_mode` | Validates rejection of json schema config  invalid claude permission mode | Invalid input | contract | P1 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_options_policy.py`

- **Test cases:** 14
- **Lines:** 114

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_unknown_runtime_options_rejected` | Tests unknown runtime options rejected | Standard scenario | functional | P2 |
| `test_runtime_no_cache_allowed` | Tests caching runtime no  allowed | Standard scenario | structural | P2 |
| `test_runtime_debug_rejected` | Tests runtime debug rejected | Standard scenario | functional | P2 |
| `test_runtime_debug_keep_temp_rejected` | Tests runtime debug keep temp rejected | Standard scenario | functional | P2 |
| `test_runtime_execution_mode_interactive_allowed` | Tests runtime execution mode interactive allowed | Standard scenario | functional | P2 |
| `test_runtime_interactive_auto_reply_allowed` | Tests reply handling runtime interactive auto  allowed | Standard scenario | functional | P2 |
| `test_runtime_execution_mode_invalid_rejected` | Tests runtime execution mode invalid rejected | Invalid input | functional | P1 |
| `test_interactive_reply_timeout_override_allowed` | Tests timeout for interactive reply  override allowed | Timeout scenario | functional | P1 |
| `test_legacy_timeout_key_rejected` | Tests timeout for legacy  key rejected | Timeout scenario | regression | P1 |
| `test_legacy_interactive_policy_key_rejected` | Tests key legacy interactive policy  rejected | Standard scenario | regression | P2 |
| `test_interactive_reply_timeout_zero_allowed` | Tests timeout for interactive reply  zero allowed | Timeout scenario | functional | P1 |
| `test_interactive_auto_reply_must_be_boolean` | Tests reply handling interactive auto  must be boolean | Standard scenario | functional | P2 |
| `test_hard_timeout_seconds_allowed` | Tests timeout for hard  seconds allowed | Timeout scenario | functional | P1 |
| `test_hard_timeout_seconds_must_be_positive_integer` | Tests timeout for hard  seconds must be positive integer | Timeout scenario | functional | P1 |

**Assessment:** Comprehensive coverage with 14 test functions.

#### `test_system_log_explorer_service.py`

- **Test cases:** 3
- **Lines:** 103

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_query_system_logs_filters_level_and_keyword` | Tests filtering query system logs s level and keyword | Standard scenario | functional | P2 |
| `test_query_bootstrap_logs_applies_time_filter` | Tests filtering query bootstrap logs applies time | Standard scenario | functional | P2 |
| `test_query_logs_rejects_unknown_source` | Validates rejection of query logs  unknown source | Standard scenario | functional | P2 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_system_settings_service.py`

- **Test cases:** 3
- **Lines:** 114

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_system_settings_service_bootstraps_missing_file` | Tests settings system  service bootstraps missing file | Missing required field | functional | P1 |
| `test_system_settings_service_updates_logging_settings_atomically` | Tests update of system settings service  logging settings atomically | Standard scenario | functional | P2 |
| `test_system_settings_service_rejects_invalid_logging_payload` | Validates rejection of system settings service  invalid logging payload | Invalid input | functional | P1 |

**Assessment:** Minimal coverage with 3 test functions.

### Category: engine_management

#### `test_engine_adapter_component_wiring.py`

- **Test cases:** 1
- **Lines:** 22

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_engine_execution_adapter_component_wiring` | Tests engine execution adapter component wiring | Standard scenario | functional | P3 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_engine_adapter_entrypoints.py`

- **Test cases:** 1
- **Lines:** 30

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_engine_execution_adapters_build_directly` | Tests engine execution adapters build directly | Standard scenario | functional | P3 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_engine_adapter_registry.py`

- **Test cases:** 3
- **Lines:** 61

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_registry_exposes_all_supported_adapters` | Tests port registry exposes all suped adapters | Standard scenario | functional | P1 |
| `test_registry_require_raises_for_unknown_engine` | Tests that exception is raised for registry require  for unknown engine | Standard scenario | functional | P2 |
| `test_opencode_adapter_builds_start_and_parses_stream` | Tests parsing of opencode adapter builds start and  stream | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_engine_package_bootstrap.py`

- **Test cases:** 2
- **Lines:** 23

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_engine_package_execution_adapters` | Tests engine package execution adapters | Standard scenario | functional | P3 |
| `test_opencode_auth_registry_reexport_is_available` | Tests auth opencode  registry reexport is available | Standard scenario | structural | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_engine_shell_capability_provider.py`

- **Test cases:** 1
- **Lines:** 27

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_engine_shell_capability_provider_uses_adapter_profile_ui_shell_metadata` | Tests engine shell capability provider uses adapter profile ui shell metadata | Standard scenario | regression | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_engine_status_cache_service.py`

- **Test cases:** 5
- **Lines:** 108

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_engine_status_cache_service_refresh_all_writes_cache` | Tests caching engine status  service refresh all writes cache | Standard scenario | functional | P1 |
| `test_engine_status_cache_service_refresh_engine_merges_existing_cache` | Tests caching engine status  service refresh engine merges existing cache | Standard scenario | functional | P1 |
| `test_engine_status_cache_service_invalid_cache_degrades_to_empty_snapshot` | Tests caching engine status  service invalid cache degrades to empty snapshot | Invalid input | functional | P2 |
| `test_engine_status_cache_service_migrates_legacy_file_when_db_empty` | Tests caching engine status  service migrates legacy file when db empty | Empty input | regression | P2 |
| `test_engine_status_cache_service_start_stop_scheduler` | Tests caching engine status  service start stop scheduler | Standard scenario | functional | P2 |

**Assessment:** Adequate coverage with 5 test functions.

#### `test_engine_upgrade_manager.py`

- **Test cases:** 6
- **Lines:** 108

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_create_task_rejects_invalid_payload` | Validates rejection of create task  invalid payload | Invalid input | functional | P1 |
| `test_create_task_rejects_when_busy` | Validates rejection of create task  when busy | Standard scenario | functional | P1 |
| `test_run_task_single_success` | Tests run task single success | Success scenario | functional | P1 |
| `test_run_task_all_with_failure` | Tests failure handling for run task all with | Failure scenario | functional | P1 |
| `test_single_engine_action_uses_install_when_managed_missing` | Tests installation single engine action uses  when managed missing | Missing required field | functional | P2 |
| `test_single_engine_action_uses_upgrade_when_managed_present` | Tests upgrade single engine action uses  when managed present | Standard scenario | functional | P2 |

**Assessment:** Adequate coverage with 6 test functions.

#### `test_engine_upgrade_store.py`

- **Test cases:** 1
- **Lines:** 24

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_engine_upgrade_store_create_update_get` | Tests update engine upgrade store create  get | Standard scenario | functional | P1 |

**Assessment:** Sparse coverage with 1 test function.

### Category: misc/structural

#### `test_engines_common_openai_ssot.py`

- **Test cases:** 1
- **Lines:** 33

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_engines_common_openai_auth_has_no_services_dependency` | Tests auth engines common openai  has no services dependency | Standard scenario | structural | P2 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_gemini_auth_cli_flow.py`

- **Test cases:** 13
- **Lines:** 386

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_extract_auth_url_multiline_compaction` | Tests auth extract  url multiline compaction | Standard scenario | functional | P2 |
| `test_start_session_uses_shared_pty_runtime` | Tests session start  uses shared pty runtime | Standard scenario | functional | P2 |
| `test_consume_output_state_transitions` | Tests state of consume output  transitions | Standard scenario | functional | P2 |
| `test_consume_output_menu_checked_api_key_switches_to_google` | Tests key consume output menu checked api  switches to google | Standard scenario | functional | P2 |
| `test_consume_output_api_key_prompt_sends_escape` | Tests key consume output api  prompt sends escape | Standard scenario | functional | P2 |
| `test_consume_output_reauth_waits_and_sends_single_confirm_enter` | Tests auth consume output re waits and sends single confirm enter | Standard scenario | functional | P2 |
| `test_consume_output_reauth_triggers_only_after_main_ui_anchor` | Tests auth consume output re triggers only after main ui anchor | Standard scenario | functional | P2 |
| `test_consume_output_menu_navigation_fallback_submits_enter` | Tests fallback for consume output menu navigation  submits enter | Fallback path | functional | P2 |
| `test_consume_output_trust_prompt_auto_enter` | Tests trust consume output  prompt auto enter | Standard scenario | functional | P2 |
| `test_consume_output_main_ui_alt_anchor_does_not_trigger_reauth` | Tests auth consume output main ui alt anchor does not trigger re | Standard scenario | functional | P2 |
| `test_submit_code_requires_waiting_state` | Tests state of submit code requires waiting | Standard scenario | functional | P2 |
| `test_consume_output_code_prompt_blocks_further_auto_input` | Tests auto mode consume output code prompt blocks further  input | Standard scenario | functional | P2 |
| `test_consume_output_direct_url_stage_short_circuits_automation` | Tests auto mode consume output direct url stage short circuits mation | Standard scenario | functional | P2 |

**Assessment:** Comprehensive coverage with 13 test functions.

#### `test_iflow_auth_cli_flow.py`

- **Test cases:** 8
- **Lines:** 301

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_extract_auth_url_multiline_compaction` | Tests auth extract  url multiline compaction | Standard scenario | functional | P2 |
| `test_start_session_uses_shared_pty_runtime` | Tests session start  uses shared pty runtime | Standard scenario | functional | P2 |
| `test_menu_checked_option_correction_and_confirm` | Tests menu checked option correction and confirm | Standard scenario | functional | P2 |
| `test_oauth_submit_model_confirm_and_success` | Tests auth o submit model confirm and success | Success scenario | functional | P2 |
| `test_oauth_url_refresh_resets_submitted_state_and_requires_retry` | Tests state of oauth url refresh resets submitted  and requires retry | Standard scenario | functional | P2 |
| `test_oauth_submit_timeout_falls_back_to_waiting_user` | Tests timeout for oauth submit  falls back to waiting user | Timeout scenario | functional | P1 |
| `test_oauth_submit_stalled_sends_single_extra_enter` | Tests auth o submit stalled sends single extra enter | Standard scenario | functional | P2 |
| `test_main_ui_triggers_auth_command_once` | Tests auth main ui triggers  command once | Standard scenario | functional | P2 |

**Assessment:** Adequate coverage with 8 test functions.

#### `test_management_log_range_attempt.py`

- **Test cases:** 1
- **Lines:** 42

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_management_logs_range_forwards_attempt` | Tests range management logs  forwards attempt | Standard scenario | functional | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_opencode_auth_cli_flow.py`

- **Test cases:** 9
- **Lines:** 219

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_opencode_auth_cli_flow_extract_menu_options` | Tests auth opencode  cli flow extract menu options | Standard scenario | functional | P2 |
| `test_opencode_auth_cli_flow_extract_auth_url` | Tests auth opencode  cli flow extract auth url | Standard scenario | functional | P2 |
| `test_opencode_auth_cli_flow_extract_auth_url_ignores_guidance_text` | Tests auth opencode  cli flow extract auth url ignores guidance text | Standard scenario | functional | P2 |
| `test_opencode_auth_cli_flow_extract_generic_openai_go_to_url` | Tests auth opencode  cli flow extract generic openai go to url | Standard scenario | functional | P2 |
| `test_opencode_auth_cli_flow_success_anchor` | Tests auth opencode  cli flow success anchor | Success scenario | functional | P2 |
| `test_opencode_auth_cli_flow_openai_waiting_anchor_without_url` | Tests auth opencode  cli flow openai waiting anchor without url | Standard scenario | functional | P2 |
| `test_opencode_auth_cli_flow_google_redirect_prompt_after_submit_allows_success` | Tests auth opencode  cli flow google redirect prompt after submit allows success | Success scenario | functional | P2 |
| `test_opencode_auth_cli_flow_google_auto_decline_add_another_account` | Tests auth opencode  cli flow google auto decline add another account | Standard scenario | functional | P2 |
| `test_start_session_uses_shared_pty_runtime` | Tests session start  uses shared pty runtime | Standard scenario | functional | P2 |

**Assessment:** Adequate coverage with 9 test functions.

#### `test_opencode_auth_store.py`

- **Test cases:** 3
- **Lines:** 62

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_opencode_auth_store_upsert_api_key` | Tests auth opencode  store upsert api key | Standard scenario | functional | P2 |
| `test_opencode_auth_store_clear_antigravity_accounts` | Tests auth opencode  store clear antigravity accounts | Standard scenario | functional | P2 |
| `test_opencode_auth_store_backup_and_restore` | Tests auth opencode  store backup and restore | Standard scenario | functional | P2 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_opencode_google_antigravity_oauth_proxy_flow.py`

- **Test cases:** 3
- **Lines:** 107

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_opencode_google_antigravity_oauth_proxy_start_session` | Tests session opencode google antigravity oauth proxy start | Standard scenario | functional | P2 |
| `test_opencode_google_antigravity_oauth_proxy_submit_input_full_callback_url` | Tests auth opencode google antigravity o proxy submit input full callback url | Standard scenario | functional | P2 |
| `test_opencode_google_antigravity_oauth_proxy_submit_input_rejects_state_mismatch` | Validates rejection of opencode google antigravity oauth proxy submit input  state mismatch | Standard scenario | functional | P2 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_opencode_model_catalog_service.py`

- **Test cases:** 3
- **Lines:** 129

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_probe_timeout_uses_unified_timeout` | Tests timeout for probe  uses unified timeout | Timeout scenario | functional | P1 |
| `test_parse_verbose_models_extracts_provider_model_and_supported_effort` | Tests extraction of parse verbose models  provider model and supported effort | Standard scenario | functional | P2 |
| `test_parse_verbose_models_accepts_label_plus_json_blocks` | Validates acceptance of parse verbose models  label plus json blocks | Standard scenario | functional | P2 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_opencode_model_catalog_startup.py`

- **Test cases:** 1
- **Lines:** 82

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_lifespan_requests_opencode_model_refresh_async_when_enabled` | Tests async boundary lifespan requests opencode model refresh  when enabled | Standard scenario | functional | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_opencode_openai_oauth_proxy_flow.py`

- **Test cases:** 1
- **Lines:** 41

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_opencode_openai_oauth_proxy_flow_start_and_submit` | Tests auth opencode openai o proxy flow start and submit | Standard scenario | functional | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_qwen_auth_cli_delegate_flow.py`

- **Test cases:** 3
- **Lines:** 90

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_qwen_cli_delegate_flow_extracts_qwen_oauth_url` | Tests extraction of qwen cli delegate flow  qwen oauth url | Standard scenario | functional | P2 |
| `test_qwen_cli_delegate_flow_coding_plan_region_and_api_key_prompt` | Tests key qwen cli delegate flow coding plan region and api  prompt | Standard scenario | functional | P2 |
| `test_qwen_cli_delegate_flow_refresh_marks_success_after_exit` | Tests refresh qwen cli delegate flow  marks success after exit | Success scenario | functional | P2 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_qwen_auth_runtime_handler.py`

- **Test cases:** 4
- **Lines:** 212

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_qwen_runtime_handler_plan_start_matches_shared_contract` | Tests qwen runtime handler plan start matches shared contract | Contract verification | contract | P1 |
| `test_qwen_runtime_handler_oauth_proxy_start_and_refresh_success` | Tests auth qwen runtime handler o proxy start and refresh success | Success scenario | functional | P2 |
| `test_qwen_runtime_handler_coding_plan_cli_sets_api_key_input` | Tests key qwen runtime handler coding plan cli sets api  input | Standard scenario | functional | P2 |
| `test_qwen_runtime_handler_coding_plan_proxy_handles_api_key_input` | Tests handling of qwen runtime handler coding plan proxy  api key input | Standard scenario | functional | P2 |

**Assessment:** Adequate coverage with 4 test functions.

#### `test_qwen_coding_plan_flow.py`

- **Test cases:** 2
- **Lines:** 91

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_qwen_coding_plan_flow_writes_snapshot_backed_settings` | Tests settings qwen coding plan flow writes snapshot backed | Standard scenario | functional | P1 |
| `test_qwen_coding_plan_flow_global_uses_official_intl_endpoint` | Tests endpoint qwen coding plan flow global uses official intl | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_test_data_dir_isolation.py`

- **Test cases:** 1
- **Lines:** 15

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_tests_use_isolated_data_dir` | Tests tests use isolated data dir | Standard scenario | functional | P1 |

**Assessment:** Sparse coverage with 1 test function.

### Category: orchestration/core

#### `test_job_orchestrator.py`

- **Test cases:** 59
- **Lines:** 4246

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_run_job_missing_required_input_marks_failed` | Tests input run job missing required  marks failed | Missing required field | functional | P0 |
| `test_run_job_writes_output_warnings` | Tests output run job writes  warnings | Standard scenario | functional | P0 |
| `test_run_job_cancel_requested_before_execution_short_circuits` | Tests cancellation run job  requested before execution short circuits | Cancellation request | functional | P0 |
| `test_cancel_run_running_updates_status_and_sets_flag` | Tests update of cancel run running  status and sets flag | Cancellation request | functional | P0 |
| `test_run_job_records_artifacts_in_result` | Tests run job records artifacts in result | Standard scenario | functional | P1 |
| `test_run_job_fails_when_output_json_missing` | Tests output run job fails when  json missing | Missing required field | functional | P1 |
| `test_run_job_recovers_output_from_result_file_when_stdout_missing` | Tests output run job recovers  from result file when stdout missing | Missing required field | functional | P1 |
| `test_run_job_recovers_output_from_result_file_when_stdout_schema_invalid` | Tests output run job recovers  from result file when stdout schema invalid | Invalid input | contract | P1 |
| `test_run_job_result_file_fallback_respects_declared_filename` | Tests fallback for run job result file  respects declared filename | Fallback path | functional | P1 |
| `test_run_job_result_file_fallback_prefers_latest_mtime` | Tests fallback for run job result file  prefers lamtime | Fallback path | functional | P1 |
| `test_run_job_result_file_fallback_uses_shallow_path_when_mtime_ties` | Tests fallback for run job result file  uses shallow path when mtime ties | Fallback path | functional | P2 |
| `test_run_job_result_file_fallback_invalid_json_still_fails` | Tests fallback for run job result file  invalid json still fails | Invalid input | functional | P1 |
| `test_run_job_result_file_fallback_schema_invalid_still_fails` | Tests fallback for run job result file  schema invalid still fails | Invalid input | contract | P1 |
| `test_run_job_result_file_fallback_recovers_interactive_run_after_legacy_ask_user` | Tests fallback for run job result file  recovers interactive run after legacy ask user | Fallback path | regression | P1 |
| `test_run_job_result_file_fallback_does_not_override_waiting_auth` | Tests fallback for run job result file  does not override waiting auth | Fallback path | functional | P0 |
| `test_run_job_fails_when_required_artifacts_missing` | Tests run job fails when required artifacts missing | Missing required field | functional | P1 |
| `test_run_job_autofix_moves_required_artifact_to_canonical_path` | Tests auto mode run job fix moves required artifact to canonical path | Standard scenario | functional | P1 |
| `test_run_job_autofix_target_exists_keeps_existing_and_warns` | Tests auto mode run job fix target exists keeps existing and warns | Standard scenario | functional | P2 |
| `test_run_job_autofix_rejects_outside_run_dir_path` | Validates rejection of run job autofix  outside run dir path | Standard scenario | functional | P0 |
| `test_run_job_marks_auth_required_error_code` | Tests error handling for run job marks auth required  code | Error condition | functional | P0 |
| `test_run_job_does_not_mark_low_confidence_auth_as_auth_required` | Tests auth run job does not mark low confidence  as auth required | Standard scenario | functional | P1 |
| `test_run_job_marks_timeout_error_code` | Tests timeout for run job marks  error code | Timeout scenario | functional | P0 |
| `test_run_job_timeout_reason_has_priority_over_exit_code` | Tests timeout for run job  reason has priority over exit code | Timeout scenario | functional | P1 |
| `test_run_job_registers_and_cleans_trust` | Tests registration of run job  and cleans trust | Standard scenario | functional | P1 |
| `test_run_job_repair_success_sets_warning_and_cacheable` | Tests caching run job repair success sets warning and able | Success scenario | functional | P1 |
| `test_run_job_records_runtime_dependency_injection_warning` | Tests run job records runtime dependency injection warning | Standard scenario | functional | P2 |
| `test_run_job_repair_result_still_fails_when_schema_invalid` | Tests schema run job repair result still fails when  invalid | Invalid input | contract | P1 |
| `test_run_job_interactive_waiting_user_persists_profile_and_handle` | Tests run job interactive waiting user persists profile and handle | Standard scenario | functional | P2 |
| `test_run_job_interactive_waiting_user_session_handle_can_be_extracted_from_stderr` | Tests session run job interactive waiting user  handle can be extracted from stderr | Standard scenario | functional | P2 |
| `test_run_job_interactive_missing_interaction_id_falls_back_to_waiting_user` | Tests interaction run job interactive missing  id falls back to waiting user | Missing required field | functional | P1 |
| ... (29 more tests) | See source file | — | — | — |

**Assessment:** Comprehensive coverage with 59 test functions.

#### `test_live_publish_ordering.py`

- **Test cases:** 9
- **Lines:** 432

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_fcmp_publisher_buffers_challenge_until_method_selection_is_published` | Tests publishing of fcmp er buffers challenge until method selection is published | Standard scenario | functional | P0 |
| `test_fcmp_publisher_allows_single_method_challenge_without_selection` | Tests publishing of fcmp er allows single method challenge without selection | Standard scenario | functional | P1 |
| `test_fcmp_publisher_buffers_success_terminal_until_assistant_message_is_published` | Tests publishing of fcmp er buffers success terminal until assistant message is published | Success scenario | functional | P0 |
| `test_fcmp_publisher_drain_mirror_flushes_audit_file` | Tests publishing of fcmp er drain mirror flushes audit file | Standard scenario | functional | P1 |
| `test_rasp_audit_mirror_writer_persists_jsonl_rows` | Tests audit rasp  mirror writer persists jsonl rows | Standard scenario | functional | P1 |
| `test_orchestrator_waiting_user_event_keeps_prompt_before_state_in_live_and_history` | Tests state of orchestrator waiting user event keeps prompt before  in live and history | Standard scenario | functional | P1 |
| `test_orchestrator_auth_selection_is_published_before_challenge` | Tests auth orchestrator  selection is published before challenge | Standard scenario | functional | P0 |
| `test_chat_replay_publish_is_fcmp_derived_and_happens_after_fcmp_commit` | Tests publishing of chat replay  is fcmp derived and happens after fcmp commit | Standard scenario | functional | P1 |
| `test_orchestrator_auth_busy_maps_to_diagnostic_instead_of_challenge` | Tests auth orchestrator  busy maps to diagnostic instead of challenge | Standard scenario | functional | P1 |

**Assessment:** Adequate coverage with 9 test functions.

#### `test_orchestration_no_compat_shells.py`

- **Test cases:** 1
- **Lines:** 11

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_orchestration_compat_shells_removed` | Tests orchestration compat shells removed | Standard scenario | regression | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_orchestrator_history_seq_backfill.py`

- **Test cases:** 1
- **Lines:** 101

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_list_protocol_history_backfills_orchestrator_seq` | Tests listing protocol history backfills orchestrator seq | Standard scenario | contract | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_run_audit_contract_service.py`

- **Test cases:** 1
- **Lines:** 30

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_initialize_attempt_audit_creates_service_log_skeleton` | Tests creation of initialize attempt audit  service log skeleton | Standard scenario | functional | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_run_auth_orchestration_service.py`

- **Test cases:** 24
- **Lines:** 1452

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_available_methods_for_uses_strategy_service` | Tests strategy available methods for uses  service | Standard scenario | functional | P1 |
| `test_available_methods_for_drops_unknown_strategy_values` | Tests strategy available methods for drops unknown  values | Standard scenario | functional | P2 |
| `test_challenge_profile_appends_high_risk_notice_for_opencode_google` | Tests challenge profile appends high risk notice for opencode google | Standard scenario | functional | P1 |
| `test_resolve_effective_provider_id_prefers_canonical_for_provider_aware_engine` | Tests resolve effective provider id prefers canonical for provider aware engine | Standard scenario | functional | P1 |
| `test_resolve_effective_provider_id_uses_qwen_rule_fallback_when_provider_missing` | Tests fallback for resolve effective provider id uses qwen rule  when provider missing | Missing required field | functional | P1 |
| `test_build_import_pending_auth_embeds_upload_files_ask_user` | Tests auth build import pending  embeds upload files ask user | Standard scenario | structural | P1 |
| `test_create_custom_provider_pending_auth_persists_provider_config_challenge` | Tests auth create custom provider pending  persists provider config challenge | Standard scenario | functional | P0 |
| `test_create_pending_auth_multi_method_returns_selection` | Tests return value for create pending auth multi method  selection | Standard scenario | functional | P0 |
| `test_create_pending_auth_single_method_starts_session` | Tests session create pending auth single method starts | Standard scenario | functional | P0 |
| `test_create_pending_auth_qwen_oauth_proxy_auto_poll_hides_chat_input` | Tests auth create pending  qwen oauth proxy auto poll hides chat input | Standard scenario | functional | P1 |
| `test_create_pending_auth_opencode_prefers_canonical_provider_over_detection_hint` | Tests auth create pending  opencode prefers canonical provider over detection hint | Standard scenario | functional | P1 |
| `test_create_pending_auth_single_method_busy_reprojects_active_challenge` | Tests auth create pending  single method busy reprojects active challenge | Standard scenario | functional | P1 |
| `test_select_auth_method_rejects_when_challenge_already_active` | Validates rejection of select auth method  when challenge already active | Standard scenario | functional | P1 |
| `test_submit_auth_input_retry_does_not_persist_raw_secret` | Tests auth submit  input retry does not persist raw secret | Standard scenario | functional | P0 |
| `test_submit_auth_input_completed_schedules_resume_attempt` | Tests auth submit  input completed schedules resume attempt | Standard scenario | functional | P0 |
| `test_submit_custom_provider_input_updates_provider_store_and_retries` | Tests update of submit custom provider input  provider store and retries | Standard scenario | functional | P1 |
| `test_submit_auth_input_writes_schema_valid_accepted_event` | Tests auth submit  input writes schema valid accepted event | Standard scenario | contract | P1 |
| `test_get_auth_session_status_returns_backend_truth` | Tests return value for get auth session status  backend truth | Standard scenario | functional | P1 |
| `test_get_auth_session_status_reconciles_completed_callback` | Tests session get auth  status reconciles completed callback | Standard scenario | functional | P2 |
| `test_reconcile_waiting_auth_non_terminal_snapshot_is_noop` | Tests auth reconcile waiting  non terminal snapshot is noop | Standard scenario | functional | P2 |
| `test_get_auth_session_status_reconciles_completed_qwen_auto_poll` | Tests session get auth  status reconciles completed qwen auto poll | Standard scenario | functional | P2 |
| `test_submit_auth_input_completed_session_returns_conflict_not_500` | Tests return value for submit auth input completed session  conflict not 500 | Resource conflict | functional | P1 |
| `test_get_auth_session_status_times_out_missing_session_marks_failed` | Tests session get auth  status times out missing session marks failed | Missing required field | functional | P1 |
| `test_engine_callback_dispatch_schedules_reconcile` | Tests patching engine callback dis schedules reconcile | Standard scenario | functional | P2 |

**Assessment:** Comprehensive coverage with 24 test functions.

#### `test_run_cleanup_manager.py`

- **Test cases:** 9
- **Lines:** 343

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_cleanup_expired_runs_removes_failed_and_old` | Tests cleanup expired runs removes failed and old | Standard scenario | functional | P1 |
| `test_cleanup_skips_queued_and_running` | Tests queue cleanup skips d and running | Standard scenario | functional | P1 |
| `test_cleanup_handles_invalid_timestamp` | Tests handling of cleanup  invalid timestamp | Invalid input | functional | P2 |
| `test_cleanup_handles_missing_run_dir` | Tests handling of cleanup  missing run dir | Missing required field | functional | P1 |
| `test_cleanup_disabled_when_retention_zero` | Tests cleanup disabled when retention zero | Standard scenario | functional | P2 |
| `test_clear_all_removes_runs_and_requests` | Tests clear all removes runs and requests | Standard scenario | functional | P1 |
| `test_cleanup_stale_trust_entries_passes_active_run_dirs` | Tests trust cleanup stale  entries passes active run dirs | Stale data | functional | P1 |
| `test_cleanup_auxiliary_storage_prunes_tmp_uploads_and_closed_leases` | Tests loading of cleanup auxiliary storage prunes tmp up and closed leases | Standard scenario | functional | P1 |
| `test_cleanup_auxiliary_storage_keeps_active_ui_shell_session_dir` | Tests session cleanup auxiliary storage keeps active ui shell  dir | Standard scenario | regression | P2 |

**Assessment:** Adequate coverage with 9 test functions.

#### `test_run_execution_core.py`

- **Test cases:** 7
- **Lines:** 107

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_resolve_conversation_mode_defaults_to_session` | Tests session resolve conversation mode defaults to | Default configuration | functional | P1 |
| `test_non_session_dual_mode_defaults_to_auto` | Tests session non  dual mode defaults to auto | Default configuration | functional | P1 |
| `test_non_session_interactive_only_normalizes_to_zero_timeout_autoreply` | Tests timeout for non session interactive only normalizes to zero  autoreply | Timeout scenario | functional | P1 |
| `test_session_interactive_preserves_requested_policy` | Tests session interactive preserves requested policy | Standard scenario | functional | P1 |
| `test_runtime_default_options_are_applied_when_request_missing` | Tests default runtime  options are applied when request missing | Missing required field | functional | P1 |
| `test_runtime_request_options_override_skill_defaults` | Tests default runtime request options override skill s | Default configuration | functional | P1 |
| `test_invalid_runtime_default_options_are_ignored_with_warning` | Tests default invalid runtime  options are ignored with warning | Invalid input | functional | P2 |

**Assessment:** Adequate coverage with 7 test functions.

#### `test_run_file_filter_service.py`

- **Test cases:** 3
- **Lines:** 24

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_non_debug_allowlist_is_explicit_only` | Tests listing non debug allow is explicit only | Standard scenario | functional | P1 |
| `test_debug_denylist_filters_node_modules` | Tests filtering debug denylist s node modules | Standard scenario | structural | P2 |
| `test_run_explorer_path_rejects_filtered_ancestors` | Validates rejection of run explorer path  filtered ancestors | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_run_folder_bootstrapper.py`

- **Test cases:** 2
- **Lines:** 119

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_run_folder_bootstrapper_materializes_installed_skill_once` | Tests installation run folder bootstrapper materializes ed skill once | Standard scenario | functional | P1 |
| `test_run_folder_bootstrapper_materializes_temp_skill_package` | Tests bootstrap run folder per materializes temp skill package | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_run_folder_git_initializer.py`

- **Test cases:** 3
- **Lines:** 52

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_ensure_git_repo_initializes_when_missing` | Tests ensure git repo initializes when missing | Missing required field | functional | P2 |
| `test_ensure_git_repo_is_idempotent_when_git_dir_exists` | Tests idempotent behavior ensure git repo is  when git dir exists | Standard scenario | functional | P2 |
| `test_ensure_git_repo_raises_on_git_failure` | Tests that exception is raised for ensure git repo  on git failure | Failure scenario | functional | P2 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_run_folder_trust_manager.py`

- **Test cases:** 6
- **Lines:** 166

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_codex_register_and_remove_run_folder` | Tests codex register and remove run folder | Standard scenario | functional | P1 |
| `test_gemini_register_repairs_malformed_file` | Tests gemini register repairs malformed file | Standard scenario | functional | P1 |
| `test_claude_register_and_remove_run_folder` | Tests claude register and remove run folder | Standard scenario | functional | P1 |
| `test_cleanup_stale_entries_only_removes_inactive_run_paths` | Tests stale rejection cleanup  entries only removes inactive run paths | Stale data | functional | P1 |
| `test_bootstrap_parent_trust_is_idempotent` | Tests bootstrap parent trust is idempotent | Standard scenario | functional | P2 |
| `test_claude_register_repairs_malformed_file` | Tests claude register repairs malformed file | Standard scenario | functional | P1 |

**Assessment:** Adequate coverage with 6 test functions.

#### `test_run_folder_trust_manager_dispatch.py`

- **Test cases:** 2
- **Lines:** 56

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_run_folder_trust_manager_has_no_engine_branches` | Tests trust run folder  manager has no engine branches | Standard scenario | structural | P2 |
| `test_run_folder_trust_manager_dispatches_to_registry` | Tests trust run folder  manager dispatches to registry | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_run_interaction_lifecycle_service.py`

- **Test cases:** 5
- **Lines:** 207

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_persist_waiting_interaction_preserves_current_attempt_as_source_attempt` | Tests interaction persist waiting  preserves current attempt as source attempt | Standard scenario | functional | P0 |
| `test_persist_waiting_interaction_fails_when_handle_missing` | Tests interaction persist waiting  fails when handle missing | Missing required field | functional | P0 |
| `test_build_default_pending_interaction_uses_generic_prompt` | Tests default build  pending interaction uses generic prompt | Default configuration | functional | P1 |
| `test_extract_pending_interaction_projects_pending_branch` | Tests interaction extract pending  projects pending branch | Standard scenario | functional | P1 |
| `test_extract_pending_interaction_rejects_legacy_ask_user_object` | Validates rejection of extract pending interaction  legacy ask user object | Standard scenario | regression | P1 |

**Assessment:** Adequate coverage with 5 test functions.

#### `test_run_observability.py`

- **Test cases:** 33
- **Lines:** 1904

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_list_runs_and_get_logs_tail` | Tests listing runs and get logs tail | Standard scenario | functional | P2 |
| `test_list_runs_reconciles_waiting_auth_before_render` | Tests auth list runs reconciles waiting  before render | Standard scenario | functional | P2 |
| `test_get_run_detail_redrives_queued_resume_ticket` | Tests queue get run detail redrives d resume ticket | Standard scenario | functional | P2 |
| `test_missing_run_dir_queued_resume_reconciles_failed_in_list_and_detail` | Tests queue missing run dir d resume reconciles failed in list and detail | Missing required field | functional | P1 |
| `test_timeline_protocol_summary_formats_output_repair_event` | Tests timeline protocol summary formats output repair event | Standard scenario | contract | P1 |
| `test_get_run_detail_hides_denylisted_node_modules` | Tests listing get run detail hides denyed node modules | Standard scenario | structural | P2 |
| `test_run_file_preview_rejects_filtered_node_modules_path` | Validates rejection of run file preview  filtered node modules path | Standard scenario | structural | P2 |
| `test_read_log_increment_supports_offsets_and_chunking` | Tests port read log increment sups offsets and chunking | Standard scenario | functional | P2 |
| `test_event_history_prefers_live_journal_when_audit_missing` | Tests audit event history prefers live journal when  missing | Missing required field | functional | P1 |
| `test_iter_sse_events_replays_live_journal_without_materializing_audit` | Tests audit iter sse events replays live journal without materializing | Standard scenario | functional | P2 |
| `test_list_event_history_filters_invalid_fcmp_rows` | Tests filtering list event history s invalid fcmp rows | Invalid input | functional | P1 |
| `test_list_event_history_delegates_to_fcmp_protocol_history` | Tests listing event history delegates to fcmp protocol history | Standard scenario | contract | P1 |
| `test_list_protocol_history_rejects_unknown_stream` | Validates rejection of list protocol history  unknown stream | Standard scenario | contract | P1 |
| `test_list_protocol_history_rasp_terminal_uses_audit_only` | Tests audit list protocol history rasp terminal uses  only | Standard scenario | contract | P1 |
| `test_list_protocol_history_terminal_fcmp_falls_back_to_live_when_mirror_drain_times_out` | Tests listing protocol history terminal fcmp falls back to live when mirror drain times out | Standard scenario | contract | P1 |
| `test_list_protocol_history_fcmp_does_not_trigger_materialize` | Tests listing protocol history fcmp does not trigger materialize | Standard scenario | contract | P1 |
| `test_list_protocol_history_fcmp_running_current_attempt_uses_live_only` | Tests listing protocol history fcmp running current attempt uses live only | Standard scenario | contract | P1 |
| `test_list_protocol_history_rasp_running_current_attempt_uses_live_only` | Tests listing protocol history rasp running current attempt uses live only | Standard scenario | contract | P1 |
| `test_list_protocol_history_running_old_attempt_still_uses_audit` | Tests audit list protocol history running old attempt still uses | Standard scenario | contract | P1 |
| `test_iter_sse_events_chat_only_for_terminal_status` | Tests terminal state iter sse events chat only for  status | Standard scenario | functional | P2 |
| `test_iter_sse_events_waiting_user_chat_only` | Tests iter sse events waiting user chat only | Standard scenario | functional | P2 |
| `test_iter_sse_events_drains_trailing_waiting_user_chat_events` | Tests iter sse events drains trailing waiting user chat events | Standard scenario | functional | P2 |
| `test_drain_trailing_chat_events_waits_for_expected_attempt` | Tests drain trailing chat events waits for expected attempt | Standard scenario | functional | P2 |
| `test_iter_sse_events_waiting_auth_chat_only` | Tests auth iter sse events waiting  chat only | Standard scenario | functional | P2 |
| `test_iter_sse_events_cursor_skips_old_chat_events` | Tests iter sse events cursor skips old chat events | Standard scenario | functional | P2 |
| `test_list_event_history_filters_fcmp_by_seq` | Tests filtering list event history s fcmp by seq | Standard scenario | functional | P2 |
| `test_read_log_range_prefers_attempt_logs` | Tests range read log  prefers attempt logs | Standard scenario | functional | P2 |
| `test_read_log_range_does_not_fallback_to_legacy_logs` | Tests fallback for read log range does not  to legacy logs | Fallback path | regression | P2 |
| `test_materialize_protocol_stream_preserves_existing_fcmp_order` | Tests stream handling for materialize protocol  preserves existing fcmp order | Standard scenario | contract | P1 |
| `test_rebuild_protocol_history_prefers_io_chunks_and_creates_backup` | Tests creation of rebuild protocol history prefers io chunks and  backup | Standard scenario | contract | P1 |
| ... (3 more tests) | See source file | — | — | — |

**Assessment:** Comprehensive coverage with 33 test functions.

#### `test_run_observability_attempt_partitioning.py`

- **Test cases:** 1
- **Lines:** 86

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_protocol_history_partitioned_by_attempt` | Tests partitioning of protocol history ed by attempt | Standard scenario | contract | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_run_output_convergence_service.py`

- **Test cases:** 3
- **Lines:** 288

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_convergence_repairs_auto_attempt_with_fenced_json` | Tests convergence of repairs auto attempt with fenced json | Standard scenario | functional | P0 |
| `test_convergence_skips_repair_without_session_handle` | Tests session convergence skips repair without  handle | Standard scenario | functional | P1 |
| `test_convergence_repairs_interactive_attempt_to_pending_branch` | Tests convergence of repairs interactive attempt to pending branch | Standard scenario | functional | P0 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_run_output_schema_service.py`

- **Test cases:** 3
- **Lines:** 175

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_materialize_auto_schema_artifacts_and_request_input_fields` | Tests auto mode materialize  schema artifacts and request input fields | Standard scenario | contract | P1 |
| `test_materialize_interactive_machine_schema_uses_union_and_keeps_stable_path` | Tests schema materialize interactive machine  uses union and keeps stable path | Standard scenario | contract | P1 |
| `test_materialize_missing_output_schema_skips_artifacts` | Tests output materialize missing  schema skips artifacts | Missing required field | contract | P2 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_run_recovery_service.py`

- **Test cases:** 5
- **Lines:** 208

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_recover_waiting_auth_fails_when_pending_auth_cannot_resume_after_restart` | Tests auth recover waiting  fails when pending auth cannot resume after restart | Standard scenario | functional | P0 |
| `test_recover_waiting_auth_preserves_method_selection` | Tests auth recover waiting  preserves method selection | Standard scenario | functional | P0 |
| `test_redrive_resume_ticket_existing_run_dir_schedules_resume_once` | Tests redrive resume ticket existing run dir schedules resume once | Standard scenario | functional | P0 |
| `test_redrive_resume_ticket_missing_run_dir_reconciles_failed` | Tests redrive resume ticket missing run dir reconciles failed | Missing required field | functional | P0 |
| `test_cleanup_orphan_runtime_bindings_logs_startup_reap` | Tests cleanup orphan runtime bindings logs startup reap | Standard scenario | functional | P1 |

**Assessment:** Adequate coverage with 5 test functions.

#### `test_run_service_log_mirror.py`

- **Test cases:** 4
- **Lines:** 125

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_mirror_writes_only_matching_run_and_attempt` | Tests mirror writes only matching run and attempt | Standard scenario | functional | P1 |
| `test_mirror_drops_records_without_run_id_context` | Tests mirror drops records without run id context | Standard scenario | functional | P2 |
| `test_mirror_rotates_log_file` | Tests mirror rotates log file | Standard scenario | functional | P2 |
| `test_run_scope_is_superset_of_attempt_scope` | Tests run scope is superset of attempt scope | Standard scenario | functional | P1 |

**Assessment:** Adequate coverage with 4 test functions.

#### `test_run_source_adapter.py`

- **Test cases:** 3
- **Lines:** 58

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_installed_source_capability_matrix` | Tests installation ed source capability matrix | Standard scenario | functional | P1 |
| `test_cache_lookup_reads_installed_namespace` | Tests caching lookup reads installed namespace | Standard scenario | functional | P1 |
| `test_get_request_and_run_dir_reads_source_request` | Tests get request and run dir reads source request | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_run_store.py`

- **Test cases:** 21
- **Lines:** 509

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_run_store_request_and_cache` | Tests caching run store request and | Standard scenario | functional | P0 |
| `test_run_store_missing_request_returns_none` | Tests return value for run store missing request  none | Missing required field | functional | P1 |
| `test_run_store_cache_miss_returns_none` | Tests return value for run store cache miss  none | Standard scenario | functional | P1 |
| `test_run_store_regular_and_temp_cache_are_isolated` | Tests caching run store regular and temp  are isolated | Standard scenario | functional | P1 |
| `test_update_run_status_without_result_path` | Tests update run status without result path | Standard scenario | functional | P1 |
| `test_update_run_status_with_result_path` | Tests update run status with result path | Standard scenario | functional | P1 |
| `test_list_active_run_ids` | Tests listing active run ids | Standard scenario | functional | P1 |
| `test_cancel_requested_roundtrip` | Tests cancellation requested roundtrip | Cancellation request | functional | P1 |
| `test_pending_interaction_roundtrip` | Tests interaction pending  roundtrip | Standard scenario | functional | P0 |
| `test_submit_interaction_reply_idempotent` | Tests interaction submit  reply idempotent | Standard scenario | functional | P1 |
| `test_interactive_runtime_roundtrip` | Tests interactive runtime roundtrip | Standard scenario | functional | P0 |
| `test_get_request_by_run_id` | Tests get request by run id | Standard scenario | functional | P1 |
| `test_interaction_history_and_consume_reply` | Tests history interaction  and consume reply | Standard scenario | functional | P1 |
| `test_auto_decision_stats` | Tests auto mode decision stats | Standard scenario | functional | P1 |
| `test_resume_ticket_roundtrip_is_idempotent` | Tests idempotent behavior resume ticket roundtrip is | Standard scenario | functional | P0 |
| `test_recovery_metadata_and_incomplete_scan_roundtrip` | Tests recovery of metadata and incomplete scan roundtrip | Recovery scenario | functional | P0 |
| `test_migrate_legacy_interactive_runtime_table` | Tests migrate legacy interactive runtime table | Standard scenario | regression | P1 |
| `test_set_pending_interaction_rejects_invalid_payload` | Validates rejection of set pending interaction  invalid payload | Invalid input | functional | P0 |
| `test_list_interaction_history_skips_legacy_invalid_rows` | Tests listing interaction history skips legacy invalid rows | Invalid input | regression | P1 |
| `test_get_pending_interaction_ignores_invalid_legacy_payload` | Tests interaction get pending  ignores invalid legacy payload | Invalid input | regression | P1 |
| `test_run_store_reinitializes_after_db_file_deleted` | Tests store run  reinitializes after db file deleted | Standard scenario | functional | P1 |

**Assessment:** Comprehensive coverage with 21 test functions.

#### `test_runs_router_cache.py`

- **Test cases:** 25
- **Lines:** 1136

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_create_run_cache_hit_without_input` | Tests caching create run  hit without input | Standard scenario | functional | P1 |
| `test_create_run_rejects_when_queue_full` | Validates rejection of create run  when queue full | Standard scenario | functional | P1 |
| `test_create_run_cache_miss_without_input` | Tests caching create run  miss without input | Standard scenario | functional | P1 |
| `test_create_run_applies_skill_runtime_default_options` | Tests default create run applies skill runtime  options | Default configuration | functional | P1 |
| `test_create_run_request_runtime_options_override_skill_defaults` | Tests default create run request runtime options override skill s | Default configuration | functional | P1 |
| `test_create_run_invalid_skill_runtime_defaults_emit_warning_payload` | Tests default create run invalid skill runtime s emit warning payload | Invalid input | functional | P2 |
| `test_create_run_with_input_schema_requires_upload` | Tests input create run with  schema requires upload | Standard scenario | contract | P1 |
| `test_create_run_with_inline_only_input_starts_immediately` | Tests input create run with inline only  starts immediately | Standard scenario | functional | P1 |
| `test_create_run_with_inline_required_missing_returns_400` | Tests return value for create run with inline required missing  400 | Missing required field | functional | P1 |
| `test_create_run_allows_missing_engines_and_defaults_to_all` | Tests default create run allows missing engines and s to all | Missing required field | functional | P2 |
| `test_create_run_rejects_engine_not_allowed` | Validates rejection of create run  engine not allowed | Standard scenario | functional | P1 |
| `test_create_run_rejects_engine_denied_by_unsupported_engines` | Validates rejection of create run  engine denied by unsupported engines | Standard scenario | functional | P1 |
| `test_upload_file_cache_hit` | Tests caching upload file  hit | Standard scenario | functional | P1 |
| `test_upload_file_interactive_skips_cache_hit` | Tests caching upload file interactive skips  hit | Standard scenario | functional | P1 |
| `test_upload_file_cache_miss` | Tests caching upload file  miss | Standard scenario | functional | P1 |
| `test_upload_file_rejects_when_queue_full` | Validates rejection of upload file  when queue full | Standard scenario | functional | P1 |
| `test_upload_temp_skill_creates_run_without_installed_registry_lookup` | Tests creation of upload temp skill  run without installed registry lookup | Standard scenario | functional | P1 |
| `test_upload_temp_skill_applies_runtime_default_options` | Tests default upload temp skill applies runtime  options | Default configuration | functional | P1 |
| `test_create_run_no_cache_skips_hit` | Tests caching create run no  skips hit | Standard scenario | structural | P1 |
| `test_create_run_interactive_skips_cache_hit` | Tests caching create run interactive skips  hit | Standard scenario | functional | P1 |
| `test_create_run_rejects_interactive_when_skill_declares_auto_only` | Validates rejection of create run  interactive when skill declares auto only | Standard scenario | functional | P1 |
| `test_get_run_artifacts_lists_outputs` | Tests listing get run artifacts s outputs | Standard scenario | functional | P1 |
| `test_get_run_artifacts_empty` | Tests get run artifacts empty | Empty input | functional | P2 |
| `test_get_run_bundle_returns_zip` | Tests return value for get run bundle  zip | Standard scenario | functional | P1 |
| `test_get_run_artifacts_does_not_scan_unlisted_files` | Tests scanning of get run artifacts does not  unlisted files | Standard scenario | functional | P1 |

**Assessment:** Comprehensive coverage with 25 test functions.

#### `test_workspace_manager.py`

- **Test cases:** 8
- **Lines:** 261

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_create_run_structure` | Tests create run structure | Standard scenario | structural | P0 |
| `test_create_run_rejects_unsupported_engine` | Validates rejection of create run  unsupported engine | Standard scenario | functional | P0 |
| `test_handle_upload` | Tests handle upload | Standard scenario | functional | P1 |
| `test_handle_upload_nested_paths` | Tests handle upload nested paths | Standard scenario | functional | P1 |
| `test_handle_upload_bad_zip` | Tests handle upload bad zip | Standard scenario | functional | P2 |
| `test_write_input_manifest_empty_uploads` | Tests loading of write input manifest empty up | Empty input | functional | P1 |
| `test_promote_request_uploads_moves_files` | Tests loading of promote request up moves files | Standard scenario | functional | P1 |
| `test_promote_request_uploads_existing_target_raises` | Tests that exception is raised for promote request uploads existing target | Standard scenario | functional | P2 |

**Assessment:** Adequate coverage with 8 test functions.

### Category: platform/infrastructure

#### `test_bundle_manifest.py`

- **Test cases:** 3
- **Lines:** 85

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_bundle_manifest_includes_run_files` | Tests manifest bundle  includes run files | Standard scenario | functional | P2 |
| `test_bundle_manifest_debug_false_filters_logs` | Tests filtering bundle manifest debug false s logs | Standard scenario | functional | P2 |
| `test_build_run_bundle_public_api_keeps_compatibility` | Tests build run bundle public api keeps compatibility | Standard scenario | functional | P2 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_cache_key_builder.py`

- **Test cases:** 15
- **Lines:** 265

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_input_manifest_hash_changes_with_content` | Tests manifest input  hash changes with content | Standard scenario | functional | P2 |
| `test_skill_fingerprint_changes_with_files` | Tests fingerprint skill  changes with files | Standard scenario | functional | P2 |
| `test_cache_key_stable_for_same_inputs` | Tests caching key stable for same inputs | Standard scenario | functional | P2 |
| `test_input_manifest_empty_dir` | Tests manifest input  empty dir | Empty input | functional | P2 |
| `test_inline_input_hash_changes_with_payload` | Tests hash computation inline input  changes with payload | Standard scenario | functional | P2 |
| `test_inline_input_hash_empty_payload_is_blank` | Tests hash computation inline input  empty payload is blank | Empty input | functional | P2 |
| `test_cache_key_changes_with_inline_input_hash` | Tests caching key changes with inline input hash | Standard scenario | functional | P2 |
| `test_skill_fingerprint_engine_specific_config` | Tests configuration skill fingerprint engine specific | Standard scenario | functional | P2 |
| `test_skill_fingerprint_uses_declared_engine_config_override` | Tests configuration skill fingerprint uses declared engine  override | Override behavior | functional | P2 |
| `test_skill_fingerprint_uses_schema_fallback_assets` | Tests fallback for skill fingerprint uses schema  assets | Fallback path | contract | P1 |
| `test_skill_fingerprint_without_path_returns_empty` | Tests return value for skill fingerprint without path  empty | Empty input | functional | P2 |
| `test_input_manifest_missing_dir` | Tests manifest input  missing dir | Missing required field | functional | P1 |
| `test_compute_bytes_hash_changes_with_content` | Tests hash computation compute bytes  changes with content | Standard scenario | functional | P2 |
| `test_cache_key_changes_with_temp_skill_package_hash` | Tests caching key changes with temp skill package hash | Standard scenario | functional | P2 |
| `test_cache_key_stable_with_same_temp_skill_package_hash` | Tests caching key stable with same temp skill package hash | Standard scenario | functional | P2 |

**Assessment:** Comprehensive coverage with 15 test functions.

#### `test_chat_replay_contract.py`

- **Test cases:** 1
- **Lines:** 24

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_chat_replay_contract_defines_roles_kinds_and_invariants` | Tests chat replay contract defines roles kinds and invariants | Contract verification | contract | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_chat_replay_derivation.py`

- **Test cases:** 9
- **Lines:** 250

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_interaction_reply_accepted_derives_user_bubble` | Tests derivation of interaction reply accepted s user bubble | Standard scenario | functional | P1 |
| `test_auth_input_accepted_derives_user_submission_bubble` | Tests auth input accepted derives user submission bubble | Standard scenario | functional | P1 |
| `test_terminal_state_changed_derives_system_bubble` | Tests state of terminal  changed derives system bubble | Standard scenario | functional | P1 |
| `test_assistant_final_derivation_strips_ask_user_yaml_block` | Tests assistant final derivation strips ask user yaml block | Standard scenario | functional | P1 |
| `test_assistant_final_derivation_keeps_raw_ref_in_correlation` | Tests assistant final derivation keeps raw ref in correlation | Standard scenario | functional | P1 |
| `test_assistant_final_derivation_prefers_display_text` | Tests assistant final derivation prefers display text | Standard scenario | functional | P1 |
| `test_assistant_process_derivation_maps_reasoning_tool_and_command` | Tests assistant process derivation maps reasoning tool and command | Standard scenario | functional | P1 |
| `test_assistant_intermediate_derivation_maps_to_assistant_message` | Tests assistant intermediate derivation maps to assistant message | Standard scenario | functional | P1 |
| `test_assistant_message_promoted_derivation_emits_no_chat_row` | Tests emission of assistant message promoted derivation s no chat row | Standard scenario | structural | P2 |

**Assessment:** Adequate coverage with 9 test functions.

#### `test_chat_replay_live_journal.py`

- **Test cases:** 2
- **Lines:** 34

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_chat_replay_live_journal_publish_and_replay` | Tests publishing of chat replay live journal  and replay | Standard scenario | functional | P1 |
| `test_chat_replay_live_journal_replay_after_cursor` | Tests chat replay live journal replay after cursor | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_chat_replay_publisher.py`

- **Test cases:** 1
- **Lines:** 55

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_chat_replay_publisher_bootstraps_seq_from_audit` | Tests bootstrap chat replay publisher s seq from audit | Standard scenario | functional | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_chat_replay_schema_registry.py`

- **Test cases:** 5
- **Lines:** 102

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_validate_chat_replay_event_accepts_user_auth_submission` | Validates acceptance of validate chat replay event  user auth submission | Standard scenario | functional | P1 |
| `test_validate_chat_replay_history_response_accepts_events` | Validates acceptance of validate chat replay history response  events | Standard scenario | functional | P1 |
| `test_validate_chat_replay_event_accepts_assistant_process` | Validates acceptance of validate chat replay event  assistant process | Standard scenario | functional | P1 |
| `test_validate_chat_replay_event_accepts_assistant_message` | Validates acceptance of validate chat replay event  assistant message | Standard scenario | functional | P1 |
| `test_validate_chat_replay_event_rejects_invalid_role` | Validates rejection of validate chat replay event  invalid role | Invalid input | functional | P0 |

**Assessment:** Adequate coverage with 5 test functions.

#### `test_chat_thinking_core_model.py`

- **Test cases:** 4
- **Lines:** 152

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_chat_thinking_core_switches_assistant_intermediate_between_plain_and_bubble` | Tests chat thinking core switches assistant intermediate between plain and bubble | Standard scenario | functional | P1 |
| `test_chat_thinking_core_dedupes_final_message_by_stable_message_id` | Tests chat thinking core dedupes final message by stable message id | Standard scenario | functional | P1 |
| `test_chat_thinking_core_uses_replaces_message_id_for_final_dedup` | Tests chat thinking core uses replaces message id for final dedup | Standard scenario | functional | P1 |
| `test_chat_thinking_core_switch_projection_is_based_on_canonical_events` | Tests chat thinking core switch projection is based on canonical events | Standard scenario | functional | P1 |

**Assessment:** Adequate coverage with 4 test functions.

#### `test_concurrency_manager.py`

- **Test cases:** 9
- **Lines:** 183

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_start_fallback_when_policy_invalid` | Tests fallback for start  when policy invalid | Invalid input | functional | P1 |
| `test_admit_or_reject_queue_limit` | Tests queue admit or reject  limit | Standard scenario | functional | P2 |
| `test_acquire_and_release_slot_updates_state` | Tests update of acquire and release slot  state | Standard scenario | functional | P2 |
| `test_env_override_for_queue_size` | Tests queue env override for  size | Override behavior | functional | P2 |
| `test_windows_limit_uses_minimum_of_all_dimensions` | Tests windows limit uses minimum of all dimensions | Standard scenario | functional | P2 |
| `test_windows_pid_limit_not_constrained_without_job_limit` | Tests windows pid limit not constrained without job limit | Standard scenario | functional | P2 |
| `test_windows_pid_limit_constrained_with_job_limit` | Tests windows pid limit constrained with job limit | Standard scenario | functional | P2 |
| `test_windows_missing_psutil_fails_fast` | Tests windows missing psutil fails fast | Missing required field | functional | P1 |
| `test_non_windows_probe_error_still_uses_fallback` | Tests fallback for non windows probe error still uses | Error condition | functional | P1 |

**Assessment:** Adequate coverage with 9 test functions.

#### `test_container_runtime_defaults.py`

- **Test cases:** 2
- **Lines:** 26

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_dockerfile_uses_non_root_runtime_user` | Tests dockerfile uses non root runtime user | Standard scenario | functional | P1 |
| `test_compose_documents_optional_data_bind_mount_permissions` | Tests compose documents optional data bind mount permissions | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_data_reset_service.py`

- **Test cases:** 5
- **Lines:** 190

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_data_reset_service_build_targets_includes_expected_optional_paths` | Tests reset data  service build targets includes expected optional paths | Standard scenario | functional | P2 |
| `test_data_reset_service_hides_engine_auth_targets_when_feature_disabled` | Tests auth data reset service hides engine  targets when feature disabled | Standard scenario | functional | P2 |
| `test_data_reset_service_execute_reset_deletes_targets_and_recreates_dirs` | Tests creation of data reset service execute reset deletes targets and re dirs | Standard scenario | functional | P2 |
| `test_data_reset_service_dry_run_returns_preview_details` | Tests return value for data reset service dry run  preview details | Standard scenario | functional | P2 |
| `test_reset_script_delegates_to_shared_data_reset_service` | Tests reset script delegates to shared data reset service | Standard scenario | functional | P2 |

**Assessment:** Adequate coverage with 5 test functions.

#### `test_e2e_client_config.py`

- **Test cases:** 3
- **Lines:** 37

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_e2e_client_port_defaults_to_9814` | Tests default e2e client port s to 9814 | Default configuration | functional | P2 |
| `test_e2e_client_port_env_override_and_invalid_fallback` | Tests fallback for e2e client port env override and invalid | Invalid input | functional | P1 |
| `test_e2e_client_backend_and_fixtures_env` | Tests e2e client backend and fixtures env | Standard scenario | functional | P2 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_e2e_completion_hidden_and_summary_single_source.py`

- **Test cases:** 2
- **Lines:** 21

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_completion_event_does_not_render_chat_bubble` | Tests completion event does not render chat bubble | Standard scenario | functional | P1 |
| `test_agent_messages_are_not_filtered_by_legacy_done_message_guard` | Tests filtering agent messages are not ed by legacy done message guard | Standard scenario | regression | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_e2e_observe_replayless_history_semantics.py`

- **Test cases:** 3
- **Lines:** 27

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_template_uses_history_then_stream_and_no_replay` | Tests stream handling for template uses history then  and no replay | Standard scenario | structural | P1 |
| `test_template_uses_canonical_chat_history_and_stream` | Tests stream handling for template uses canonical chat history and | Standard scenario | functional | P1 |
| `test_template_pending_cards_are_separate_from_chat_replay` | Tests pending state template  cards are separate from chat replay | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_e2e_run_observe_semantics.py`

- **Test cases:** 22
- **Lines:** 280

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_run_observe_template_has_prompt_card_and_shortcut_hint` | Tests observability of run  template has prompt card and shortcut hint | Standard scenario | functional | P1 |
| `test_run_observe_template_has_running_thinking_card` | Tests observability of run  template has running thinking card | Standard scenario | functional | P1 |
| `test_run_observe_template_removes_technical_panels` | Tests observability of run  template removes technical panels | Standard scenario | functional | P2 |
| `test_run_observe_template_consumes_backend_ask_user_hints` | Tests observability of run  template consumes backend ask user hints | Standard scenario | functional | P1 |
| `test_run_observe_template_maps_user_input_required_to_agent_semantics` | Tests observability of run  template maps user input required to agent semantics | Standard scenario | functional | P1 |
| `test_run_observe_template_supports_auth_challenge_and_redacted_submission` | Tests auth run observe template supports  challenge and redacted submission | Standard scenario | functional | P1 |
| `test_run_observe_template_supports_custom_provider_auth_panel` | Tests auth run observe template supports custom provider  panel | Standard scenario | functional | P1 |
| `test_run_observe_auth_import_panel_not_cleared_before_signature_early_return` | Tests auth run observe  import panel not cleared before signature early return | Standard scenario | structural | P2 |
| `test_run_observe_template_hides_technical_auth_details` | Tests auth run observe template hides technical  details | Standard scenario | functional | P2 |
| `test_run_observe_template_hides_prompt_card_body_when_hint_missing` | Tests observability of run  template hides prompt card body when hint missing | Missing required field | functional | P2 |
| `test_run_observe_template_removes_final_summary_card` | Tests observability of run  template removes final summary card | Standard scenario | functional | P2 |
| `test_run_observe_template_defaults_to_plain_mode_for_assistant_messages` | Tests default run observe template s to plain mode for assistant messages | Default configuration | functional | P1 |
| `test_run_observe_template_supports_assistant_process_thinking_bubble` | Tests port run observe template sups assistant process thinking bubble | Standard scenario | functional | P1 |
| `test_run_observe_template_keeps_stream_open_until_terminal_chat_event` | Tests stream handling for run observe template keeps  open until terminal chat event | Standard scenario | functional | P1 |
| `test_run_observe_template_catches_up_history_for_waiting_and_terminal_states` | Tests state of run observe template catches up history for waiting and terminal s | Standard scenario | functional | P1 |
| `test_run_observe_template_reports_client_init_failures_separately_from_backend_errors` | Tests error handling for run observe template reports client init failures separately from backend s | Error condition | functional | P1 |
| `test_run_observe_template_restarts_stream_after_waiting_exit_even_if_existing_stream_is_open` | Tests stream handling for run observe template restarts  after waiting exit even if existing stream is open | Standard scenario | functional | P1 |
| `test_run_observe_template_result_link_removed_and_file_tree_layout_stable` | Tests observability of run  template result link removed and file tree layout stable | Standard scenario | regression | P2 |
| `test_run_observe_template_uses_canonical_chat_replay_routes` | Tests route run observe template uses canonical chat replay s | Standard scenario | functional | P1 |
| `test_run_observe_template_does_not_optimistically_append_chat_bubbles` | Tests observability of run  template does not optimistically append chat bubbles | Standard scenario | functional | P1 |
| `test_run_observe_template_supports_markdown_and_json_preview_modes` | Tests preview run observe template supports markdown and json  modes | Standard scenario | functional | P1 |
| `test_e2e_key_pages_keep_standard_table_action_button_classes` | Tests key e2e  pages keep standard table action button classes | Standard scenario | functional | P2 |

**Assessment:** Comprehensive coverage with 22 test functions.

#### `test_execution_modules_relocated.py`

- **Test cases:** 1
- **Lines:** 10

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_runtime_execution_business_modules_are_relocated` | Tests runtime execution business modules are relocated | Standard scenario | structural | P2 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_fs_diff_ignore_rules.py`

- **Test cases:** 1
- **Lines:** 32

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_job_orchestrator_snapshot_ignores_internal_prefixes` | Tests job orchestrator snapshot ignores internal prefixes | Standard scenario | functional | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_harness_fs_diff_ignore_rules.py`

- **Test cases:** 1
- **Lines:** 34

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_harness_snapshot_ignores_internal_prefixes` | Tests harness snapshot ignores internal prefixes | Standard scenario | functional | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_i18n_locale_coverage.py`

- **Test cases:** 3
- **Lines:** 67

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_all_template_translation_keys_exist_in_english_locale` | Tests key all template translation s exist in english locale | Standard scenario | functional | P2 |
| `test_non_english_locales_cover_all_localizable_template_keys` | Tests key non english locales cover all localizable template s | Standard scenario | functional | P2 |
| `test_non_localized_key_policy_basic_scope` | Tests key non localized  policy basic scope | Standard scenario | functional | P2 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_local_runtime_lease_service.py`

- **Test cases:** 2
- **Lines:** 50

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_first_heartbeat_grace_window_prevents_early_expiry` | Prevents first heartbeat grace window  early expiry | Standard scenario | functional | P1 |
| `test_heartbeat_after_first_renew_uses_regular_ttl_without_grace` | Tests heartbeat after first renew uses regular ttl without grace | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_logging_config.py`

- **Test cases:** 10
- **Lines:** 235

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_setup_logging_installs_stream_and_timed_file_handler` | Tests stream handling for setup logging installs  and timed file handler | Standard scenario | functional | P2 |
| `test_setup_logging_is_idempotent` | Tests logging setup  is idempotent | Standard scenario | functional | P2 |
| `test_setup_logging_keeps_record_factory_idempotent` | Tests logging setup  keeps record factory idempotent | Standard scenario | functional | P2 |
| `test_setup_logging_json_format_writes_expected_fields` | Tests logging setup  json format writes expected fields | Standard scenario | functional | P2 |
| `test_setup_logging_falls_back_to_stream_only_when_file_handler_fails` | Tests stream handling for setup logging falls back to  only when file handler fails | Standard scenario | functional | P2 |
| `test_setup_logging_defaults_apscheduler_to_warning` | Tests default setup logging s apscheduler to warning | Default configuration | functional | P2 |
| `test_setup_logging_raises_apscheduler_to_info_under_debug` | Tests that exception is raised for setup logging  apscheduler to info under debug | Standard scenario | functional | P2 |
| `test_reload_logging_from_settings_replaces_managed_handlers` | Tests settings reload logging from  replaces managed handlers | Standard scenario | functional | P2 |
| `test_logging_settings_payload_uses_settings_file_for_editable_and_env_for_read_only` | Tests settings logging  payload uses settings file for editable and env for read only | Standard scenario | functional | P2 |
| `test_setup_logging_installs_run_context_record_factory` | Tests logging setup  installs run context record factory | Standard scenario | functional | P2 |

**Assessment:** Adequate coverage with 10 test functions.

#### `test_logging_quota_policy.py`

- **Test cases:** 2
- **Lines:** 51

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_enforce_log_dir_quota_evicts_oldest_archives_only` | Tests quota enforce log dir  evicts oldest archives only | Standard scenario | functional | P1 |
| `test_enforce_log_dir_quota_disabled_when_max_bytes_is_zero` | Tests quota enforce log dir  disabled when max bytes is zero | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_model_registry.py`

- **Test cases:** 18
- **Lines:** 406

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_get_models_uses_latest_snapshot_when_version_unknown` | Tests model get s uses lasnapshot when version unknown | Standard scenario | functional | P1 |
| `test_get_models_uses_exact_or_lower_version` | Tests model get s uses exact or lower version | Standard scenario | functional | P1 |
| `test_get_models_no_semver_match` | Tests model get s no semver match | Standard scenario | structural | P2 |
| `test_validate_model_codex_effort` | Tests model validate  codex effort | Standard scenario | functional | P1 |
| `test_validate_model_codex_unsupported_effort` | Tests port validate model codex unsuped effort | Standard scenario | functional | P2 |
| `test_validate_model_non_codex_ignores_suffix_when_effort_is_unsupported` | Tests port validate model non codex ignores suffix when effort is unsuped | Standard scenario | functional | P2 |
| `test_validate_model_opencode_requires_provider_model` | Tests model validate  opencode requires provider model | Standard scenario | functional | P1 |
| `test_validate_model_unknown_engine` | Tests model validate  unknown engine | Standard scenario | functional | P2 |
| `test_get_models_opencode_runtime_probe_cache` | Tests caching get models opencode runtime probe | Standard scenario | functional | P1 |
| `test_get_manifest_view_opencode_dynamic_compat` | Tests manifest get  view opencode dynamic compat | Standard scenario | functional | P1 |
| `test_add_snapshot_for_detected_version_opencode_not_supported` | Tests port add snapshot for detected version opencode not suped | Standard scenario | functional | P2 |
| `test_get_manifest_view` | Tests manifest get  view | Standard scenario | functional | P1 |
| `test_get_manifest_view_qwen_uses_snapshot_contract` | Tests manifest get  view qwen uses snapshot contract | Contract verification | contract | P1 |
| `test_add_snapshot_for_detected_version_success` | Tests detection add snapshot for ed version success | Success scenario | functional | P1 |
| `test_add_snapshot_for_detected_version_rejects_existing` | Validates rejection of add snapshot for detected version  existing | Standard scenario | functional | P2 |
| `test_add_snapshot_for_detected_version_requires_version` | Tests detection add snapshot for ed version requires version | Standard scenario | functional | P2 |
| `test_claude_catalog_merges_custom_provider_models_and_marks_sources` | Tests merge of claude catalog s custom provider models and marks sources | Standard scenario | functional | P1 |
| `test_claude_validate_model_accepts_strict_custom_provider_spec` | Validates acceptance of claude validate model  strict custom provider spec | Standard scenario | functional | P1 |

**Assessment:** Comprehensive coverage with 18 test functions.

#### `test_models_module_structure.py`

- **Test cases:** 3
- **Lines:** 29

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_models_facade_is_thin_module` | Tests model s facade is thin module | Standard scenario | structural | P2 |
| `test_models_package_owns_domain_modules` | Tests model s package owns domain modules | Standard scenario | structural | P2 |
| `test_models_facade_exports_resolve` | Tests port models facade exs resolve | Standard scenario | structural | P2 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_no_unapproved_broad_exception.py`

- **Test cases:** 1
- **Lines:** 115

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_no_unapproved_broad_exception_usage` | Tests no unapproved broad exception usage | Standard scenario | structural | P2 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_process_supervisor.py`

- **Test cases:** 4
- **Lines:** 136

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_process_supervisor_register_release_is_idempotent` | Tests process supervisor process  register release is idempotent | Standard scenario | functional | P2 |
| `test_reap_orphan_leases_on_startup_only_processes_active` | Tests lease reap orphan s on startup only processes active | Standard scenario | functional | P2 |
| `test_terminate_lease_async_falls_back_to_pid_when_process_ref_missing` | Tests async boundary terminate lease  falls back to pid when process ref missing | Missing required field | functional | P1 |
| `test_terminate_lease_sync_with_missing_lease_returns_already_exited` | Tests return value for terminate lease sync with missing lease  already exited | Missing required field | functional | P1 |

**Assessment:** Adequate coverage with 4 test functions.

#### `test_process_termination.py`

- **Test cases:** 5
- **Lines:** 53

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_terminate_pid_tree_invalid_pid` | Tests terminate pid tree invalid pid | Invalid input | functional | P1 |
| `test_terminate_pid_tree_returns_already_exited_when_pid_not_alive` | Tests return value for terminate pid tree  already exited when pid not alive | Standard scenario | functional | P2 |
| `test_terminate_pid_tree_windows_taskkill_success` | Tests terminate pid tree windows taskkill success | Success scenario | functional | P2 |
| `test_terminate_asyncio_process_tree_already_exited` | Tests async boundary terminate io process tree already exited | Standard scenario | functional | P2 |
| `test_terminate_popen_process_tree_delegates` | Tests terminate popen process tree delegates | Standard scenario | functional | P2 |

**Assessment:** Adequate coverage with 5 test functions.

#### `test_protocol_schema_registry.py`

- **Test cases:** 27
- **Lines:** 668

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_validate_fcmp_event_accepts_state_changed_payload` | Validates acceptance of validate fcmp event  state changed payload | Standard scenario | functional | P1 |
| `test_validate_fcmp_event_accepts_terminal_state_changed_payload` | Validates acceptance of validate fcmp event  terminal state changed payload | Standard scenario | functional | P1 |
| `test_validate_fcmp_event_accepts_local_seq_meta` | Validates acceptance of validate fcmp event  local seq meta | Standard scenario | functional | P1 |
| `test_validate_rasp_event_accepts_parsed_json_payload` | Validates acceptance of validate rasp event  parsed json payload | Standard scenario | functional | P1 |
| `test_validate_rasp_event_accepts_run_handle_payload` | Validates acceptance of validate rasp event  run handle payload | Standard scenario | functional | P1 |
| `test_validate_rasp_event_accepts_turn_complete_structured_payload` | Validates acceptance of validate rasp event  turn complete structured payload | Standard scenario | structural | P1 |
| `test_validate_fcmp_event_accepts_optional_correlation` | Validates acceptance of validate fcmp event  optional correlation | Standard scenario | functional | P2 |
| `test_validate_fcmp_event_accepts_auth_required_method_selection` | Validates acceptance of validate fcmp event  auth required method selection | Standard scenario | functional | P1 |
| `test_validate_fcmp_event_accepts_callback_url_submission_kind` | Validates acceptance of validate fcmp event  callback url submission kind | Standard scenario | functional | P1 |
| `test_validate_fcmp_event_rejects_missing_trigger` | Validates rejection of validate fcmp event  missing trigger | Missing required field | functional | P0 |
| `test_validate_pending_interaction_rejects_unknown_fields` | Validates rejection of validate pending interaction  unknown fields | Standard scenario | functional | P0 |
| `test_validate_resume_command_rejects_extra_fields` | Validates rejection of validate resume command  extra fields | Standard scenario | functional | P0 |
| `test_validate_orchestrator_event_accepts_diagnostic_warning` | Validates acceptance of validate orchestrator event  diagnostic warning | Standard scenario | functional | P1 |
| `test_validate_orchestrator_event_accepts_output_repair_exhausted` | Validates acceptance of validate orchestrator event  output repair exhausted | Standard scenario | functional | P1 |
| `test_validate_orchestrator_event_rejects_output_repair_event_with_wrong_category` | Validates rejection of validate orchestrator event  output repair event with wrong category | Standard scenario | functional | P1 |
| `test_validate_fcmp_event_rejects_reserved_output_repair_type` | Validates rejection of validate fcmp event  reserved output repair type | Standard scenario | functional | P1 |
| `test_validate_orchestrator_event_accepts_auth_method_selection_required` | Validates acceptance of validate orchestrator event  auth method selection required | Standard scenario | functional | P1 |
| `test_validate_orchestrator_event_accepts_auth_method_selection_with_ask_user_hint` | Validates acceptance of validate orchestrator event  auth method selection with ask user hint | Standard scenario | functional | P1 |
| `test_validate_pending_auth_accepts_custom_provider_payload` | Validates acceptance of validate pending auth  custom provider payload | Standard scenario | functional | P1 |
| `test_validate_pending_auth_method_selection_accepts_custom_provider_available_method` | Validates acceptance of validate pending auth method selection  custom provider available method | Standard scenario | functional | P1 |
| `test_validate_orchestrator_event_accepts_interaction_reply_accepted` | Validates acceptance of validate orchestrator event  interaction reply accepted | Standard scenario | functional | P1 |
| `test_validate_orchestrator_event_accepts_auth_lifecycle_payloads` | Validates acceptance of validate orchestrator event  auth lifecycle payloads | Lifecycle operation | functional | P1 |
| `test_validate_rasp_event_accepts_terminal_payload` | Validates acceptance of validate rasp event  terminal payload | Standard scenario | functional | P1 |
| `test_validate_interaction_history_entry_contract` | Tests history validate interaction  entry contract | Contract verification | contract | P1 |
| `test_validate_fcmp_event_accepts_resume_ownership_fields` | Validates acceptance of validate fcmp event  resume ownership fields | Standard scenario | functional | P1 |
| `test_validate_current_run_projection_accepts_waiting_user_payload` | Validates acceptance of validate current run projection  waiting user payload | Standard scenario | functional | P1 |
| `test_validate_terminal_run_result_rejects_non_terminal_status` | Validates rejection of validate terminal run result  non terminal status | Standard scenario | functional | P0 |

**Assessment:** Comprehensive coverage with 27 test functions.

#### `test_protocol_state_alignment.py`

- **Test cases:** 2
- **Lines:** 118

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_waiting_user_protocol_events_align_with_state_transition` | Tests state of waiting user protocol events align with  transition | Standard scenario | contract | P0 |
| `test_terminal_protocol_events_align_with_state_transitions` | Tests state of terminal protocol events align with  transitions | Standard scenario | contract | P0 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_release_installer_output_contract.py`

- **Test cases:** 3
- **Lines:** 38

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_shell_installer_exposes_json_and_legacy_install_dir_output` | Tests installation shell er exposes json and legacy install dir output | Standard scenario | regression | P2 |
| `test_powershell_installer_exposes_json_and_legacy_install_dir_output` | Tests installation powershell er exposes json and legacy install dir output | Standard scenario | regression | P2 |
| `test_release_workflow_generates_integrity_manifest_for_source_package` | Tests manifest release workflow generates integrity  for source package | Standard scenario | functional | P0 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_schema_validator.py`

- **Test cases:** 16
- **Lines:** 344

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_validate_schema_valid` | Tests schema validate  valid | Standard scenario | contract | P1 |
| `test_validate_schema_invalid_type` | Tests schema validate  invalid type | Invalid input | contract | P1 |
| `test_validate_schema_missing_required` | Tests schema validate  missing required | Missing required field | contract | P1 |
| `test_get_schema_keys` | Tests key get schema s | Standard scenario | contract | P2 |
| `test_get_schema_required` | Tests schema get  required | Standard scenario | contract | P1 |
| `test_get_schema_required_empty_list` | Tests listing get schema required empty | Empty input | contract | P2 |
| `test_get_schema_required_missing_schema_file` | Tests schema get  required missing schema file | Missing required field | contract | P2 |
| `test_get_input_sources_defaults_to_file` | Tests default get input sources s to file | Default configuration | functional | P1 |
| `test_validate_inline_input_create_accepts_declared_file_source_path` | Validates acceptance of validate inline input create  declared file source path | Standard scenario | functional | P1 |
| `test_validate_inline_input_create_rejects_invalid_declared_file_source_path` | Validates rejection of validate inline input create  invalid declared file source path | Invalid input | functional | P0 |
| `test_build_input_context_mixed_file_and_inline` | Tests input build  context mixed file and inline | Standard scenario | functional | P1 |
| `test_build_input_context_prefers_declared_file_path` | Tests input build  context prefers declared file path | Standard scenario | functional | P1 |
| `test_validate_declared_file_input_paths_reports_missing_declared_path` | Tests port validate declared file input paths res missing declared path | Missing required field | functional | P1 |
| `test_validate_input_for_execution_reports_missing_required_file` | Tests port validate input for execution res missing required file | Missing required field | functional | P1 |
| `test_validate_schema_uses_assets_fallback_when_runner_schema_missing` | Tests fallback for validate schema uses assets  when runner schema missing | Missing required field | contract | P2 |
| `test_validate_schema_invalid_declared_path_falls_back_to_assets` | Tests schema validate  invalid declared path falls back to assets | Invalid input | contract | P2 |

**Assessment:** Comprehensive coverage with 16 test functions.

#### `test_services_topology_rules.py`

- **Test cases:** 1
- **Lines:** 17

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_services_root_has_no_flat_legacy_modules` | Tests services root has no flat legacy modules | Standard scenario | structural | P2 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_sqlite_async_boundary.py`

- **Test cases:** 2
- **Lines:** 58

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_migrated_sqlite_stores_do_not_import_sqlite3` | Tests port migrated sqlite stores do not im sqlite3 | Standard scenario | structural | P1 |
| `test_migrated_sqlite_store_public_methods_are_async` | Tests async boundary migrated sqlite store public methods are | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_structured_output_pipeline.py`

- **Test cases:** 4
- **Lines:** 190

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_noop_engine_passthrough_keeps_canonical_artifacts_and_payload` | Tests noop engine passthrough keeps canonical artifacts and payload | Standard scenario | functional | P1 |
| `test_codex_compat_translation_materializes_engine_specific_artifacts` | Tests codex compat translation materializes engine specific artifacts | Standard scenario | functional | P1 |
| `test_codex_payload_canonicalizer_projects_compat_final_shape_back_to_canonical` | Tests codex payload canonicalizer projects compat final shape back to canonical | Standard scenario | functional | P1 |
| `test_codex_payload_canonicalizer_projects_compat_pending_shape_back_to_canonical` | Tests pending state codex payload canonicalizer projects compat  shape back to canonical | Standard scenario | functional | P1 |

**Assessment:** Adequate coverage with 4 test functions.

#### `test_structured_trace_logging.py`

- **Test cases:** 2
- **Lines:** 52

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_log_event_uses_run_context_and_formats_kv` | Tests log event uses run context and formats kv | Standard scenario | functional | P1 |
| `test_log_event_redacts_sensitive_values` | Tests log event redacts sensitive values | Standard scenario | functional | P0 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_trust_folder_strategy_invocation_paths.py`

- **Test cases:** 1
- **Lines:** 31

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_trust_strategy_invocation_paths_cover_run_and_auth` | Tests auth trust strategy invocation paths cover run and | Standard scenario | functional | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_trust_folder_strategy_registry.py`

- **Test cases:** 2
- **Lines:** 38

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_trust_registry_resolves_codex_gemini_and_claude_strategies` | Tests trust registry resolves codex gemini and claude strategies | Standard scenario | functional | P1 |
| `test_trust_registry_noop_is_safe_for_unregistered_engine` | Tests trust registry noop is safe for unregistered engine | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

### Category: runtime_protocols

#### `test_ask_user_schema_role.py`

- **Test cases:** 1
- **Lines:** 25

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_ask_user_schema_is_repositioned_as_ui_hints_vocabulary` | Tests schema ask user  is repositioned as ui hints vocabulary | Standard scenario | contract | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_attempt_materialization_context_isolation.py`

- **Test cases:** 1
- **Lines:** 90

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_materialize_uses_attempt_meta_and_attempt_pending` | Tests pending state materialize uses attempt meta and attempt | Standard scenario | functional | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_fcmp_cursor_global_seq.py`

- **Test cases:** 2
- **Lines:** 226

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_list_event_history_rewrites_seq_to_global_monotonic` | Tests listing event history rewrites seq to global monotonic | Standard scenario | functional | P1 |
| `test_iter_sse_events_respects_global_cursor_across_attempts` | Tests iter sse events respects global cursor across attempts | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_fcmp_global_seq_persisted_files.py`

- **Test cases:** 1
- **Lines:** 138

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_fcmp_seq_is_global_and_local_seq_is_persisted` | Tests fcmp seq is global and local seq is persisted | Standard scenario | functional | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_fcmp_interaction_dedup.py`

- **Test cases:** 1
- **Lines:** 115

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_build_fcmp_events_deduplicates_waiting_prompt_and_keeps_reply_preview` | Tests preview build fcmp events deduplicates waiting prompt and keeps reply | Duplicate operation | functional | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_fcmp_lifecycle_normalization.py`

- **Test cases:** 3
- **Lines:** 39

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_conversation_lifecycle_reduces_to_state_changed_only` | Tests lifecycle of conversation  reduces to state changed only | Lifecycle operation | functional | P1 |
| `test_terminal_state_changed_carries_terminal_payload` | Tests state of terminal  changed carries terminal payload | Standard scenario | functional | P1 |
| `test_non_terminal_state_changed_omits_terminal_payload` | Tests state of non terminal  changed omits terminal payload | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_fcmp_live_journal.py`

- **Test cases:** 2
- **Lines:** 39

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_fcmp_live_journal_publish_and_replay` | Tests publishing of fcmp live journal  and replay | Standard scenario | functional | P1 |
| `test_fcmp_live_journal_replay_after_cursor` | Tests fcmp live journal replay after cursor | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_fcmp_mapping_properties.py`

- **Test cases:** 6
- **Lines:** 267

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_conversation_state_changed_events_follow_declared_mapping` | Tests state of conversation  changed events follow declared mapping | Standard scenario | property | P1 |
| `test_paired_reply_and_auto_decide_events_require_state_change_pair` | Tests state of paired reply and auto decide events require  change pair | Standard scenario | functional | P1 |
| `test_terminal_state_change_has_consistent_terminal_event` | Tests state of terminal  change has consistent terminal event | Standard scenario | functional | P1 |
| `test_waiting_user_state_requires_user_input_required_event` | Tests state of waiting user  requires user input required event | Standard scenario | functional | P1 |
| `test_fcmp_seq_is_monotonic_and_contiguous` | Tests fcmp seq is monotonic and contiguous | Standard scenario | functional | P1 |
| `test_reply_accepted_precedes_resumed_assistant_message` | Tests reply handling accepted precedes resumed assistant message | Standard scenario | functional | P1 |

**Assessment:** Adequate coverage with 6 test functions.

#### `test_file_preview_renderer.py`

- **Test cases:** 6
- **Lines:** 160

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_build_preview_payload_from_bytes_marks_binary` | Tests preview build  payload from bytes marks binary | Standard scenario | functional | P2 |
| `test_build_preview_payload_from_bytes_marks_too_large` | Tests preview build  payload from bytes marks too large | Standard scenario | functional | P2 |
| `test_build_preview_payload_from_bytes_json_pretty` | Tests preview build  payload from bytes json pretty | Standard scenario | functional | P2 |
| `test_build_preview_payload_from_bytes_jsonl_rendered` | Tests preview build  payload from bytes jsonl rendered | Standard scenario | functional | P2 |
| `test_build_preview_payload_from_bytes_code_highlight_for_structured_formats` | Tests preview build  payload from bytes code highlight for structured formats | Standard scenario | structural | P2 |
| `test_build_preview_payload_from_bytes_markdown_sanitized` | Tests preview build  payload from bytes markdown sanitized | Standard scenario | functional | P2 |

**Assessment:** Adequate coverage with 6 test functions.

#### `test_raw_row_coalescer.py`

- **Test cases:** 4
- **Lines:** 85

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_coalesce_raw_rows_merges_embedded_prefixed_json_block` | Tests merge of coalesce raw rows s embedded prefixed json block | Standard scenario | functional | P2 |
| `test_coalesce_raw_rows_does_not_break_on_brackets_inside_json_string` | Tests coalescing of raw rows does not break on brackets inside json string | Standard scenario | functional | P2 |
| `test_coalesce_raw_rows_merges_stack_frames_under_error_context` | Tests error handling for coalesce raw rows merges stack frames under  context | Error condition | functional | P1 |
| `test_coalesce_raw_rows_splits_when_error_context_starts_after_warning` | Tests error handling for coalesce raw rows splits when  context starts after warning | Error condition | functional | P1 |

**Assessment:** Adequate coverage with 4 test functions.

#### `test_runtime_adapter_no_legacy_dependencies.py`

- **Test cases:** 2
- **Lines:** 20

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_legacy_adapter_files_removed` | Tests legacy adapter files removed | Standard scenario | regression | P3 |
| `test_no_server_module_imports_legacy_base` | Tests port no server module ims legacy base | Standard scenario | structural | P3 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_runtime_auth_no_engine_coupling.py`

- **Test cases:** 1
- **Lines:** 16

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_runtime_auth_has_no_engine_imports` | Tests auth runtime  has no engine imports | Standard scenario | structural | P0 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_runtime_core_import_boundaries.py`

- **Test cases:** 1
- **Lines:** 35

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_runtime_modules_do_not_import_legacy_flat_services` | Tests port runtime modules do not im legacy flat services | Standard scenario | structural | P0 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_runtime_event_ordering_contract_rules.py`

- **Test cases:** 4
- **Lines:** 51

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_runtime_event_ordering_contract_declares_auth_and_terminal_precedence` | Tests ordering of runtime event  contract declares auth and terminal precedence | Contract verification | contract | P1 |
| `test_runtime_event_ordering_contract_declares_projection_gate` | Tests ordering of runtime event  contract declares projection gate | Contract verification | contract | P1 |
| `test_runtime_event_ordering_contract_declares_single_method_busy_recovery` | Tests recovery of runtime event ordering contract declares single method busy | Recovery scenario | contract | P1 |
| `test_runtime_event_ordering_contract_declares_replay_rules` | Tests ordering of runtime event  contract declares replay rules | Contract verification | contract | P1 |

**Assessment:** Adequate coverage with 4 test functions.

#### `test_runtime_event_ordering_contract_schema.py`

- **Test cases:** 3
- **Lines:** 33

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_runtime_event_ordering_contract_exists_and_loads` | Tests loading of runtime event ordering contract exists and | Contract verification | contract | P1 |
| `test_runtime_event_ordering_contract_declares_lifecycle_normalization` | Tests lifecycle of runtime event ordering contract declares  normalization | Contract verification | contract | P1 |
| `test_runtime_event_ordering_contract_declares_buffer_policies` | Tests ordering of runtime event  contract declares buffer policies | Contract verification | contract | P1 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_runtime_event_ordering_gate.py`

- **Test cases:** 2
- **Lines:** 49

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_ordering_gate_buffers_until_prerequisite_publish_id_is_seen` | Tests ordering of gate buffers until prerequisite publish id is seen | Standard scenario | functional | P1 |
| `test_ordering_gate_publishes_ready_candidate_immediately` | Tests ordering of gate publishes ready candidate immediately | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_runtime_event_protocol.py`

- **Test cases:** 33
- **Lines:** 1358

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_fcmp_suppresses_duplicate_raw_echo_blocks` | Tests fcmp suppresses duplicate raw echo blocks | Duplicate operation | functional | P2 |
| `test_build_rasp_events_coalesces_large_stderr_bursts` | Tests coalescing of build rasp events s large stderr bursts | Standard scenario | functional | P2 |
| `test_build_rasp_events_coalesces_pretty_json_blocks_below_min_threshold` | Tests coalescing of build rasp events s pretty json blocks below min threshold | Standard scenario | functional | P2 |
| `test_read_jsonl_recovers_concatenated_json_objects_on_single_line` | Tests read jsonl recovers concatenated json objects on single line | Standard scenario | functional | P2 |
| `test_codex_parser_uses_pty_fallback_when_stdout_incomplete` | Tests fallback for codex parser uses pty  when stdout incomplete | Fallback path | functional | P2 |
| `test_process_events_promote_to_final_on_turn_completed` | Tests process events promote to final on turn completed | Standard scenario | functional | P2 |
| `test_turn_markers_are_rasp_only_and_not_mapped_to_fcmp` | Tests turn markers are rasp only and not mapped to fcmp | Standard scenario | functional | P2 |
| `test_no_fallback_final_on_failed_without_turn_completed` | Tests fallback for no  final on failed without turn completed | Fallback path | structural | P2 |
| `test_completion_conflict_maps_to_failed_conversation` | Tests conflict handling for completion  maps to failed conversation | Resource conflict | functional | P1 |
| `test_build_rasp_events_delegates_parsing_to_adapter` | Tests build rasp events delegates parsing to adapter | Standard scenario | functional | P2 |
| `test_build_rasp_events_emits_parsed_json_from_structured_payload` | Tests emission of build rasp events s parsed json from structured payload | Standard scenario | structural | P2 |
| `test_soft_completion_reason_and_warning_propagate_to_fcmp` | Tests soft completion reason and warning propagate to fcmp | Standard scenario | functional | P2 |
| `test_max_attempt_exceeded_maps_to_failed_conversation` | Tests max attempt exceeded maps to failed conversation | Standard scenario | functional | P2 |
| `test_completed_completion_does_not_override_failed_terminal_status` | Tests terminal state completed completion does not override failed  status | Override behavior | functional | P2 |
| `test_fcmp_emits_state_changed_for_waiting_user` | Tests state of fcmp emits  changed for waiting user | Standard scenario | functional | P2 |
| `test_fcmp_assistant_final_projects_pending_display_text` | Tests pending state fcmp assistant final projects  display text | Standard scenario | functional | P2 |
| `test_fcmp_assistant_final_projects_final_branch_markdown` | Tests fcmp assistant final projects final branch markdown | Standard scenario | functional | P2 |
| `test_fcmp_emits_auth_required_and_waiting_auth_transition` | Tests transition for fcmp emits auth required and waiting auth | Standard scenario | functional | P2 |
| `test_fcmp_emits_auth_required_for_custom_provider_challenge` | Tests auth fcmp emits  required for custom provider challenge | Standard scenario | functional | P2 |
| `test_fcmp_auth_required_prefers_pending_auth_provider_when_orchestrator_payload_is_missing_it` | Tests auth fcmp  required prefers pending auth provider when orchestrator payload is missing it | Missing required field | functional | P1 |
| `test_fcmp_emits_auth_required_for_method_selection` | Tests auth fcmp emits  required for method selection | Standard scenario | functional | P2 |
| `test_fcmp_waiting_auth_suppresses_process_exit_failed_event` | Tests auth fcmp waiting  suppresses process exit failed event | Standard scenario | functional | P2 |
| `test_fcmp_emits_auth_completion_transition` | Tests transition for fcmp emits auth completion | Standard scenario | functional | P2 |
| `test_translate_orchestrator_interaction_reply_accepted_to_fcmp_pair` | Tests interaction translate orchestrator  reply accepted to fcmp pair | Standard scenario | functional | P2 |
| `test_translate_orchestrator_terminal_failed_carries_error_summary` | Tests error handling for translate orchestrator terminal failed carries  summary | Error condition | functional | P1 |
| `test_build_fcmp_events_uses_orchestrator_terminal_summary` | Tests terminal state build fcmp events uses orchestrator  summary | Standard scenario | functional | P2 |
| `test_translate_orchestrator_error_run_failed_maps_to_diagnostic_warning` | Tests error handling for translate orchestrator  run failed maps to diagnostic warning | Error condition | functional | P1 |
| `test_translate_orchestrator_output_repair_events_do_not_map_to_fcmp` | Tests output translate orchestrator  repair events do not map to fcmp | Standard scenario | functional | P1 |
| `test_build_fcmp_events_explicitly_ignores_output_repair_orchestrator_rows` | Tests output build fcmp events explicitly ignores  repair orchestrator rows | Standard scenario | functional | P1 |
| `test_fcmp_maps_auth_session_busy_to_diagnostic_warning` | Tests session fcmp maps auth  busy to diagnostic warning | Standard scenario | functional | P1 |
| ... (3 more tests) | See source file | — | — | — |

**Assessment:** Comprehensive coverage with 33 test functions.

#### `test_runtime_event_protocol_fixtures.py`

- **Test cases:** 1
- **Lines:** 105

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_runtime_protocol_parsers_and_completion_state` | Tests state of runtime protocol parsers and completion | Standard scenario | contract | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_runtime_file_contract_scan.py`

- **Test cases:** 1
- **Lines:** 53

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_runtime_file_contract_scan_blocks_legacy_paths` | Tests scanning of runtime file contract  blocks legacy paths | Contract verification | contract | P0 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_runtime_no_orchestration_imports.py`

- **Test cases:** 1
- **Lines:** 24

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_runtime_modules_do_not_import_orchestration` | Tests port runtime modules do not im orchestration | Standard scenario | structural | P0 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_runtime_observability_port_injection.py`

- **Test cases:** 2
- **Lines:** 140

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_runtime_observability_ports_are_injected` | Tests port runtime observability s are injected | Standard scenario | functional | P1 |
| `test_run_read_facade_result_requires_terminal_projection` | Tests terminal state run read facade result requires  projection | Standard scenario | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_runtime_profile.py`

- **Test cases:** 2
- **Lines:** 48

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_runtime_profile_container_defaults` | Tests default runtime profile container s | Default configuration | functional | P1 |
| `test_runtime_profile_local_env_overrides` | Tests runtime profile local env overrides | Override behavior | functional | P1 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_runtime_protocol_parser_resolver_port.py`

- **Test cases:** 1
- **Lines:** 39

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_runtime_protocol_uses_injected_parser_resolver` | Tests runtime protocol uses injected parser resolver | Standard scenario | contract | P1 |

**Assessment:** Sparse coverage with 1 test function.

#### `test_session_invariant_contract.py`

- **Test cases:** 6
- **Lines:** 128

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_invariant_contract_file_exists_and_loadable` | Tests invariant contract file exists and loadable | Contract verification | contract | P1 |
| `test_canonical_states_and_terminals_match_session_statechart` | Tests state of canonical s and terminals match session statechart | Standard scenario | functional | P1 |
| `test_transition_set_is_exactly_equal_to_session_statechart` | Tests state of transition set is exactly equal to session chart | Standard scenario | functional | P1 |
| `test_fcmp_mapping_references_declared_state_space` | Tests state of fcmp mapping references declared  space | Standard scenario | property | P1 |
| `test_paired_event_rules_point_to_state_changed_rows` | Tests state of paired event rules point to  changed rows | Standard scenario | functional | P1 |
| `test_ordering_rules_are_complete_for_model_tests` | Tests ordering of rules are complete for model tests | Standard scenario | functional | P1 |

**Assessment:** Adequate coverage with 6 test functions.

#### `test_session_state_model_properties.py`

- **Test cases:** 7
- **Lines:** 104

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_transition_keys_are_unique_and_match_contract` | Tests transition for keys are unique and match contract | Contract verification | contract | P1 |
| `test_all_declared_states_are_reachable_from_initial_state` | Tests state of all declared s are reachable from initial state | Standard scenario | functional | P1 |
| `test_terminal_states_have_no_outgoing_edges` | Tests state of terminal s have no outgoing edges | Edge case | structural | P1 |
| `test_waiting_user_outgoing_events_are_explicitly_bounded` | Tests waiting user outgoing events are explicitly bounded | Standard scenario | functional | P1 |
| `test_model_and_implementation_transition_indices_are_equivalent` | Tests transition for model and implementation  indices are equivalent | Standard scenario | functional | P1 |
| `test_finite_event_sequence_enumeration_matches_implementation_model` | Tests model finite event sequence enumeration matches implementation | Standard scenario | functional | P1 |
| `test_recovery_event_helper_matches_model_edges` | Tests recovery of event helper matches model edges | Recovery scenario | functional | P1 |

**Assessment:** Adequate coverage with 7 test functions.

#### `test_session_statechart_contract.py`

- **Test cases:** 4
- **Lines:** 62

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_transition_keys_are_unique` | Tests transition for keys are unique | Standard scenario | functional | P1 |
| `test_state_reachability_from_queued` | Tests state of reachability from queued | Standard scenario | functional | P1 |
| `test_terminal_states_are_mutually_exclusive_and_have_no_outgoing_edges` | Tests state of terminal s are mutually exclusive and have no outgoing edges | Edge case | structural | P1 |
| `test_waiting_recovery_event_contract` | Tests recovery of waiting  event contract | Recovery scenario | contract | P1 |

**Assessment:** Adequate coverage with 4 test functions.

#### `test_session_timeout.py`

- **Test cases:** 3
- **Lines:** 22

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_resolve_interactive_reply_timeout_default` | Tests timeout for resolve interactive reply  default | Timeout scenario | functional | P1 |
| `test_resolve_interactive_reply_timeout_prefers_new_key` | Tests timeout for resolve interactive reply  prefers new key | Timeout scenario | functional | P1 |
| `test_resolve_interactive_reply_timeout_accepts_zero` | Validates acceptance of resolve interactive reply timeout  zero | Timeout scenario | functional | P1 |

**Assessment:** Minimal coverage with 3 test functions.

### Category: skill_management

#### `test_skill_browser.py`

- **Test cases:** 6
- **Lines:** 93

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_list_skill_entries_returns_structure` | Tests return value for list skill entries  structure | Standard scenario | structural | P2 |
| `test_resolve_skill_file_path_enforces_root` | Tests enforcement of resolve skill file path  root | Standard scenario | functional | P1 |
| `test_build_preview_payload_text_binary_and_size` | Tests preview build  payload text binary and size | Standard scenario | functional | P2 |
| `test_build_preview_payload_gb18030_markdown_is_text` | Tests preview build  payload gb18030 markdown is text | Standard scenario | functional | P2 |
| `test_build_preview_payload_json_pretty` | Tests preview build  payload json pretty | Standard scenario | functional | P2 |
| `test_build_preview_payload_jsonl_with_line_number_rendering` | Tests preview build  payload jsonl with line number rendering | Standard scenario | functional | P2 |

**Assessment:** Adequate coverage with 6 test functions.

#### `test_skill_install_store.py`

- **Test cases:** 3
- **Lines:** 56

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_skill_install_store_lifecycle` | Tests lifecycle of skill install store | Lifecycle operation | functional | P1 |
| `test_skill_install_store_failed` | Tests installation skill  store failed | Standard scenario | functional | P1 |
| `test_skill_install_store_list_order` | Tests installation skill  store list order | Standard scenario | functional | P2 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_skill_package_manager.py`

- **Test cases:** 10
- **Lines:** 341

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_install_new_skill` | Tests installation new skill | Standard scenario | functional | P0 |
| `test_install_strips_git_directory_and_preserves_non_git_hidden_entries` | Tests installation strips git directory and preserves non git hidden entries | Standard scenario | functional | P1 |
| `test_update_archives_old_version` | Tests update archives old version | Standard scenario | functional | P1 |
| `test_update_strips_git_file_in_uploaded_package` | Tests update strips git file in uploaded package | Standard scenario | functional | P2 |
| `test_reject_downgrade` | Tests reject downgrade | Standard scenario | functional | P1 |
| `test_reject_missing_required_files` | Tests reject missing required files | Missing required field | functional | P1 |
| `test_reject_identity_mismatch` | Tests reject identity mismatch | Standard scenario | functional | P1 |
| `test_reject_existing_archive_path` | Tests reject existing archive path | Standard scenario | functional | P2 |
| `test_rolls_back_when_swap_fails` | Tests rolls back when swap fails | Standard scenario | functional | P1 |
| `test_invalid_existing_directory_is_quarantined_and_reinstalled` | Tests installation invalid existing directory is quarantined and reed | Invalid input | functional | P1 |

**Assessment:** Adequate coverage with 10 test functions.

#### `test_skill_package_validator.py`

- **Test cases:** 21
- **Lines:** 434

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_rejects_multiple_top_levels` | Validates rejection of multiple top levels | Standard scenario | functional | P1 |
| `test_rejects_zip_slip_on_extract` | Validates rejection of zip slip on extract | Standard scenario | security | P0 |
| `test_rejects_identity_mismatch` | Validates rejection of identity mismatch | Standard scenario | functional | P1 |
| `test_accepts_valid_temp_skill` | Validates acceptance of valid temp skill | Standard scenario | functional | P1 |
| `test_accepts_valid_temp_skill_without_runner_artifacts` | Validates acceptance of valid temp skill without runner artifacts | Standard scenario | functional | P2 |
| `test_accepts_result_json_filename_in_runner_entrypoint` | Validates acceptance of result json filename in runner entrypoint | Standard scenario | functional | P2 |
| `test_accepts_valid_temp_skill_without_engines` | Validates acceptance of valid temp skill without engines | Standard scenario | functional | P2 |
| `test_rejects_missing_execution_modes` | Validates rejection of missing execution modes | Missing required field | functional | P1 |
| `test_rejects_overlapping_engines_and_unsupported_engines` | Validates rejection of overlapping engines and unsupported engines | Standard scenario | functional | P1 |
| `test_rejects_empty_effective_engines_when_engines_omitted` | Validates rejection of empty effective engines when engines omitted | Empty input | functional | P2 |
| `test_rejects_legacy_unsupport_engine_field` | Validates rejection of legacy unsupport engine field | Standard scenario | regression | P2 |
| `test_rejects_invalid_input_schema_extension_key` | Validates rejection of invalid input schema extension key | Invalid input | contract | P1 |
| `test_rejects_invalid_parameter_schema_shape` | Validates rejection of invalid parameter schema shape | Invalid input | contract | P1 |
| `test_rejects_invalid_output_schema_artifact_marker` | Validates rejection of invalid output schema artifact marker | Invalid input | contract | P1 |
| `test_accepts_runner_runtime_default_options_object` | Validates acceptance of runner runtime default options object | Default configuration | functional | P2 |
| `test_rejects_runner_runtime_default_options_non_object` | Validates rejection of runner runtime default options non object | Default configuration | functional | P2 |
| `test_accepts_schema_fallback_when_runner_declaration_missing` | Validates acceptance of schema fallback when runner declaration missing | Missing required field | contract | P1 |
| `test_accepts_schema_fallback_when_runner_declaration_invalid` | Validates acceptance of schema fallback when runner declaration invalid | Invalid input | contract | P1 |
| `test_rejects_schema_when_declaration_invalid_and_fallback_missing` | Validates rejection of schema when declaration invalid and fallback missing | Missing required field | contract | P1 |
| `test_accepts_valid_max_attempt` | Validates acceptance of valid max attempt | Standard scenario | functional | P1 |
| `test_rejects_invalid_max_attempt` | Validates rejection of invalid max attempt | Invalid input | functional | P1 |

**Assessment:** Comprehensive coverage with 21 test functions.

#### `test_skill_packages_router.py`

- **Test cases:** 4
- **Lines:** 94

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_install_skill_package_route` | Tests route install skill package | Standard scenario | functional | P1 |
| `test_install_skill_package_rejects_empty_file` | Validates rejection of install skill package  empty file | Empty input | functional | P1 |
| `test_get_install_status` | Tests installation get  status | Standard scenario | functional | P2 |
| `test_get_install_status_not_found` | Tests installation get  status not found | Resource not found | functional | P2 |

**Assessment:** Adequate coverage with 4 test functions.

#### `test_skill_patch_output_schema.py`

- **Test cases:** 7
- **Lines:** 158

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_build_output_contract_details_markdown_simple_object` | Tests detail view build output contract s markdown simple object | Contract verification | contract | P1 |
| `test_build_output_contract_details_markdown_handles_anyof_object_or_null` | Tests handling of build output contract details markdown  anyof object or null | Contract verification | contract | P1 |
| `test_build_output_contract_details_markdown_handles_array_object_description` | Tests handling of build output contract details markdown  array object description | Contract verification | contract | P1 |
| `test_build_output_contract_details_markdown_artifact_field_description_and_skeleton` | Tests detail view build output contract s markdown artifact field description and skeleton | Contract verification | contract | P1 |
| `test_build_output_contract_details_markdown_array_item_count_constraints_and_valid_skeleton` | Tests detail view build output contract s markdown array item count constraints and valid skeleton | Contract verification | contract | P1 |
| `test_build_output_contract_details_markdown_uses_static_template_loader` | Tests detail view build output contract s markdown uses static template loader | Contract verification | contract | P2 |
| `test_build_output_contract_details_markdown_places_final_before_pending` | Tests detail view build output contract s markdown places final before pending | Contract verification | contract | P1 |

**Assessment:** Adequate coverage with 7 test functions.

#### `test_skill_patcher.py`

- **Test cases:** 5
- **Lines:** 133

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_generate_patch_content_auto_mode_forbids_questions_and_has_artifact_redirect` | Tests auto mode generate patch content  mode forbids questions and has artifact redirect | Standard scenario | functional | P0 |
| `test_generate_patch_content_interactive_mode_uses_json_union_contract` | Tests patching generate  content interactive mode uses json union contract | Contract verification | contract | P0 |
| `test_patch_skill_md_is_idempotent` | Tests idempotent behavior patch skill md is | Standard scenario | functional | P1 |
| `test_patch_skill_md_without_output_schema_skips_dynamic_schema_section` | Tests patching skill md without output schema skips dynamic schema section | Standard scenario | contract | P2 |
| `test_patch_skill_md_missing_template_fails_fast` | Tests patching skill md missing template fails fast | Missing required field | functional | P1 |

**Assessment:** Adequate coverage with 5 test functions.

#### `test_skill_patcher_pipeline.py`

- **Test cases:** 6
- **Lines:** 142

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_build_patch_plan_fixed_only_auto_mode` | Tests auto mode build patch plan fixed only  mode | Standard scenario | functional | P1 |
| `test_build_patch_plan_with_artifact_patch` | Tests patching build  plan with artifact patch | Standard scenario | functional | P1 |
| `test_build_patch_plan_with_output_schema_and_interactive_mode` | Tests patching build  plan with output schema and interactive mode | Standard scenario | contract | P1 |
| `test_patch_plan_order_is_stable_for_all_modules` | Tests patching plan order is stable for all modules | Standard scenario | structural | P1 |
| `test_patch_skill_md_is_idempotent_with_pipeline` | Tests idempotent behavior patch skill md is  with pipeline | Standard scenario | functional | P1 |
| `test_build_patch_plan_missing_template_fails_fast` | Tests patching build  plan missing template fails fast | Missing required field | functional | P1 |

**Assessment:** Adequate coverage with 6 test functions.

#### `test_skill_registry.py`

- **Test cases:** 7
- **Lines:** 262

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_scan_artifacts_from_output_schema` | Tests scanning of artifacts from output schema | Standard scenario | contract | P1 |
| `test_scan_skips_excluded_and_invalid_dirs` | Tests scanning of skips excluded and invalid dirs | Invalid input | functional | P2 |
| `test_scan_missing_execution_modes_falls_back_to_auto` | Tests scanning of missing execution modes falls back to auto | Missing required field | functional | P1 |
| `test_scan_missing_engines_defaults_to_all_supported` | Tests default scan missing engines s to all supported | Missing required field | functional | P1 |
| `test_scan_loads_manifest_max_attempt` | Tests loading of scan  manifest max attempt | Standard scenario | functional | P2 |
| `test_scan_skills_falls_back_to_builtin_when_user_dir_empty` | Tests scanning of skills falls back to builtin when user dir empty | Empty input | functional | P1 |
| `test_scan_skills_user_overrides_builtin_on_same_skill_id` | Tests scanning of skills user overrides builtin on same skill id | Override behavior | functional | P1 |

**Assessment:** Adequate coverage with 7 test functions.

#### `test_skill_runner_uninstall_scripts.py`

- **Test cases:** 8
- **Lines:** 272

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_skill_runnerctl_wrappers_and_uninstall_scripts_expose_contract_fields` | Tests installation skill runnerctl wrappers and un scripts expose contract fields | Contract verification | contract | P1 |
| `test_shell_ctl_wrapper_defaults_data_dir_to_local_root` | Tests default shell ctl wrapper s data dir to local root | Default configuration | regression | P2 |
| `test_uninstall_default_mode_keeps_data_and_agent_home` | Tests default uninstall  mode keeps data and agent home | Default configuration | functional | P1 |
| `test_uninstall_continues_cleanup_when_down_fails` | Tests installation un continues cleanup when down fails | Standard scenario | functional | P1 |
| `test_uninstall_clear_data_mode` | Tests installation un clear data mode | Standard scenario | functional | P2 |
| `test_uninstall_clear_agent_home_mode` | Tests installation un clear agent home mode | Standard scenario | functional | P2 |
| `test_uninstall_clear_data_and_agent_home_attempts_remove_local_root` | Tests installation un clear data and agent home attempts remove local root | Standard scenario | functional | P2 |
| `test_uninstall_reports_failed_paths_and_non_zero_exit_on_delete_failure` | Tests failure handling for uninstall reports failed paths and non zero exit on delete | Failure scenario | functional | P1 |

**Assessment:** Adequate coverage with 8 test functions.

#### `test_skill_runnerctl_bootstrap.py`

- **Test cases:** 2
- **Lines:** 85

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_bootstrap_returns_continue_result_for_partial_failure` | Tests return value for bootstrap  continue result for partial failure | Failure scenario | functional | P1 |
| `test_bootstrap_forwards_explicit_engine_subset` | Tests bootstrap forwards explicit engine subset | Standard scenario | functional | P2 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_skill_runnerctl_port_policy.py`

- **Test cases:** 5
- **Lines:** 144

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_parser_defaults_use_service_port_9813` | Tests default parser s use service port 9813 | Default configuration | functional | P2 |
| `test_parser_defaults_use_plugin_port_and_fallback_from_env` | Tests fallback for parser defaults use plugin port and  from env | Fallback path | functional | P2 |
| `test_collect_local_status_uses_lightweight_probe` | Tests probe collect local status uses lightweight | Standard scenario | functional | P2 |
| `test_cmd_up_local_uses_fallback_port_when_requested_port_unavailable` | Tests fallback for cmd up local uses  port when requested port unavailable | Fallback path | functional | P1 |
| `test_cmd_up_local_fails_when_no_port_available` | Tests port cmd up local fails when no  available | Standard scenario | structural | P1 |

**Assessment:** Adequate coverage with 5 test functions.

#### `test_skill_runnerctl_preflight.py`

- **Test cases:** 9
- **Lines:** 290

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_preflight_passes_when_environment_ready` | Tests preflight checks passes when environment ready | Standard scenario | functional | P1 |
| `test_preflight_claude_sandbox_dependency_warning_is_non_blocking` | Tests preflight checks claude sandbox dependency warning is non blocking | Standard scenario | functional | P2 |
| `test_preflight_missing_dependency_returns_exit_2` | Tests return value for preflight missing dependency  exit 2 | Missing required field | functional | P1 |
| `test_preflight_port_unavailable_returns_exit_1` | Tests return value for preflight port unavailable  exit 1 | Standard scenario | functional | P1 |
| `test_preflight_partial_failure_report_is_warning` | Tests failure handling for preflight partial  report is warning | Failure scenario | functional | P1 |
| `test_preflight_stale_state_file_is_warning` | Tests state of preflight stale  file is warning | Stale data | functional | P2 |
| `test_preflight_missing_integrity_manifest_returns_exit_2` | Tests return value for preflight missing integrity manifest  exit 2 | Missing required field | functional | P0 |
| `test_preflight_integrity_missing_file_returns_exit_2` | Tests return value for preflight integrity missing file  exit 2 | Missing required field | functional | P0 |
| `test_preflight_integrity_hash_mismatch_returns_exit_2` | Tests return value for preflight integrity hash mismatch  exit 2 | Standard scenario | functional | P0 |

**Assessment:** Adequate coverage with 9 test functions.

### Category: structured_output

#### `test_agent_output_protocol_contract.py`

- **Test cases:** 11
- **Lines:** 114

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_agent_output_protocol_contract_exists_and_loads` | Tests loading of agent output protocol contract exists and | Contract verification | contract | P1 |
| `test_auto_final_contract_requires_explicit_done_marker` | Tests auto mode final contract requires explicit done marker | Contract verification | contract | P1 |
| `test_interactive_union_contract_has_exactly_final_and_pending_branches` | Tests pending state interactive union contract has exactly final and  branches | Contract verification | contract | P1 |
| `test_pending_branch_requires_false_done_marker_message_and_ui_hints` | Tests pending state branch requires false done marker message and ui hints | Standard scenario | functional | P1 |
| `test_repair_loop_is_attempt_local_and_bounded` | Tests repair loop is attempt local and bounded | Standard scenario | functional | P1 |
| `test_attempt_round_model_distinguishes_attempt_and_internal_round` | Tests model attempt round  distinguishes attempt and internal round | Standard scenario | functional | P1 |
| `test_repair_executor_ownership_assigns_single_orchestrator_owner` | Tests repair executor ownership assigns single orchestrator owner | Standard scenario | functional | P1 |
| `test_repair_pipeline_order_unifies_repair_and_legacy_fallbacks` | Tests fallback for repair pipeline order unifies repair and legacy s | Fallback path | regression | P1 |
| `test_repair_event_requirements_define_internal_diagnostic_event_surface` | Tests repair event requirements define internal diagnostic event surface | Standard scenario | functional | P1 |
| `test_repair_audit_requirements_define_future_canonical_history_file` | Tests audit repair  requirements define future canonical history file | Standard scenario | functional | P1 |
| `test_legacy_deprecations_include_ask_user_yaml` | Tests legacy deprecations include ask user yaml | Standard scenario | regression | P1 |

**Assessment:** Comprehensive coverage with 11 test functions.

### Category: ui/routes

#### `test_jobs_interaction_routes.py`

- **Test cases:** 12
- **Lines:** 524

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_get_interaction_pending_returns_pending` | Tests return value for get interaction pending  pending | Standard scenario | functional | P2 |
| `test_get_run_status_exposes_waiting_user_pending_fields` | Tests pending state get run status exposes waiting user  fields | Standard scenario | functional | P2 |
| `test_get_run_status_exposes_interactive_auto_reply_fields` | Tests reply handling get run status exposes interactive auto  fields | Standard scenario | functional | P2 |
| `test_create_run_normalizes_non_session_dual_mode_skill_to_auto` | Tests session create run normalizes non  dual mode skill to auto | Standard scenario | functional | P2 |
| `test_create_run_normalizes_non_session_interactive_only_skill_to_zero_timeout` | Tests timeout for create run normalizes non session interactive only skill to zero | Timeout scenario | functional | P1 |
| `test_reply_interaction_accepts_and_transitions_to_queued` | Validates acceptance of reply interaction  and transitions to queued | Standard scenario | functional | P2 |
| `test_reply_interaction_accepts_free_text_for_all_supported_kinds` | Validates acceptance of reply interaction  free text for all supported kinds | Standard scenario | functional | P2 |
| `test_reply_interaction_appends_response_preview_for_open_text` | Tests preview reply interaction appends response  for open text | Standard scenario | functional | P2 |
| `test_reply_interaction_rejects_stale_interaction` | Validates rejection of reply interaction  stale interaction | Stale data | functional | P2 |
| `test_interaction_endpoints_require_interactive_mode` | Tests endpoint interaction s require interactive mode | Standard scenario | functional | P2 |
| `test_cancel_run_running_accepts` | Validates acceptance of cancel run running | Cancellation request | functional | P0 |
| `test_cancel_run_terminal_is_idempotent` | Tests cancellation run terminal is idempotent | Cancellation request | functional | P0 |

**Assessment:** Comprehensive coverage with 12 test functions.

#### `test_management_routes.py`

- **Test cases:** 26
- **Lines:** 1106

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_management_skills_list_and_detail` | Tests listing management skills  and detail | Standard scenario | functional | P2 |
| `test_management_runtime_options_endpoint` | Tests endpoint management runtime options | Standard scenario | functional | P2 |
| `test_management_engine_custom_provider_crud` | Tests management engine custom provider crud | Standard scenario | functional | P1 |
| `test_management_skills_list_marks_builtin_skill` | Tests listing management skills  marks builtin skill | Standard scenario | functional | P2 |
| `test_management_skill_schemas_endpoint` | Tests endpoint management skill schemas | Standard scenario | contract | P1 |
| `test_management_engines_list_and_detail` | Tests listing management engines  and detail | Standard scenario | functional | P2 |
| `test_management_engine_auth_import_spec_route` | Tests auth management engine  import spec route | Standard scenario | structural | P2 |
| `test_management_engine_auth_import_submit_route` | Tests auth management engine  import submit route | Standard scenario | structural | P2 |
| `test_management_run_state_includes_pending_and_interaction_count` | Tests state of management run  includes pending and interaction count | Standard scenario | functional | P2 |
| `test_management_run_files_and_preview` | Tests preview management run files and | Standard scenario | functional | P2 |
| `test_management_run_events_stream` | Tests stream handling for management run events | Standard scenario | functional | P1 |
| `test_management_run_events_history_delegate` | Tests history management run events  delegate | Standard scenario | functional | P2 |
| `test_management_run_chat_history_delegate` | Tests history management run chat  delegate | Standard scenario | functional | P2 |
| `test_management_run_log_range_delegate` | Tests range management run log  delegate | Standard scenario | functional | P2 |
| `test_management_run_protocol_rebuild_route` | Tests route management run protocol rebuild | Standard scenario | contract | P1 |
| `test_management_run_pending_reply_cancel_delegate_to_jobs` | Tests cancellation management run pending reply  delegate to jobs | Cancellation request | functional | P1 |
| `test_management_reset_data_rejects_invalid_confirmation` | Validates rejection of management reset data  invalid confirmation | Invalid input | functional | P1 |
| `test_management_reset_data_dry_run` | Tests reset management  data dry run | Standard scenario | functional | P2 |
| `test_management_get_system_settings` | Tests settings management get system | Standard scenario | functional | P2 |
| `test_management_query_system_logs` | Tests query management  system logs | Standard scenario | functional | P2 |
| `test_management_query_system_logs_rejects_invalid_source` | Validates rejection of management query system logs  invalid source | Invalid input | functional | P1 |
| `test_management_query_system_logs_rejects_invalid_level` | Validates rejection of management query system logs  invalid level | Invalid input | functional | P1 |
| `test_management_update_system_settings` | Tests settings management update system | Standard scenario | functional | P2 |
| `test_management_update_system_settings_rejects_invalid_payload` | Validates rejection of management update system settings  invalid payload | Invalid input | functional | P1 |
| `test_management_reset_data_execute_with_include_flags` | Tests reset management  data execute with include flags | Standard scenario | functional | P2 |
| `test_management_reset_data_normalizes_engine_auth_flag_when_feature_disabled` | Tests auth management reset data normalizes engine  flag when feature disabled | Standard scenario | functional | P2 |

**Assessment:** Comprehensive coverage with 26 test functions.

#### `test_management_routes_protocol_history.py`

- **Test cases:** 3
- **Lines:** 128

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_management_protocol_history_streams` | Tests stream handling for management protocol history s | Standard scenario | contract | P1 |
| `test_management_protocol_history_filters` | Tests filtering management protocol history s | Standard scenario | contract | P1 |
| `test_management_protocol_history_rejects_invalid_stream` | Validates rejection of management protocol history  invalid stream | Invalid input | contract | P1 |

**Assessment:** Minimal coverage with 3 test functions.

#### `test_management_routes_timeline_history.py`

- **Test cases:** 2
- **Lines:** 92

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_management_timeline_history_success` | Tests timeline management  history success | Success scenario | functional | P1 |
| `test_management_timeline_history_request_or_run_not_found` | Tests timeline management  history request or run not found | Resource not found | functional | P2 |

**Assessment:** Minimal coverage with 2 test functions.

#### `test_ui_auth.py`

- **Test cases:** 4
- **Lines:** 37

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_validate_ui_basic_auth_config_disabled` | Tests auth validate ui basic  config disabled | Standard scenario | functional | P2 |
| `test_validate_ui_basic_auth_config_enabled_requires_credentials` | Tests auth validate ui basic  config enabled requires credentials | Standard scenario | functional | P1 |
| `test_validate_ui_basic_auth_config_enabled_accepts_credentials` | Validates acceptance of validate ui basic auth config enabled  credentials | Standard scenario | functional | P2 |
| `test_verify_ui_basic_auth_header` | Tests auth verify ui basic  header | Standard scenario | functional | P1 |

**Assessment:** Adequate coverage with 4 test functions.

#### `test_ui_routes.py`

- **Test cases:** 48
- **Lines:** 1698

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_build_engine_ui_metadata_prefers_engine_specific_auth_label` | Tests auth build engine ui metadata prefers engine specific  label | Standard scenario | functional | P2 |
| `test_ui_index_available_when_auth_disabled` | Tests auth ui index available when  disabled | Standard scenario | functional | P2 |
| `test_ui_language_query_sets_cookie_and_preserves_query` | Tests query ui language  sets cookie and preserves query | Standard scenario | functional | P2 |
| `test_ui_index_links_to_settings_and_hides_danger_zone` | Tests settings ui index links to  and hides danger zone | Standard scenario | functional | P2 |
| `test_ui_index_renders_engine_status_indicator_from_cache` | Tests rendering of ui index  engine status indicator from cache | Standard scenario | functional | P2 |
| `test_ui_settings_contains_logging_and_reset_controls` | Tests settings ui  contains logging and reset controls | Standard scenario | functional | P2 |
| `test_ui_settings_shows_engine_auth_reset_toggle_when_feature_enabled` | Tests auth ui settings shows engine  reset toggle when feature enabled | Standard scenario | functional | P2 |
| `test_ui_auth_protects_ui_and_skill_package_routes` | Tests auth ui  protects ui and skill package routes | Standard scenario | functional | P2 |
| `test_run_detail_template_keeps_stream_open_until_terminal_chat_event` | Tests stream handling for run detail template keeps  open until terminal chat event | Standard scenario | functional | P2 |
| `test_run_detail_template_catches_up_history_for_waiting_and_terminal_states` | Tests state of run detail template catches up history for waiting and terminal s | Standard scenario | functional | P2 |
| `test_ui_core_pages_use_shared_page_header_partial` | Tests ui core pages use shared page header partial | Standard scenario | functional | P2 |
| `test_page_header_partial_uses_standard_secondary_back_button` | Tests page header partial uses standard secondary back button | Standard scenario | functional | P2 |
| `test_design_system_enforces_non_wrapping_buttons_and_table_actions` | Tests enforcement of design system  non wrapping buttons and table actions | Standard scenario | functional | P2 |
| `test_ui_skills_table_highlight` | Tests ui skills table highlight | Standard scenario | functional | P2 |
| `test_ui_install_status_succeeded_refreshes_table` | Tests installation ui  status succeeded refreshes table | Standard scenario | functional | P2 |
| `test_ui_skill_detail_and_text_preview` | Tests preview ui skill detail and text | Standard scenario | functional | P2 |
| `test_ui_skill_preview_binary_and_large_and_invalid_path` | Tests preview ui skill  binary and large and invalid path | Invalid input | functional | P1 |
| `test_ui_engines_page` | Tests ui engines page | Standard scenario | functional | P2 |
| `test_ui_engines_page_hides_terminal_panel_when_ttyd_missing` | Tests terminal state ui engines page hides  panel when ttyd missing | Missing required field | functional | P1 |
| `test_ui_engines_page_exposes_custom_provider_tui_dialog_markup` | Tests ui engines page exposes custom provider tui dialog markup | Standard scenario | functional | P2 |
| `test_ui_engines_auth_capabilities_come_from_strategy_service` | Tests auth ui engines  capabilities come from strategy service | Standard scenario | functional | P2 |
| `test_ui_engine_auth_shell_route_is_removed` | Tests auth ui engine  shell route is removed | Standard scenario | regression | P2 |
| `test_ui_engine_tui_session_endpoints` | Tests session ui engine tui  endpoints | Standard scenario | functional | P2 |
| `test_ui_engine_tui_start_busy_returns_409` | Tests return value for ui engine tui start busy  409 | Standard scenario | functional | P1 |
| `test_ui_engine_tui_start_sandbox_probe_is_not_blocking` | Tests probe ui engine tui start sandbox  is not blocking | Standard scenario | functional | P2 |
| `test_ui_engine_tui_start_invalid_custom_model_returns_400` | Tests return value for ui engine tui start invalid custom model  400 | Invalid input | functional | P1 |
| `test_ui_engine_tui_start_returns_503_when_ttyd_unavailable` | Tests return value for ui engine tui start  503 when ttyd unavailable | Standard scenario | functional | P2 |
| `test_ui_engines_table_partial` | Tests ui engines table partial | Standard scenario | functional | P2 |
| `test_ui_engines_table_shows_claude_sandbox_warning` | Tests ui engines table shows claude sandbox warning | Standard scenario | functional | P2 |
| `test_ui_engines_table_hides_tui_start_when_ttyd_missing` | Tests ui engines table hides tui start when ttyd missing | Missing required field | functional | P1 |
| ... (18 more tests) | See source file | — | — | — |

**Assessment:** Comprehensive coverage with 48 test functions.

#### `test_ui_shell_manager.py`

- **Test cases:** 23
- **Lines:** 574

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_ui_shell_manager_rejects_unknown_engine` | Validates rejection of ui shell manager  unknown engine | Standard scenario | regression | P2 |
| `test_ui_shell_manager_requires_ttyd` | Tests ui shell manager requires ttyd | Standard scenario | regression | P2 |
| `test_ui_shell_manager_single_active_session_busy` | Tests session ui shell manager single active  busy | Standard scenario | regression | P1 |
| `test_ui_shell_manager_stop_session_sets_terminal` | Tests session ui shell manager stop  sets terminal | Standard scenario | regression | P2 |
| `test_ui_shell_manager_registers_and_releases_process_lease` | Tests registration of ui shell manager  and releases process lease | Standard scenario | regression | P2 |
| `test_ui_shell_manager_landlock_disabled_is_non_blocking` | Tests ui shell manager landlock disabled is non blocking | Standard scenario | regression | P2 |
| `test_ui_shell_manager_non_codex_sandbox_probe_is_non_blocking` | Tests probe ui shell manager non codex sandbox  is non blocking | Standard scenario | regression | P2 |
| `test_ui_shell_manager_local_port_conflict_fallback` | Tests fallback for ui shell manager local port conflict | Resource conflict | regression | P1 |
| `test_ui_shell_manager_container_port_conflict_raises_busy` | Tests that exception is raised for ui shell manager container port conflict  busy | Resource conflict | regression | P1 |
| `test_ui_shell_manager_start_session_injects_trust_and_ttyd_flags` | Tests session ui shell manager start  injects trust and ttyd flags | Standard scenario | regression | P2 |
| `test_ui_shell_manager_start_failure_rolls_back_trust` | Tests failure handling for ui shell manager start  rolls back trust | Failure scenario | regression | P1 |
| `test_ui_shell_manager_claude_session_bootstraps_git_without_parent_trust` | Tests session ui shell manager claude  bootstraps git without parent trust | Standard scenario | regression | P2 |
| `test_ui_shell_manager_claude_custom_model_injects_provider_env` | Tests model ui shell manager claude custom  injects provider env | Standard scenario | regression | P2 |
| `test_ui_shell_manager_claude_custom_model_1m_mode_uses_root_model_and_default_sonnet` | Tests default ui shell manager claude custom model 1m mode uses root model and  sonnet | Default configuration | regression | P2 |
| `test_ui_shell_manager_rejects_invalid_custom_model_format` | Validates rejection of ui shell manager  invalid custom model format | Invalid input | regression | P1 |
| `test_ui_shell_manager_rejects_custom_model_for_non_claude_engine` | Validates rejection of ui shell manager  custom model for non claude engine | Standard scenario | regression | P2 |
| `test_ui_shell_manager_gemini_session_enforces_sandbox_and_disables_shell` | Tests enforcement of ui shell manager gemini session  sandbox and disables shell | Standard scenario | regression | P2 |
| `test_ui_shell_manager_iflow_session_disables_shell_and_reports_non_sandbox` | Tests session ui shell manager iflow  disables shell and reports non sandbox | Standard scenario | regression | P2 |
| `test_ui_shell_manager_opencode_session_reports_non_sandbox` | Tests session ui shell manager opencode  reports non sandbox | Standard scenario | regression | P2 |
| `test_ui_shell_manager_respects_auth_gate_conflict` | Tests conflict handling for ui shell manager respects auth gate | Resource conflict | regression | P1 |
| `test_ui_shell_manager_gemini_fallback_without_sandbox_runtime_still_disables_shell` | Tests fallback for ui shell manager gemini  without sandbox runtime still disables shell | Fallback path | regression | P2 |
| `test_ui_shell_manager_gemini_api_key_mode_disables_sandbox` | Tests key ui shell manager gemini api  mode disables sandbox | Standard scenario | regression | P2 |
| `test_ui_shell_manager_gemini_missing_auth_fields_do_not_crash_and_keep_sandbox` | Tests auth ui shell manager gemini missing  fields do not crash and keep sandbox | Missing required field | regression | P1 |

**Assessment:** Comprehensive coverage with 23 test functions.

#### `test_v1_routes.py`

- **Test cases:** 55
- **Lines:** 1386

| Test Function | Purpose | Scenario | Type | Importance |
|--------------|---------|----------|------|------------|
| `test_legacy_routes_return_404` | Tests route legacy s return 404 | Standard scenario | regression | P2 |
| `test_v1_system_ping_route_available` | Tests route v1 system ping  available | Standard scenario | functional | P2 |
| `test_v1_skills_route_available` | Tests route v1 skills  available | Standard scenario | functional | P2 |
| `test_v1_jobs_file_routes_available` | Tests route v1 jobs file s available | Standard scenario | functional | P2 |
| `test_v1_local_runtime_status_route_available` | Tests route v1 local runtime status  available | Standard scenario | functional | P2 |
| `test_v1_local_runtime_lease_roundtrip` | Tests lease v1 local runtime  roundtrip | Standard scenario | functional | P2 |
| `test_v1_local_runtime_lease_rejected_when_not_local` | Tests lease v1 local runtime  rejected when not local | Standard scenario | functional | P2 |
| `test_v1_engines_route_available` | Tests route v1 engines  available | Standard scenario | functional | P2 |
| `test_v1_engine_auth_status_route_removed` | Tests auth v1 engine  status route removed | Standard scenario | regression | P2 |
| `test_v1_oauth_proxy_grouped_routes` | Tests auth v1 o proxy grouped routes | Standard scenario | functional | P2 |
| `test_v1_cli_delegate_grouped_routes` | Tests route v1 cli delegate grouped s | Standard scenario | functional | P2 |
| `test_v1_engine_auth_session_start_route` | Tests session v1 engine auth  start route | Standard scenario | functional | P2 |
| `test_v1_engine_auth_session_start_route_passes_auth_method` | Tests session v1 engine auth  start route passes auth method | Standard scenario | functional | P2 |
| `test_v1_engine_auth_session_start_route_iflow` | Tests session v1 engine auth  start route iflow | Standard scenario | functional | P2 |
| `test_v1_engine_auth_session_start_route_opencode` | Tests session v1 engine auth  start route opencode | Standard scenario | functional | P2 |
| `test_v1_engine_auth_session_start_route_qwen_provider_aware` | Tests session v1 engine auth  start route qwen provider aware | Standard scenario | functional | P2 |
| `test_v1_engine_auth_session_start_conflict` | Tests conflict handling for v1 engine auth session start | Resource conflict | functional | P1 |
| `test_v1_engine_auth_session_start_unprocessable` | Tests session v1 engine auth  start unprocessable | Standard scenario | functional | P2 |
| `test_v1_engine_auth_session_status_and_cancel` | Tests cancellation v1 engine auth session status and | Cancellation request | functional | P1 |
| `test_v1_engine_auth_session_input` | Tests session v1 engine auth  input | Standard scenario | functional | P2 |
| `test_v1_engine_auth_session_input_iflow` | Tests session v1 engine auth  input iflow | Standard scenario | functional | P2 |
| `test_v1_engine_auth_session_input_unprocessable` | Tests session v1 engine auth  input unprocessable | Standard scenario | functional | P2 |
| `test_v1_engine_auth_openai_callback_without_basic_auth` | Tests auth v1 engine  openai callback without basic auth | Standard scenario | functional | P2 |
| `test_v1_engine_auth_openai_callback_invalid_state` | Tests state of v1 engine auth openai callback invalid | Invalid input | functional | P1 |
| `test_v1_engine_auth_openai_callback_missing_state` | Tests state of v1 engine auth openai callback missing | Missing required field | functional | P1 |
| `test_v1_engine_auth_session_submit_removed` | Tests session v1 engine auth  submit removed | Standard scenario | regression | P2 |
| `test_v1_engine_auth_session_status_not_found` | Tests session v1 engine auth  status not found | Resource not found | functional | P2 |
| `test_v1_engine_models_route_available` | Tests route v1 engine models  available | Standard scenario | functional | P2 |
| `test_v1_engine_models_route_opencode_runtime_probe_cache` | Tests route v1 engine models  opencode runtime probe cache | Standard scenario | functional | P2 |
| `test_v1_engine_models_not_found` | Tests model v1 engine s not found | Resource not found | functional | P2 |
| ... (25 more tests) | See source file | — | — | — |

**Assessment:** Comprehensive coverage with 55 test functions.

---

## 3. Statistical Analysis

### Heatmap: Importance x Test Type

| Importance | Functional | Contract | Regression | Property | Structural | Security | Governance | Total |
|------------|------------|----------|------------|----------|------------|----------|------------|-------|
| P0 | 80 | 6 | 0 | 0 | 5 | 1 | 0 | 92 |
| P1 | 540 | 88 | 18 | 3 | 23 | 0 | 0 | 672 |
| P2 | 470 | 13 | 34 | 0 | 28 | 0 | 0 | 545 |
| P3 | 3 | 0 | 1 | 0 | 3 | 0 | 0 | 7 |

### Category Coverage Analysis

| Category | Files | Tests | Avg Tests/File | Largest File | Smallest File |
|----------|-------|-------|----------------|--------------|---------------|
| orchestration/core | 24 | 238 | 9.9 | test_job_orchestrator.py (59) | test_orchestration_no_compat_shells.py (1) |
| platform/infrastructure | 37 | 197 | 5.3 | test_protocol_schema_registry.py (27) | test_chat_replay_contract.py (1) |
| adapter | 14 | 181 | 12.9 | test_gemini_adapter.py (27) | test_adapter_component_contracts.py (1) |
| ui/routes | 8 | 173 | 21.6 | test_v1_routes.py (55) | test_management_routes_timeline_history.py (2) |
| auth_detection | 32 | 135 | 4.2 | test_engine_auth_flow_manager.py (35) | test_auth_detection_audit_persistence.py (1) |
| runtime_protocols | 27 | 101 | 3.7 | test_runtime_event_protocol.py (33) | test_ask_user_schema_role.py (1) |
| skill_management | 13 | 93 | 7.2 | test_skill_package_validator.py (21) | test_skill_runnerctl_bootstrap.py (2) |
| cli/harness | 7 | 64 | 9.1 | test_agent_cli_manager.py (28) | test_cli_delegate_orchestrator.py (1) |
| misc/structural | 14 | 53 | 3.8 | test_gemini_auth_cli_flow.py (13) | test_engines_common_openai_ssot.py (1) |
| config/settings | 11 | 50 | 4.5 | test_options_policy.py (14) | test_command_defaults.py (2) |
| engine_management | 8 | 20 | 2.5 | test_engine_upgrade_manager.py (6) | test_engine_adapter_component_wiring.py (1) |
| structured_output | 1 | 11 | 11.0 | test_agent_output_protocol_contract.py (11) | test_agent_output_protocol_contract.py (11) |

### Gap Analysis: Under-tested Areas

The following areas have relatively low test coverage or could benefit from additional testing:

| Area | Issue | Recommendation |
|------|-------|----------------|
| 76 files with <=2 tests | Minimal coverage per file | Consider merging related tests or adding more scenarios |
| structured_output (11 tests) | Low test density | Add more functional and edge case tests |
| engine_management (20 tests) | Low test density | Add more functional and edge case tests |
| Property-based tests | Only mapping/invariant tests | Add hypothesis-based tests for parsers, state machines |
| Regression test suites | Limited to deprecation checks | Add tests for known bug patterns and historical issues |
| Cross-component integration | Mostly unit-level | Add integration tests across adapter/orchestration boundaries |
| Error propagation paths | Partial coverage | Add tests verifying error messages bubble up correctly |
| Concurrent/async edge cases | Limited testing | Add race condition and async timeout tests |

---

## 4. Recommendations

### Missing Test Areas

1. **Performance/benchmark tests**: No tests verifying response time or throughput characteristics.
2. **Load/stress tests**: No tests exercising the system under concurrent load.
3. **Database migration tests**: No tests verifying SQLite schema migrations.
4. **i18n completeness tests**: Limited to key coverage, not actual translation quality.
5. **Accessibility tests**: No tests for UI accessibility features.
6. **Configuration migration tests**: No tests for config format upgrades.

### Tests to Upgrade

The following tests should be considered for importance upgrades:

| Test | Current | Proposed | Rationale |
|------|---------|----------|-----------|
| Structural/import boundary tests | P2 | P1 | Prevent architectural regression, critical for maintainability |
| Engine adapter stream parsing | P1 | P0 | Core output processing path, affects all engines |
| Session state contract tests | P1 | P0 | State machine correctness is critical for run lifecycle |
| Auth session persistence | P2 | P1 | Auth state loss causes user-visible failures |
| File preview binary detection | P2 | P1 | Security boundary (binary file handling) |

### Tests That Could Be Consolidated

| Group | Files | Rationale |
|-------|-------|-----------|
| Engine local callback servers | `test_antigravity_local_callback_server.py`, `test_gemini_local_callback_server.py`, `test_iflow_local_callback_server.py`, `test_openai_local_callback_server.py` (4 files, 9 tests total) | Similar lifecycle tests, could share fixtures |
| Engine OAuth proxy flows | `test_gemini_oauth_proxy_flow.py`, `test_iflow_oauth_proxy_flow.py`, `test_codex_oauth_proxy_flow.py`, `test_opencode_openai_oauth_proxy_flow.py` (4 files, 10 tests total) | Common OAuth patterns could use shared test base |
| Auth detection per-engine | `test_auth_detection_codex.py`, `test_auth_detection_gemini.py`, `test_auth_detection_iflow.py`, `test_auth_detection_opencode.py` (4 files, 8 tests total) | Similar detection logic, parameterizable |
| Runtime import boundaries | `test_runtime_no_orchestration_imports.py`, `test_runtime_core_import_boundaries.py`, `test_runtime_auth_no_engine_coupling.py`, `test_runtime_adapter_no_legacy_dependencies.py` (4 files, 5 tests total) | Similar governance pattern |
| E2E completion/observe | `test_e2e_completion_hidden_and_summary_single_source.py`, `test_e2e_observe_replayless_history_semantics.py` (2 files, 5 tests total) | Related semantics testing |

### Structural Improvements

1. **Shared test fixtures**: Many test files duplicate fixture setup (FakeProcess, FakePtyRuntime, etc.). Extract to `tests/unit/fixtures/` for reuse.
2. **Parameterized tests**: Several files have near-identical tests for different engines. Use `@pytest.mark.parametrize` to reduce duplication.
3. **Test data isolation**: Some tests use `tmp_path` but could benefit from more structured test data fixtures.
4. **Test naming convention**: Consider adopting a consistent naming pattern: `test_<component>_<scenario>_<expected>` for better organization.
5. **Mark-based filtering**: Use pytest markers (`@pytest.mark.security`, `@pytest.mark.contract`, `@pytest.mark.slow`) to enable selective test runs.
6. **Snapshot testing**: For UI route and template rendering tests, consider snapshot-based testing to catch visual regressions.
7. **Contract test registry**: Centralize contract test definitions so that protocol changes automatically trigger relevant test updates.

---

## Appendix A: Complete File Listing by Importance

### P0 Files (38 files)

| File | Category | Tests | Lines |
|------|----------|-------|-------|
| `test_adapter_command_profiles.py` | adapter | 21 | 755 |
| `test_adapter_failfast.py` | adapter | 19 | 870 |
| `test_adapter_parsing.py` | adapter | 20 | 352 |
| `test_agent_cli_manager.py` | cli/harness | 28 | 610 |
| `test_auth_detection_codex.py` | auth_detection | 3 | 71 |
| `test_auth_detection_gemini.py` | auth_detection | 2 | 48 |
| `test_auth_detection_iflow.py` | auth_detection | 1 | 27 |
| `test_auth_detection_lifecycle_integration.py` | auth_detection | 10 | 1026 |
| `test_auth_detection_opencode.py` | auth_detection | 2 | 64 |
| `test_auth_session_starter.py` | auth_detection | 2 | 128 |
| `test_chat_replay_schema_registry.py` | platform/infrastructure | 5 | 102 |
| `test_codex_adapter.py` | adapter | 16 | 518 |
| `test_config_contract_governance_guards.py` | config/settings | 2 | 64 |
| `test_engine_auth_bootstrap.py` | auth_detection | 3 | 141 |
| `test_gemini_adapter.py` | adapter | 27 | 867 |
| `test_job_orchestrator.py` | orchestration/core | 59 | 4246 |
| `test_jobs_interaction_routes.py` | ui/routes | 12 | 524 |
| `test_live_publish_ordering.py` | orchestration/core | 9 | 432 |
| `test_protocol_schema_registry.py` | platform/infrastructure | 27 | 668 |
| `test_protocol_state_alignment.py` | platform/infrastructure | 2 | 118 |
| `test_qwen_adapter.py` | adapter | 5 | 190 |
| `test_release_installer_output_contract.py` | platform/infrastructure | 3 | 38 |
| `test_run_auth_orchestration_service.py` | orchestration/core | 24 | 1452 |
| `test_run_interaction_lifecycle_service.py` | orchestration/core | 5 | 207 |
| `test_run_output_convergence_service.py` | orchestration/core | 3 | 288 |
| `test_run_recovery_service.py` | orchestration/core | 5 | 208 |
| `test_run_store.py` | orchestration/core | 21 | 509 |
| `test_runtime_auth_no_engine_coupling.py` | runtime_protocols | 1 | 16 |
| `test_runtime_core_import_boundaries.py` | runtime_protocols | 1 | 35 |
| `test_runtime_file_contract_scan.py` | runtime_protocols | 1 | 53 |
| `test_runtime_no_orchestration_imports.py` | runtime_protocols | 1 | 24 |
| `test_schema_validator.py` | platform/infrastructure | 16 | 344 |
| `test_skill_package_manager.py` | skill_management | 10 | 341 |
| `test_skill_package_validator.py` | skill_management | 21 | 434 |
| `test_skill_patcher.py` | skill_management | 5 | 133 |
| `test_skill_runnerctl_preflight.py` | skill_management | 9 | 290 |
| `test_structured_trace_logging.py` | platform/infrastructure | 2 | 52 |
| `test_workspace_manager.py` | orchestration/core | 8 | 261 |

### P1 Files (132 files)

| File | Category | Tests | Lines |
|------|----------|-------|-------|
| `test_adapter_common_components.py` | adapter | 12 | 389 |
| `test_adapter_component_contracts.py` | adapter | 1 | 95 |
| `test_adapter_io_chunks_journal.py` | adapter | 4 | 291 |
| `test_adapter_live_stream_emission.py` | adapter | 21 | 1091 |
| `test_adapter_profile_loader.py` | adapter | 6 | 614 |
| `test_agent_harness_config.py` | cli/harness | 2 | 28 |
| `test_agent_harness_container_wrapper.py` | cli/harness | 2 | 108 |
| `test_agent_harness_runtime.py` | cli/harness | 20 | 805 |
| `test_agent_manager_bootstrap.py` | cli/harness | 4 | 159 |
| `test_agent_output_protocol_contract.py` | structured_output | 11 | 114 |
| `test_antigravity_local_callback_server.py` | auth_detection | 2 | 50 |
| `test_ask_user_schema_role.py` | runtime_protocols | 1 | 25 |
| `test_attempt_materialization_context_isolation.py` | runtime_protocols | 1 | 90 |
| `test_auth_callback_listener_registry.py` | auth_detection | 2 | 47 |
| `test_auth_callback_state_store.py` | auth_detection | 3 | 32 |
| `test_auth_detection_audit_persistence.py` | auth_detection | 1 | 64 |
| `test_auth_detection_rule_loader.py` | auth_detection | 7 | 291 |
| `test_auth_driver_registry.py` | auth_detection | 2 | 34 |
| `test_auth_import_service.py` | auth_detection | 9 | 177 |
| `test_auth_log_writer.py` | auth_detection | 3 | 36 |
| `test_cache_key_builder.py` | platform/infrastructure | 15 | 265 |
| `test_chat_replay_contract.py` | platform/infrastructure | 1 | 24 |
| `test_chat_replay_derivation.py` | platform/infrastructure | 9 | 250 |
| `test_chat_replay_live_journal.py` | platform/infrastructure | 2 | 34 |
| `test_chat_replay_publisher.py` | platform/infrastructure | 1 | 55 |
| `test_chat_thinking_core_model.py` | platform/infrastructure | 4 | 152 |
| `test_claude_adapter.py` | adapter | 2 | 108 |
| `test_claude_custom_providers.py` | config/settings | 5 | 100 |
| `test_cli_delegate_orchestrator.py` | cli/harness | 1 | 66 |
| `test_codex_config_fusion.py` | config/settings | 6 | 175 |
| `test_codex_oauth_proxy_flow.py` | auth_detection | 1 | 40 |
| `test_command_defaults.py` | config/settings | 2 | 24 |
| `test_concurrency_manager.py` | platform/infrastructure | 9 | 183 |
| `test_config.py` | config/settings | 3 | 28 |
| `test_config_generator.py` | config/settings | 3 | 102 |
| `test_container_runtime_defaults.py` | platform/infrastructure | 2 | 26 |
| `test_e2e_client_config.py` | platform/infrastructure | 3 | 37 |
| `test_e2e_completion_hidden_and_summary_single_source.py` | platform/infrastructure | 2 | 21 |
| `test_e2e_observe_replayless_history_semantics.py` | platform/infrastructure | 3 | 27 |
| `test_e2e_run_observe_semantics.py` | platform/infrastructure | 22 | 280 |
| `test_engine_adapter_registry.py` | engine_management | 3 | 61 |
| `test_engine_auth_driver_contracts.py` | auth_detection | 2 | 46 |
| `test_engine_auth_driver_matrix_registration.py` | auth_detection | 1 | 117 |
| `test_engine_auth_flow_manager.py` | auth_detection | 35 | 1483 |
| `test_engine_auth_strategy_schema.py` | auth_detection | 3 | 67 |
| `test_engine_auth_strategy_service.py` | auth_detection | 8 | 144 |
| `test_engine_interaction_gate.py` | auth_detection | 2 | 20 |
| `test_engine_package_bootstrap.py` | engine_management | 2 | 23 |
| `test_engine_shell_capability_provider.py` | engine_management | 1 | 27 |
| `test_engine_status_cache_service.py` | engine_management | 5 | 108 |
| `test_engine_upgrade_manager.py` | engine_management | 6 | 108 |
| `test_engine_upgrade_store.py` | engine_management | 1 | 24 |
| `test_fcmp_cursor_global_seq.py` | runtime_protocols | 2 | 226 |
| `test_fcmp_global_seq_persisted_files.py` | runtime_protocols | 1 | 138 |
| `test_fcmp_interaction_dedup.py` | runtime_protocols | 1 | 115 |
| `test_fcmp_lifecycle_normalization.py` | runtime_protocols | 3 | 39 |
| `test_fcmp_live_journal.py` | runtime_protocols | 2 | 39 |
| `test_fcmp_mapping_properties.py` | runtime_protocols | 6 | 267 |
| `test_fs_diff_ignore_rules.py` | platform/infrastructure | 1 | 32 |
| `test_gemini_local_callback_server.py` | auth_detection | 2 | 48 |
| `test_harness_fs_diff_ignore_rules.py` | platform/infrastructure | 1 | 34 |
| `test_iflow_adapter.py` | adapter | 20 | 453 |
| `test_iflow_auth_cli_flow.py` | misc/structural | 8 | 301 |
| `test_iflow_local_callback_server.py` | auth_detection | 2 | 48 |
| `test_local_runtime_lease_service.py` | platform/infrastructure | 2 | 50 |
| `test_logging_quota_policy.py` | platform/infrastructure | 2 | 51 |
| `test_management_log_range_attempt.py` | misc/structural | 1 | 42 |
| `test_management_routes.py` | ui/routes | 26 | 1106 |
| `test_management_routes_protocol_history.py` | ui/routes | 3 | 128 |
| `test_management_routes_timeline_history.py` | ui/routes | 2 | 92 |
| `test_model_registry.py` | platform/infrastructure | 18 | 406 |
| `test_oauth_openai_callback_routes.py` | auth_detection | 2 | 63 |
| `test_oauth_proxy_orchestrator.py` | auth_detection | 3 | 97 |
| `test_openai_device_proxy_flow.py` | auth_detection | 2 | 98 |
| `test_openai_local_callback_server.py` | auth_detection | 3 | 67 |
| `test_opencode_adapter.py` | adapter | 7 | 191 |
| `test_opencode_model_catalog_service.py` | misc/structural | 3 | 129 |
| `test_opencode_model_catalog_startup.py` | misc/structural | 1 | 82 |
| `test_opencode_openai_oauth_proxy_flow.py` | misc/structural | 1 | 41 |
| `test_options_policy.py` | config/settings | 14 | 114 |
| `test_orchestration_no_compat_shells.py` | orchestration/core | 1 | 11 |
| `test_orchestrator_history_seq_backfill.py` | orchestration/core | 1 | 101 |
| `test_process_supervisor.py` | platform/infrastructure | 4 | 136 |
| `test_process_termination.py` | platform/infrastructure | 5 | 53 |
| `test_qwen_auth_runtime_handler.py` | misc/structural | 4 | 212 |
| `test_qwen_coding_plan_flow.py` | misc/structural | 2 | 91 |
| `test_qwen_oauth_proxy_flow.py` | auth_detection | 10 | 356 |
| `test_raw_row_coalescer.py` | runtime_protocols | 4 | 85 |
| `test_run_audit_contract_service.py` | orchestration/core | 1 | 30 |
| `test_run_cleanup_manager.py` | orchestration/core | 9 | 343 |
| `test_run_execution_core.py` | orchestration/core | 7 | 107 |
| `test_run_file_filter_service.py` | orchestration/core | 3 | 24 |
| `test_run_folder_bootstrapper.py` | orchestration/core | 2 | 119 |
| `test_run_folder_trust_manager.py` | orchestration/core | 6 | 166 |
| `test_run_folder_trust_manager_dispatch.py` | orchestration/core | 2 | 56 |
| `test_run_observability.py` | orchestration/core | 33 | 1904 |
| `test_run_observability_attempt_partitioning.py` | orchestration/core | 1 | 86 |
| `test_run_output_schema_service.py` | orchestration/core | 3 | 175 |
| `test_run_service_log_mirror.py` | orchestration/core | 4 | 125 |
| `test_run_source_adapter.py` | orchestration/core | 3 | 58 |
| `test_runs_router_cache.py` | orchestration/core | 25 | 1136 |
| `test_runtime_event_ordering_contract_rules.py` | runtime_protocols | 4 | 51 |
| `test_runtime_event_ordering_contract_schema.py` | runtime_protocols | 3 | 33 |
| `test_runtime_event_ordering_gate.py` | runtime_protocols | 2 | 49 |
| `test_runtime_event_protocol.py` | runtime_protocols | 33 | 1358 |
| `test_runtime_event_protocol_fixtures.py` | runtime_protocols | 1 | 105 |
| `test_runtime_observability_port_injection.py` | runtime_protocols | 2 | 140 |
| `test_runtime_profile.py` | runtime_protocols | 2 | 48 |
| `test_runtime_protocol_parser_resolver_port.py` | runtime_protocols | 1 | 39 |
| `test_session_invariant_contract.py` | runtime_protocols | 6 | 128 |
| `test_session_state_model_properties.py` | runtime_protocols | 7 | 104 |
| `test_session_statechart_contract.py` | runtime_protocols | 4 | 62 |
| `test_session_timeout.py` | runtime_protocols | 3 | 22 |
| `test_skill_browser.py` | skill_management | 6 | 93 |
| `test_skill_install_store.py` | skill_management | 3 | 56 |
| `test_skill_packages_router.py` | skill_management | 4 | 94 |
| `test_skill_patch_output_schema.py` | skill_management | 7 | 158 |
| `test_skill_patcher_pipeline.py` | skill_management | 6 | 142 |
| `test_skill_registry.py` | skill_management | 7 | 262 |
| `test_skill_runner_uninstall_scripts.py` | skill_management | 8 | 272 |
| `test_skill_runnerctl_bootstrap.py` | skill_management | 2 | 85 |
| `test_skill_runnerctl_port_policy.py` | skill_management | 5 | 144 |
| `test_sqlite_async_boundary.py` | platform/infrastructure | 2 | 58 |
| `test_structured_output_pipeline.py` | platform/infrastructure | 4 | 190 |
| `test_system_settings_service.py` | config/settings | 3 | 114 |
| `test_test_data_dir_isolation.py` | misc/structural | 1 | 15 |
| `test_trust_folder_strategy_invocation_paths.py` | platform/infrastructure | 1 | 31 |
| `test_trust_folder_strategy_registry.py` | platform/infrastructure | 2 | 38 |
| `test_ui_auth.py` | ui/routes | 4 | 37 |
| `test_ui_routes.py` | ui/routes | 48 | 1698 |
| `test_ui_shell_manager.py` | ui/routes | 23 | 574 |
| `test_v1_routes.py` | ui/routes | 55 | 1386 |

### P2 Files (26 files)

| File | Category | Tests | Lines |
|------|----------|-------|-------|
| `test_agent_harness_cli.py` | cli/harness | 7 | 315 |
| `test_bundle_manifest.py` | platform/infrastructure | 3 | 85 |
| `test_claude_config_composer.py` | config/settings | 5 | 290 |
| `test_codex_config.py` | config/settings | 4 | 76 |
| `test_data_reset_service.py` | platform/infrastructure | 5 | 190 |
| `test_engine_adapter_component_wiring.py` | engine_management | 1 | 22 |
| `test_engine_adapter_entrypoints.py` | engine_management | 1 | 30 |
| `test_engine_auth_manager_import_boundary.py` | auth_detection | 1 | 9 |
| `test_engines_common_openai_ssot.py` | misc/structural | 1 | 33 |
| `test_execution_modules_relocated.py` | platform/infrastructure | 1 | 10 |
| `test_file_preview_renderer.py` | runtime_protocols | 6 | 160 |
| `test_gemini_auth_cli_flow.py` | misc/structural | 13 | 386 |
| `test_gemini_oauth_proxy_flow.py` | auth_detection | 3 | 94 |
| `test_i18n_locale_coverage.py` | platform/infrastructure | 3 | 67 |
| `test_iflow_oauth_proxy_flow.py` | auth_detection | 3 | 87 |
| `test_logging_config.py` | platform/infrastructure | 10 | 235 |
| `test_models_module_structure.py` | platform/infrastructure | 3 | 29 |
| `test_no_unapproved_broad_exception.py` | platform/infrastructure | 1 | 115 |
| `test_opencode_auth_cli_flow.py` | misc/structural | 9 | 219 |
| `test_opencode_auth_store.py` | misc/structural | 3 | 62 |
| `test_opencode_google_antigravity_oauth_proxy_flow.py` | misc/structural | 3 | 107 |
| `test_qwen_auth_cli_delegate_flow.py` | misc/structural | 3 | 90 |
| `test_run_folder_git_initializer.py` | orchestration/core | 3 | 52 |
| `test_runtime_adapter_no_legacy_dependencies.py` | runtime_protocols | 2 | 20 |
| `test_services_topology_rules.py` | platform/infrastructure | 1 | 17 |
| `test_system_log_explorer_service.py` | config/settings | 3 | 103 |

---

## 5. 可下线测试清单

本节列出建议直接**删除**的测试文件。这些测试的共同特征是：**验证已经完成且不可能回退的迁移/重构**，或**验证稳定配置文件的内容**。代码已经历多轮迭代，这些场景的回退概率接近于零。

### 下线原则

1. **已完成迁移的一次性检查** — 验证旧文件不存在、旧导入已移除、旧路径已清理。一旦删除，不可能再出现
2. **已稳定配置的内容验证** — 验证 YAML/JSON/TOML/Dockerfile 文件包含特定内容。一旦配置确定，除非故意修改否则不会变化
3. **继承/组件结构的验证** — 验证类继承关系或组件接线。一旦架构稳定，不会回退
4. **安装脚本/CI 流程的格式检查** — 验证安装脚本输出格式或 CI workflow 包含特定步骤。这些是发布工件，不会在常规开发中回退

### 不可下线的测试（即使在治理范围内）

- **活跃行为测试** — 测试实际运行时代码的行为（过滤、排序、状态机、并发控制等），即使只有 1 个测试也要保留
- **活跃治理守卫** — 如 `test_no_unapproved_broad_exception.py`（防止新增宽泛异常处理）、`test_config_contract_governance_guards.py` 的测试 2（强制 registry 模式读取合约）— 这些在开发过程中可能被违反
- **有外部依赖的验证** — 依赖运行时生成数据的测试（如 seq backfill、partitioning、materialization）— 这些是功能行为测试

---

### 第 1 组：已完成的迁移验证（8 个文件，10 个测试）

这些测试验证**已经完成且不可能回退**的文件移动、删除、目录重组。

| 文件 | 测试数 | 验证内容 | 为何可下线 |
|------|--------|----------|------------|
| `test_execution_modules_relocated.py` | 1 | 旧执行模块路径不存在，新路径存在 | 文件移动后不可能再出现旧路径，除非有人刻意复制回去 |
| `test_orchestration_no_compat_shells.py` | 1 | 兼容壳文件已删除 | 已删除的文件不可能自行恢复 |
| `test_services_topology_rules.py` | 1 | `server/services/` 根目录无扁平 .py 文件 | 目录结构已重组完成，不会回退 |
| `test_runtime_adapter_no_legacy_dependencies.py` | 2 | 旧 adapter 文件已删除；无 `server.adapters.base` 导入 | 旧文件已删除，导入路径已重构，不可能回退 |
| `test_runtime_no_orchestration_imports.py` | 1 | runtime 模块不导入 orchestration | 导入已移除，架构已稳定，不会回退 |
| `test_runtime_core_import_boundaries.py` | 1 | runtime 不导入遗留服务域 | 同上 |
| `test_runtime_auth_no_engine_coupling.py` | 1 | runtime/auth 不导入 engines | 同上 |
| `test_runtime_file_contract_scan.py` | 1 | 代码中无遗留文件路径引用 | 路径引用已清理，不会回退 |

**小计**: -8 文件, -10 测试

---

### 第 2 组：单一文件 Import 边界检查（3 个文件，3 个测试）

这些测试用 AST/文本扫描检查特定文件的导入模式，属于已完成重构的验证。

| 文件 | 测试数 | 验证内容 | 为何可下线 |
|------|--------|----------|------------|
| `test_engine_auth_manager_import_boundary.py` | 1 | `engine_auth_flow_manager.py` 的导入模式正确 | 单一文件的导入模式检查，重构完成后不会回退 |
| `test_engines_common_openai_ssot.py` | 1 | `openai_auth/` 不导入 `server.services` | 依赖边界已清理，不会回退 |
| `test_trust_folder_strategy_invocation_paths.py` | 1 | 多文件中存在特定方法调用模式 | 本质是"代码拼写检查"，验证特定调用路径存在。架构稳定后不会回退 |

**小计**: -3 文件, -3 测试

---

### 第 3 组：Adapter 组件结构验证（3 个文件，3 个测试）

验证类继承关系和组件接线。

| 文件 | 测试数 | 验证内容 | 为何可下线 |
|------|--------|----------|------------|
| `test_engine_adapter_component_wiring.py` | 1 | 每个引擎的 ExecutionAdapter 是 `EngineExecutionAdapter` 子类 | 继承关系已建立，不可能回退 |
| `test_engine_adapter_entrypoints.py` | 1 | 所有适配器具有必需的组件属性 | 组件接线已建立，不可能回退 |
| `test_engine_package_bootstrap.py`（部分） | 1 | `test_all_engine_adapters_instantiate` — 适配器可实例化 | 基本实例化检查，适配器注册后不可能突然失败 |

**注意**: `test_engine_package_bootstrap.py` 的第二个测试 `test_opencode_auth_registry_providers` 应保留（验证注册表行为）。

**小计**: -3 文件, -3 测试

---

### 第 4 组：配置/合约内容验证（5 个文件，12 个测试）

验证 YAML/JSON/TOML/Dockerfile 文件包含特定内容。

| 文件 | 测试数 | 验证内容 | 为何可下线 |
|------|--------|----------|------------|
| `test_runtime_event_ordering_contract_rules.py` | 3 | 排序合同 YAML 包含 version=1、生命周期标准化规则、缓冲策略 | 配置内容验证。合同文件已定义后不会回退 |
| `test_runtime_event_ordering_contract_schema.py` | 4 | 排序合同 YAML 包含前置规则、门控规则、恢复规则、重放规则 | 同上 |
| `test_chat_replay_contract.py` | 1 | Chat replay 合同 YAML 定义了 roles、kinds、invariants | 配置内容验证，不会回退 |
| `test_ask_user_schema_role.py` | 1 | Schema YAML 有特定 name、role、enum 值 | 配置内容验证，不会回退 |
| `test_container_runtime_defaults.py` | 2 | Dockerfile 包含非 root 用户；compose.yml 包含绑定挂载权限说明 | Dockerfile/compose 文件内容验证。一旦配置确定不会回退 |

**小计**: -5 文件, -12 测试

---

### 第 5 组：安装脚本/CI 验证 + 其他（2 个文件，4 个测试）

| 文件 | 测试数 | 验证内容 | 为何可下线 |
|------|--------|----------|------------|
| `test_release_installer_output_contract.py` | 3 | Shell 安装脚本有 JSON 输出；PowerShell 安装脚本有 JSON 输出；CI workflow 有 integrity manifest 步骤 | 安装脚本和 CI 配置是发布工件，格式已稳定 |
| `test_test_data_dir_isolation.py` | 1 | 测试使用隔离的数据目录 | 一次性配置验证，不会回退 |

**小计**: -2 文件, -4 测试

---

### 可下线测试汇总

| 组别 | 文件数 | 测试数 |
|------|--------|--------|
| 1. 已完成迁移验证 | 8 | 10 |
| 2. 单一文件 Import 边界 | 3 | 3 |
| 3. Adapter 组件结构 | 3 | 3 |
| 4. 配置/合约内容 | 5 | 12 |
| 5. 安装脚本/CI + 其他 | 2 | 4 |
| **合计** | **21** | **32** |

### 完整下线文件列表

```
# 第 1 组：已完成迁移
tests/unit/test_execution_modules_relocated.py
tests/unit/test_orchestration_no_compat_shells.py
tests/unit/test_services_topology_rules.py
tests/unit/test_runtime_adapter_no_legacy_dependencies.py
tests/unit/test_runtime_no_orchestration_imports.py
tests/unit/test_runtime_core_import_boundaries.py
tests/unit/test_runtime_auth_no_engine_coupling.py
tests/unit/test_runtime_file_contract_scan.py

# 第 2 组：单一文件 Import 边界
tests/unit/test_engine_auth_manager_import_boundary.py
tests/unit/test_engines_common_openai_ssot.py
tests/unit/test_trust_folder_strategy_invocation_paths.py

# 第 3 组：Adapter 组件结构
tests/unit/test_engine_adapter_component_wiring.py
tests/unit/test_engine_adapter_entrypoints.py
# test_engine_package_bootstrap.py — 仅删除 test_all_engine_adapters_instantiate，保留 test_opencode_auth_registry_providers

# 第 4 组：配置/合约内容
tests/unit/test_runtime_event_ordering_contract_rules.py
tests/unit/test_runtime_event_ordering_contract_schema.py
tests/unit/test_chat_replay_contract.py
tests/unit/test_ask_user_schema_role.py
tests/unit/test_container_runtime_defaults.py

# 第 5 组：安装脚本/CI + 其他
tests/unit/test_release_installer_output_contract.py
tests/unit/test_test_data_dir_isolation.py
```

### 预期效果

| 指标 | 当前 | 下线后 |
|------|------|--------|
| 测试文件数 | 196 | **175**（或合并后 **154**） |
| 测试函数数 | 1316 | **~1284**（删除 32 个，合并组去重约 13 个） |
| 无意义测试占比 | ~2.4% | **0%** |
| 平均测试/文件 | 6.7 | **7.3** |

### 注意事项

1. `test_engine_package_bootstrap.py` 只需删除第一个测试函数，保留第二个（注册表行为测试）
2. `test_models_module_structure.py` 不在下线列表中 — 虽然包含迁移验证，但其第三个测试（`__all__` 导出解析）有轻微运行时价值
3. `test_config_contract_governance_guards.py` 不在下线列表中 — 其第二个测试（registry 模式读取合约）是活跃的架构守卫
4. 下线前建议运行一次 `pytest` 确认这些测试确实通过，然后批量删除

---
## 6. 单元测试合并/精简方案

本方案列出了可以在治理阶段安全合并或精简的测试文件，以及合并的理由和具体操作。

### 合并原则

1. **单例测试文件优先合并** — 仅含 1-2 个测试的文件应被合并到同域名的文件中
2. **跨引擎重复模式用参数化替代** — 多个引擎的 OAuth/callback/auth_detection 测试结构相同
3. **治理类测试归一化** — 架构边界、import 检查、路径扫描类测试共享同一套基础设施
4. **保留大型/复杂测试的独立性** — 测试数 ≥ 10 或逻辑复杂的文件保持独立
5. **保留有外部依赖的测试** — 依赖外部 YAML/JSON 合约文件的测试保持独立
6. **每次合并后运行 `pytest` 确认全部通过**

---

### 合并组 A：架构迁移验证 (4 → 1 文件)

| 源文件 | 测试数 | 为何可合并 |
|--------|--------|------------|
| `test_execution_modules_relocated.py` | 1 | 一次性迁移检查：验证执行模块已从 `runtime/execution/` 迁移到 `services/orchestration/` |
| `test_orchestration_no_compat_shells.py` | 1 | 一次性迁移检查：验证兼容壳文件已删除 |
| `test_services_topology_rules.py` | 1 | 一次性迁移检查：验证 `server/services/` 根目录无遗留的扁平 .py 文件 |
| `test_runtime_adapter_no_legacy_dependencies.py`（部分） | 1 | `test_legacy_adapter_files_removed` 是一次性迁移检查 |

**目标文件**: `test_architecture_migration_complete.py`（~4 个测试）
**合并后行数**: ~80 行（当前合计 ~48 行）
**预期减少**: 3 个文件

**理由**: 这 4 个文件都是**一次性迁移验证**，检查特定目录/文件是否已被正确移动或删除。它们的模式完全一致：`assert not old_path.exists()` 或 `assert not list(dir.glob("*.py"))`。一旦代码库稳定，这些测试甚至可以全部删除。合并为一个文件减少维护负担，也明确标识了它们的"临时性"。

**不可合并部分**: `test_runtime_adapter_no_legacy_dependencies.py` 中的 `test_no_server_module_imports_legacy_base` 是持续性回归守卫，应归入合并组 B。

---

### 合并组 B：架构 Import 边界守卫 (7 → 1 文件)

| 源文件 | 测试数 | 为何可合并 |
|--------|--------|------------|
| `test_runtime_no_orchestration_imports.py` | 1 | AST 扫描 runtime 模块，禁止导入 `server.services.orchestration` |
| `test_runtime_core_import_boundaries.py` | 1 | AST 扫描 runtime 模块，禁止导入遗留服务域 |
| `test_runtime_auth_no_engine_coupling.py` | 1 | AST 扫描 runtime/auth，禁止导入 `server.engines` |
| `test_runtime_file_contract_scan.py` | 1 | 文本扫描，禁止出现遗留运行时文件路径引用 |
| `test_engine_auth_manager_import_boundary.py` | 1 | AST 扫描 engine_auth_flow_manager，禁止特定导入 |
| `test_engines_common_openai_ssot.py` | 1 | AST 扫描 openai_auth，禁止导入 `server.services` |
| `test_runtime_adapter_no_legacy_dependencies.py`（部分） | 1 | `test_no_server_module_imports_legacy_base` 是持续性 import 检查 |

**目标文件**: `test_architecture_import_boundaries.py`（~7 个测试）
**预期减少**: 6 个文件

**理由**: 所有 7 个文件使用**完全相同的测试模式**：扫描 `*.py` 文件 → 用 `ast.parse()` 或文本匹配检查禁止的导入/引用 → 收集违规列表 → `assert not violations`。它们共享相同的基础设施代码（`rglob("*.py")`、`ast.parse()`、分类器逻辑），合并后可以提取一个通用的 `_scan_imports()` 辅助函数，所有 7 个测试复用同一套基础设施。

---

### 合并组 C：文件系统快照忽略规则 (2 → 1 文件)

| 源文件 | 测试数 | 为何可合并 |
|--------|--------|------------|
| `test_fs_diff_ignore_rules.py` | 1 | JobOrchestrator 的文件系统快照忽略内部前缀（.audit, .state, .git 等） |
| `test_harness_fs_diff_ignore_rules.py` | 1 | agent_harness 的 `snapshot_filesystem()` 忽略同样的内部前缀 |

**目标文件**: `test_filesystem_snapshot_ignore_rules.py`
**预期减少**: 1 个文件

**理由**: 两个测试验证**相同的忽略规则列表**，只是应用于不同组件（JobOrchestrator vs agent_harness.storage）。可以使用共享常量定义忽略前缀集合，然后对两个组件分别运行相同的忽略规则测试。

---

### 合并组 D：信任文件夹策略 (2 → 1 文件)

| 源文件 | 测试数 | 为何可合并 |
|--------|--------|------------|
| `test_trust_folder_strategy_invocation_paths.py` | 1 | 验证信任策略调用路径覆盖 run 和 auth 场景 |
| `test_trust_folder_strategy_registry.py` | 2 | 验证注册表正确解析 codex/gemini/claude 策略，noop 策略安全 |

**目标文件**: `test_trust_folder_strategy.py`（3 个测试）
**预期减少**: 1 个文件

**理由**: 两个文件都是关于 **trust folder strategy** 的同一个领域概念。一个测试调用路径，一个测试注册表解析。合并后文件更内聚，方便理解信任策略的完整行为。

---

### 合并组 E：Per-Engine OAuth Proxy 流 (5 → 1 文件)

| 源文件 | 测试数 | 为何可合并 |
|--------|--------|------------|
| `test_codex_oauth_proxy_flow.py` | 1 | Codex OAuth 代理流的 start_session 和 submit 测试 |
| `test_gemini_oauth_proxy_flow.py` | 3 | Gemini OAuth 流的 start/submit/state_mismatch 测试 |
| `test_iflow_oauth_proxy_flow.py` | 3 | iFlow OAuth 流的 start/submit/state_mismatch 测试 |
| `test_opencode_openai_oauth_proxy_flow.py` | 1 | OpenCode OpenAI 变体的 OAuth 流测试 |
| `test_opencode_google_antigravity_oauth_proxy_flow.py` | 3 | OpenCode Google Antigravity 变体的 OAuth 流测试 |

**目标文件**: `test_oauth_proxy_flow_per_engine.py`（~9 个参数化测试）
**预期减少**: 4 个文件

**理由**: 文件 1-5 遵循**完全相同的测试模式**：
- `start_session` 验证 auth_url 格式、redirect_uri、state/verifier 存在
- `submit_input` 验证凭证文件写入（monkeypatch token exchange）
- `state_mismatch` 拒绝测试（gemini/iflow/antigravity 中完全相同的模式）

唯一差异是：导入路径、auth URL 前缀、凭证文件路径、环境变量。这些差异可以用 `@pytest.mark.parametrize` 配合引擎配置字典消除。合并后测试数从 11 个减少到 9 个（去重共享模式），文件数从 5 减少到 1。

**保留独立**: `test_qwen_oauth_proxy_flow.py`（9 个测试）—— Qwen 使用设备流（poll-based），与其他引擎的回调流完全不同，测试 WAF 拦截、authorization_pending、slow_down 等独特逻辑。

---

### 合并组 F：Per-Engine Local Callback Server (4 → 1 文件)

| 源文件 | 测试数 | 为何可合并 |
|--------|--------|------------|
| `test_openai_local_callback_server.py` | 3 | OpenAI 回调服务器的 success、missing_state、callback_error 测试 |
| `test_gemini_local_callback_server.py` | 2 | Gemini 回调服务器的 success、missing_state 测试 |
| `test_iflow_local_callback_server.py` | 2 | iFlow 回调服务器的 success、missing_state 测试 |
| `test_antigravity_local_callback_server.py` | 2 | Antigravity 回调服务器的 success、missing_state 测试 |

**目标文件**: `test_local_callback_server_per_engine.py`（~3 个参数化测试）
**预期减少**: 3 个文件

**理由**: 四个文件的测试结构**完全相同**：创建服务器实例 → 启动 → HTTP 请求 → 验证响应体。唯一差异是导入路径和 skip 消息。可以用 `@pytest.mark.parametrize` 传递不同的服务器类路径。

---

### 合并组 G：Auth Infrastructure Registry (4 → 1 文件)

| 源文件 | 测试数 | 为何可合并 |
|--------|--------|------------|
| `test_auth_driver_registry.py` | 2 | Auth 驱动注册表的 resolve/fallback |
| `test_auth_callback_listener_registry.py` | 2 | 回调监听器的 start/stop、未知 channel |
| `test_auth_callback_state_store.py` | 3 | 状态存储 register/resolve/consume、channel scope |
| `test_auth_log_writer.py` | 3 | 日志写入器的布局（oauth_proxy、cli_delegate、noop） |

**目标文件**: `test_auth_infrastructure_registry.py`（~10 个测试）
**预期减少**: 3 个文件

**理由**: 四个文件都测试**简单的数据结构和注册表操作**——没有复杂的 mock 或异步逻辑，没有 HTTP 客户端或子进程交互。合并后形成一个统一的 "auth runtime 基础设施" 测试文件，结构清晰。

---

### 合并组 H：Per-Engine Auth Detection (3 → 1 文件)

| 源文件 | 测试数 | 为何可合并 |
|--------|--------|------------|
| `test_auth_detection_codex.py` | 3 | missing bearer、refresh token reauth、access token logged out |
| `test_auth_detection_gemini.py` | 2 | auth method not configured、OAuth prompt diagnostic |
| `test_auth_detection_iflow.py` | 1 | OAuth token expired |

**目标文件**: `test_auth_detection_per_engine.py`（~6 个参数化测试）
**预期减少**: 2 个文件

**理由**: 三个文件共享**完全相同的测试骨架**：`load_sample(engine, fixture_id)` → 创建适配器 → `parse_runtime_stream()` → `auth_detection_service.detect()` → 验证分类/subcategory/confidence/rule_ids。差异仅为引擎名称、fixture ID 和期望规则。可以用参数化合并。

**保留独立**: `test_auth_detection_opencode.py`（已有参数化 8 个变体 + manifest sync）、`test_auth_detection_rule_loader.py`（8 个复杂注册表测试）、`test_auth_detection_lifecycle_integration.py`（11 个端到端集成测试）。

---

### 合并组 I：Runtime Event Ordering Contract (3 → 1 文件)

| 源文件 | 测试数 | 为何可合并 |
|--------|--------|------------|
| `test_runtime_event_ordering_contract_rules.py` | 4 | 排序合同的前置规则、门控规则、单方法恢复、重放规则 |
| `test_runtime_event_ordering_contract_schema.py` | 3 | 排序合同 Schema：文件存在性、生命周期标准化、缓冲策略 |
| `test_runtime_event_ordering_gate.py` | 2 | RuntimeEventOrderingGate：缓冲直到前置条件、发布就绪 |

**目标文件**: `test_runtime_event_ordering_contract.py`（9 个测试）
**预期减少**: 2 个文件

**理由**: 三个文件都围绕**同一个核心概念**——运行时事件的排序合同。一个测试规则，一个测试 schema，一个测试 gate 实现。合并后形成一个完整的 ordering contract 测试套件。

---

### 合并组 J：Session Statechart Contract (4 → 1 文件)

| 源文件 | 测试数 | 为何可合并 |
|--------|--------|------------|
| `test_session_invariant_contract.py` | 6 | 会话不变量：合同加载、状态匹配、转移、FCMP 映射、配对事件、排序规则 |
| `test_session_state_model_properties.py` | 7 | 状态机属性：转移唯一性、可达性、终端独占性、恢复事件 |
| `test_session_statechart_contract.py` | 9 | 状态合同验证：转移键匹配、可达性、终端边、等待事件、模型等价 |
| `test_protocol_state_alignment.py` | 2 | 协议-状态对齐：waiting_user/terminal 事件与状态转移对齐 |

**目标文件**: `test_session_statechart_contract.py`（24 个测试）
**预期减少**: 3 个文件

**理由**: 四个文件都验证**会话状态机的正确性**，从不同角度（不变量、属性、合同、对齐）。合并后形成一个完整的 session state 测试套件，结构清晰。

---

### 合并组 K：Chat Replay Contract & Schema (2 → 1 文件)

| 源文件 | 测试数 | 为何可合并 |
|--------|--------|------------|
| `test_chat_replay_contract.py` | 1 | Chat replay 合同 YAML 验证：roles、kinds、invariants |
| `test_chat_replay_schema_registry.py` | 5 | Chat replay schema 验证：用户认证提交、历史响应、助手进程、助手消息、无效角色拒绝 |

**目标文件**: `test_chat_replay_contract.py`（6 个测试）
**预期减少**: 1 个文件

**理由**: 两个文件都验证 **chat replay 的 schema/合同层**。contract YAML 和 schema registry 是同一抽象层的不同方面。

---

### 合并组 L：Chat Replay Journal (2 → 1 文件)

| 源文件 | 测试数 | 为何可合并 |
|--------|--------|------------|
| `test_chat_replay_live_journal.py` | 2 | `chat_replay_live_journal`：publish/replay、游标后重放 |
| `test_chat_replay_publisher.py` | 1 | `ChatReplayPublisher`：从审计文件 bootstrap seq |

**目标文件**: `test_chat_replay_journal.py`（3 个测试）
**预期减少**: 1 个文件

**理由**: 都测试 chat replay 的 **journal/publish 机制**。live_journal 和 publisher 是同一子系统的两个组件。

---

### 合并组 M：FCMP Event Mapping (3 → 1 文件)

| 源文件 | 测试数 | 为何可合并 |
|--------|--------|------------|
| `test_fcmp_lifecycle_normalization.py` | 3 | 生命周期事件标准化：conversation lifecycle 简化为 state_changed |
| `test_fcmp_interaction_dedup.py` | 1 | 交互去重：waiting prompt 去重、reply preview 保留 |
| `test_fcmp_mapping_properties.py` | 6 | FCMP 事件映射属性：状态跟随、配对事件、终端一致性、输入需求、序列单调性 |

**目标文件**: `test_fcmp_event_mapping.py`（10 个测试）
**预期减少**: 2 个文件

**理由**: 三个文件都验证 **FCMP 事件映射的正确性**——生命周期标准化、交互去重、映射属性都是同一事件流处理管道的不同方面。

---

### 合并组 N：FCMP Global Sequence (2 → 1 文件)

| 源文件 | 测试数 | 为何可合并 |
|--------|--------|------------|
| `test_fcmp_cursor_global_seq.py` | 2 | 全局序列游标处理：seq 重写为全局单调、跨 attempt 的 SSE cursor |
| `test_fcmp_global_seq_persisted_files.py` | 1 | 全局序列持久化：fcmp_seq 全局、local_seq 持久化到文件 |

**目标文件**: `test_fcmp_global_seq.py`（3 个测试）
**预期减少**: 1 个文件

**理由**: 都测试 FCMP 的**全局序列机制**——一个测试游标/重写，一个测试持久化。合并后覆盖全局序列的完整行为。

---

### 合并组 O：Engine Adapter Registry (4 → 1 文件)

| 源文件 | 测试数 | 为何可合并 |
|--------|--------|------------|
| `test_engine_adapter_component_wiring.py` | 1 | 适配器组件接线：所有适配器继承基类 |
| `test_engine_adapter_entrypoints.py` | 1 | 适配器入口点：适配器直接用所有组件构建 |
| `test_engine_adapter_registry.py` | 3 | EngineAdapterRegistry：暴露所有适配器、未知引擎报错、opencode 构建/解析 |
| `test_engine_package_bootstrap.py` | 2 | 引擎包引导：执行适配器实例化、opencode auth 注册 |

**目标文件**: `test_engine_adapter_registry.py`（7 个测试）
**预期减少**: 3 个文件

**理由**: 四个文件都测试**引擎适配器的注册/引导/接线**。它们是同一系统的不同观察角度。

---

### 合并组 P：Config Generation (2 → 1 文件)

| 源文件 | 测试数 | 为何可合并 |
|--------|--------|------------|
| `test_config_generator.py` | 3 | ConfigGenerator JSON schema 验证：未知键告警、Claude env 处理、权限模式验证 |
| `test_codex_config.py` | 4 | CodexConfigManager TOML 操作：配置创建、profile 更新、注释保留、全局设置 |

**目标文件**: `test_config_generation.py`（7 个测试）
**预期减少**: 1 个文件

**理由**: 都测试**配置生成/操作逻辑**——一个生成 JSON schema，一个操作 TOML。都是配置工具链的一部分。

---

### 合并组 Q：System Services (3 → 1 文件)

| 源文件 | 测试数 | 为何可合并 |
|--------|--------|------------|
| `test_system_settings_service.py` | 4 | SystemSettingsService：引导缺失文件、原子更新、验证拒绝 |
| `test_system_log_explorer_service.py` | 3 | SystemLogExplorerService：日志查询过滤器、时间过滤、来源验证 |
| `test_container_runtime_defaults.py` | 2 | Dockerfile/compose 验证：非 root 用户、绑定挂载权限 |

**目标文件**: `test_system_services.py`（9 个测试）
**预期减少**: 2 个文件

**理由**: 都测试**系统级服务/配置**——settings、log explorer、container defaults 都是系统运行时的基础设施配置。

---

### 合并组 R：Runtime Protocol Ports (3 → 1 文件)

| 源文件 | 测试数 | 为何可合并 |
|--------|--------|------------|
| `test_runtime_profile.py` | 2 | Runtime profile：container defaults、local env overrides |
| `test_runtime_protocol_parser_resolver_port.py` | 1 | 解析器注入：使用注入的解析器进行解析 |
| `test_runtime_observability_port_injection.py` | 2 | 可观测性端口注入：run observability 端口、run read facade 结果验证 |

**目标文件**: `test_runtime_protocol_ports.py`（5 个测试）
**预期减少**: 2 个文件

**理由**: 都测试 **runtime 协议层的端口/接口**——profile、parser resolver、observability 都是协议端口概念。

---

### 合并组 S：Engine Interaction Management (2 → 1 文件)

| 源文件 | 测试数 | 为何可合并 |
|--------|--------|------------|
| `test_engine_interaction_gate.py` | 2 | EngineInteractionGate：单一活跃会话、冲突 scope 拒绝 |
| `test_engine_shell_capability_provider.py` | 1 | EngineShellCapabilityProvider：使用适配器 profile ui_shell 元数据 |

**目标文件**: `test_engine_interaction_management.py`（3 个测试）
**预期减少**: 1 个文件

**理由**: 都测试**引擎交互管理**——gate 控制并发会话，capability provider 提供 shell 能力。

---

### 合并总览

| 合并组 | 源文件数 | 目标文件数 | 减少文件数 | 测试数变化 |
|--------|---------|-----------|-----------|-----------|
| A. 架构迁移验证 | 4 | 1 | -3 | 4 → 4 |
| B. Import 边界守卫 | 7 | 1 | -6 | 7 → 7 |
| C. 文件系统快照忽略 | 2 | 1 | -1 | 2 → 2 |
| D. 信任文件夹策略 | 2 | 1 | -1 | 3 → 3 |
| E. OAuth Proxy 流 | 5 | 1 | -4 | 11 → 9 |
| F. Local Callback Server | 4 | 1 | -3 | 9 → ~7 |
| G. Auth Infrastructure | 4 | 1 | -3 | 10 → 10 |
| H. Auth Detection Per-Engine | 3 | 1 | -2 | 6 → 6 |
| I. Event Ordering Contract | 3 | 1 | -2 | 9 → 9 |
| J. Session Statechart | 4 | 1 | -3 | 24 → 24 |
| K. Chat Replay Contract | 2 | 1 | -1 | 6 → 6 |
| L. Chat Replay Journal | 2 | 1 | -1 | 3 → 3 |
| M. FCMP Event Mapping | 3 | 1 | -2 | 10 → 10 |
| N. FCMP Global Seq | 2 | 1 | -1 | 3 → 3 |
| O. Engine Adapter Registry | 4 | 1 | -3 | 7 → 7 |
| P. Config Generation | 2 | 1 | -1 | 7 → 7 |
| Q. System Services | 3 | 1 | -2 | 9 → 9 |
| R. Runtime Protocol Ports | 3 | 1 | -2 | 5 → 5 |
| S. Engine Interaction | 2 | 1 | -1 | 3 → 3 |
| **合计** | **61** | **19** | **-42** | **~1316 → ~1303** |

### 合并后的效果

- **文件数**: 196 → **154**（减少 21.4%）
- **测试数**: 1316 → **~1303**（基本不变，仅去除少量重复）
- **平均测试/文件**: 6.7 → **8.5**（更合理的粒度）
- **最大单文件测试数**: 24（`test_session_statechart_contract.py` 合并后）

### 实施顺序建议

1. **第一阶段（低风险）**：合并组 A-D（治理类，无业务逻辑变动）
2. **第二阶段（参数化改造）**：合并组 E-H（跨引擎 OAuth/callback/auth detection）
3. **第三阶段（领域聚合）**：合并组 I-J, M-N（runtime contract, FCMP）
4. **第四阶段（辅助合并）**：合并组 K-S（chat replay, engine adapter, config, services）

每个合并组完成后运行 `pytest` 确认全部通过，再进入下一组。
