#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

openspec validate add-codebuddy-code-engine --strict
git diff --check
conda run --no-capture-output -n DataProcessing python -u -m pytest tests/unit
conda run --no-capture-output -n DataProcessing python -u -m pytest tests/api_integration/test_e2e_example_client.py
conda run --no-capture-output -n DataProcessing python -u -m pytest \
  tests/engine_integration/test_codebuddy_golden_integration.py \
  tests/engine_integration/test_golden_corpus_completeness.py
conda run --no-capture-output -n DataProcessing python -u scripts/scan_codebuddy_secrets.py \
  artifacts/codebuddy_release_gate.json
conda run --no-capture-output -n DataProcessing python -u -m pytest \
  tests/unit/test_session_invariant_contract.py \
  tests/unit/test_session_state_model_properties.py \
  tests/unit/test_fcmp_mapping_properties.py \
  tests/unit/test_protocol_state_alignment.py \
  tests/unit/test_protocol_schema_registry.py \
  tests/unit/test_runtime_event_protocol.py \
  tests/unit/test_run_observability.py
