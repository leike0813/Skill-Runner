# REST E2E Tests

This suite runs REST-level end-to-end tests against the in-process FastAPI app
using TestClient. Test cases are sourced from `tests/engine_integration/suites/*.yaml`, matching
the input format used by the integration runner. Use the wrapper script for
environment setup and filtering.

Run:
```
tests/e2e/run_e2e_tests.sh -k demo-bible-verse -e gemini --no-cache
```

Container run (targets a running service, default `http://localhost:8000`):
```
tests/e2e/run_container_e2e_tests.sh -k demo-bible-verse -e gemini --no-cache
```

Run Local E2E Tests (auto-start local deploy chain, then test via REST):
```
tests/e2e/run_local_e2e_tests.sh -k demo-bible-verse -e gemini --no-cache
```
Local E2E fail-fast behavior:
- By default, if `--base-url` is already serving, the runner exits immediately to avoid reusing stale services.
- Use `--reuse-existing-service` only when you intentionally target an already-running service.
- `--keep-server` only applies to services started by the current local E2E process.

Bundle downloads are saved under:
`$E2E_DOWNLOAD_DIR/<request_id>/`.
If not set, wrappers default to `<project_root>/e2e-test-download`.

Useful environment overrides:
- `E2E_DOWNLOAD_DIR` (or `SKILL_RUNNER_E2E_DOWNLOAD_DIR` in wrappers): bundle download root
- `SKILL_RUNNER_DATA_DIR`: in-process E2E data root
- `UV_CACHE_DIR`, `UV_PROJECT_ENVIRONMENT`: uv cache and venv paths

Shared wrapper environment:
- `tests/config/test_env.sh` is the single source for test wrapper directory defaults.
- E2E and integration wrappers both source this file.

Covered behaviors:
- `POST /v1/jobs` and `POST /v1/jobs/{request_id}/upload`
- `POST /v1/temp-skill-runs` and `POST /v1/temp-skill-runs/{request_id}/upload`
- `GET /v1/jobs/{request_id}` status polling
- `GET /v1/temp-skill-runs/{request_id}` status polling
- `GET /v1/jobs/{request_id}/result`
- `GET /v1/temp-skill-runs/{request_id}/result`
- `GET /v1/jobs/{request_id}/artifacts` (列表)
- `GET /v1/temp-skill-runs/{request_id}/artifacts` (列表)
- `GET /v1/jobs/{request_id}/bundle` (下载 bundle)
- `GET /v1/temp-skill-runs/{request_id}/bundle` (下载 bundle)
- `runtime_options.no_cache` with both `true` and `false`

Engine mismatch rule:
- Installed skill (`skill_source=installed`): mismatch should be rejected at job creation.
- Temporary skill (`skill_source=temp`): mismatch should be rejected at temp upload/start.

Demo suites (`demo-*`) are configured with `skill_source=temp` and are uploaded
from `tests/fixtures/skills/*` at runtime, so they do not require pre-installing
demo skills into the service `skills/` directory.

Input rule:
- If a skill defines an input schema and the case has no inputs, the runner
  uploads an empty zip to trigger input validation.
