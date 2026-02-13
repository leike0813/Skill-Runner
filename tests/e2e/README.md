# REST E2E Tests

This suite runs REST-level end-to-end tests against the in-process FastAPI app
using TestClient. Test cases are sourced from `tests/suites/*.yaml`, matching
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

Container bundle downloads are saved under:
`/home/joshua/Workspace/Code/Skill-Runner/e2e-test-download/<request_id>/`.

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

Input rule:
- If a skill defines an input schema and the case has no inputs, the runner
  uploads an empty zip to trigger input validation.
