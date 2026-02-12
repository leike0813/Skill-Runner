# Skill Runner

For the Chinese version, see `README_CN.md`.

Skill Runner is a lightweight REST service that wraps Codex, Gemini CLI, and
iFlow CLI behind a unified Skill protocol for deterministic execution and
artifact management.

## Features

- Multi-engine execution: Codex / Gemini CLI / iFlow CLI
- Skill protocol: `runner.json` + `SKILL.md` + input/parameter/output schemas
- Isolated runs with reproducible artifacts
- Structured results: JSON + artifacts + bundle
- Cache reuse for identical inputs and parameters
- Web admin UI at `/ui` for skill overview and package install
- Skill browser at `/ui/skills/{skill_id}` for read-only package/file inspection
- Engine management at `/ui/engines` for status, upgrades, and upgrade logs
- Model manifest management at `/ui/engines/{engine}/models` for snapshot view/add

## Container build & run

Prepare host directories to avoid permission issues:
```
mkdir -p skills agent_config data
```
> `data` is optional and only needed when you want to persist run data or debug.

Build the image:
```
docker build -t skill-runner:local .
```

Start with Compose:
```
docker compose up --build
```

Default API base: `http://localhost:8000/v1`
Admin UI: `http://localhost:8000/ui`

See `docs/containerization.md` for details.

To protect the admin/install surfaces with Basic Auth:
- `UI_BASIC_AUTH_ENABLED=true`
- `UI_BASIC_AUTH_USERNAME=<username>`
- `UI_BASIC_AUTH_PASSWORD=<password>`

## Local development (non-container)

Recommended environment setup with `uv`:
```
uv venv
source .venv/bin/activate
uv pip install -e ".[dev]"
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

Optional environment:
- `SKILL_RUNNER_DATA_DIR`: run data directory (default `data/`)

To quickly verify UI Basic Auth locally, use:
```
./scripts/start_ui_auth_server.sh
```

Override defaults when needed:
```
UI_BASIC_AUTH_USERNAME=admin \
UI_BASIC_AUTH_PASSWORD=secret \
PORT=8011 \
./scripts/start_ui_auth_server.sh
```

Quick checks:
```
curl -i http://127.0.0.1:8000/ui
curl -i -u admin:change-me http://127.0.0.1:8000/ui
```

## API examples

List skills:
```
curl -sS http://localhost:8000/v1/skills
```

List engines and models:
```
curl -sS http://localhost:8000/v1/engines
curl -sS http://localhost:8000/v1/engines/gemini/models
```

View engine manifest (with Basic Auth when enabled):
```
curl -sS -u admin:change-me http://localhost:8000/v1/engines/codex/models/manifest
```

Create and poll an engine upgrade task (with Basic Auth when enabled):
```
curl -sS -u admin:change-me -X POST http://localhost:8000/v1/engines/upgrades \
  -H "Content-Type: application/json" \
  -d '{"mode":"single","engine":"gemini"}'
curl -sS -u admin:change-me http://localhost:8000/v1/engines/upgrades/<request_id>
```

Create a job:
```
curl -sS -X POST http://localhost:8000/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "skill_id": "demo-bible-verse",
    "engine": "gemini",
    "parameter": { "language": "en" },
    "model": "gemini-3-pro-preview",
    "runtime_options": { "no_cache": false, "debug": false }
  }'
```

Upload inputs:
```
curl -sS -X POST http://localhost:8000/v1/jobs/<request_id>/upload \
  -F "file=@inputs.zip"
```

Poll status and result:
```
curl -sS http://localhost:8000/v1/jobs/<request_id>
curl -sS http://localhost:8000/v1/jobs/<request_id>/result
```

Artifacts and bundle:
```
curl -sS http://localhost:8000/v1/jobs/<request_id>/artifacts
curl -sS -o run_bundle.zip http://localhost:8000/v1/jobs/<request_id>/bundle
```

Codex model format:
- `model_name@reasoning_effort` (example: `gpt-5.2-codex@high`)

Full API details: `docs/api_reference.md`.

## Architecture (brief)

- Skill Registry scans `skills/`
- Workspace Manager prepares run directories
- Job Orchestrator validates inputs/outputs, executes, and bundles results
- Engine Adapters integrate Codex / Gemini / iFlow CLIs

Flow:
1) POST /v1/jobs  
2) Optional inputs.zip upload  
3) Engine execution  
4) Output validation + bundle  
5) GET results and downloads

## Agent CLI login

Method 1: Login inside container (TUI)
```
docker exec -it <container_id> /bin/bash
```
Run the CLI login flow in the container.

Method 2: Login elsewhere and copy credentials

Required files:
- Codex: `auth.json`
- Gemini: `google_accounts.json`, `oauth_creds.json`
- iFlow: `iflow_accounts.json`, `oauth_creds.json`

Copy to:
- `agent_config/codex/`
- `agent_config/gemini/`
- `agent_config/iflow/`

## Supported engines

- Codex CLI (`@openai/codex`)
- Gemini CLI (`@google/gemini-cli`)
- iFlow CLI (`@iflow-ai/iflow-cli`)

---

See `docs/` for more details.
