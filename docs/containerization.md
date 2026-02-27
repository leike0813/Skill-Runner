# Containerization Guide

This guide describes a container setup that provides the runtime for Skill Runner
without bundling the agent CLIs into the image.

## Goals

- Use a Debian-based Node.js base image.
- Keep agent CLIs (codex/gemini/iflow/opencode) out of the image for fast upgrades.
- Mount `skills/` from the host for hot updates.
- Persist data, configs, and CLI installs via volumes.
- Centralize caches/packages under a single named volume.

## Files

- `Dockerfile`: runtime image (Node + Python 3.11).
- `docker-compose.yml`: recommended volume layout.
- `scripts/entrypoint.sh`: runtime checks + uvicorn start (baked into image).
- `scripts/agent_manager.py`: cross-platform Engine manager (ensure/check/upgrade/import credentials).
- `scripts/agent_manager.sh`: thin shell wrapper to `agent_manager.py`.
- `scripts/upgrade_agents.sh`: upgrade wrapper (`local` / `container` mode).
- `scripts/deploy_local.sh` / `scripts/deploy_local.ps1`: one-click local deployment.

## Volumes

The default compose file mounts:

- `./skills:/app/skills` (skills registry)
- `./agent_config:/opt/config` (credential import source; optional)
- `agent_cache:/opt/cache` (contains isolated agent home + uv cache + npm prefix)
- *(optional)* `./data:/data` (runs.db, runs/, requests/, logs)

## Agent CLI installation

The image does not ship the agent CLIs. Install them into the mounted prefix:

```
docker compose run --rm skill-runner sh -lc "npm install -g <cli-package>"
```

Install packages that provide `codex`, `gemini`, and `iflow` commands.

## Upgrading agent CLIs

Use the upgrade script to refresh installed CLIs:

```
./scripts/upgrade_agents.sh local
./scripts/upgrade_agents.sh container
```

## Agent CLI status

The entrypoint runs an agent check on startup and writes a status file:

- Path: `${SKILL_RUNNER_DATA_DIR:-/data}/agent_status.json`
- Fields: `present` and `version` per CLI

## Configuration, isolation & auth

- Skill Runner now uses an **isolated Agent Home** by default:
  - `SKILL_RUNNER_AGENT_HOME=/opt/cache/skill-runner/agent-home`
  - CLIs read/write config under:
    - `${SKILL_RUNNER_AGENT_HOME}/.codex`
    - `${SKILL_RUNNER_AGENT_HOME}/.gemini`
    - `${SKILL_RUNNER_AGENT_HOME}/.iflow`
    - `${SKILL_RUNNER_AGENT_HOME}/.config/opencode`
    - `${SKILL_RUNNER_AGENT_HOME}/.local/share/opencode`
- Engine CLI install/upgrade/check always use managed prefix:
  - `SKILL_RUNNER_NPM_PREFIX=/opt/cache/skill-runner/npm`
  - `NPM_CONFIG_PREFIX=/opt/cache/skill-runner/npm`
- Cache locations are centralized under `/opt/cache/skill-runner`:
  - `SKILL_RUNNER_AGENT_CACHE_DIR=/opt/cache/skill-runner`
  - `UV_CACHE_DIR=/opt/cache/skill-runner/uv_cache`
  - `UV_PROJECT_ENVIRONMENT=/opt/cache/skill-runner/uv_venv`
- Runtime data remains independent:
  - `SKILL_RUNNER_DATA_DIR=/data`
- Concurrency policy (optional env overrides):
  - `SKILL_RUNNER_MAX_CONCURRENT_HARD_CAP`
  - `SKILL_RUNNER_MAX_QUEUE_SIZE`
  - `SKILL_RUNNER_CPU_FACTOR`
  - `SKILL_RUNNER_MEM_RESERVE_MB`
  - `SKILL_RUNNER_ESTIMATED_MEM_PER_RUN_MB`
  - `SKILL_RUNNER_FD_RESERVE`
  - `SKILL_RUNNER_ESTIMATED_FD_PER_RUN`
  - `SKILL_RUNNER_PID_RESERVE`
  - `SKILL_RUNNER_ESTIMATED_PID_PER_RUN`
  - `SKILL_RUNNER_FALLBACK_MAX_CONCURRENT`
- UI Basic Auth (optional, recommended for exposed deployments):
  - `UI_BASIC_AUTH_ENABLED` (`true` / `false`, default `false`)
  - `UI_BASIC_AUTH_USERNAME`
  - `UI_BASIC_AUTH_PASSWORD`
  - These are runtime environment variables and are not baked into image `ENV`.
  - Set them in `docker-compose.yml` (`services.api.environment`) or via `docker run -e`.
  - When enabled, `/ui/*` and `/v1/skill-packages/*` require Basic Auth.
  - If enabled but username/password are missing, app startup fails fast.

Example compose config:
```yaml
services:
  api:
    environment:
      UI_BASIC_AUTH_ENABLED: "true"
      UI_BASIC_AUTH_USERNAME: "admin"
      UI_BASIC_AUTH_PASSWORD: "change-me"
```

Example docker run:
```bash
docker run --rm -p 8000:8000 -p 7681:7681 \
  -e UI_BASIC_AUTH_ENABLED=true \
  -e UI_BASIC_AUTH_USERNAME=admin \
  -e UI_BASIC_AUTH_PASSWORD=change-me \
  leike0813/skill-runner:v0.3.3
```
- UI includes read-only skill browser endpoints:
    - `/ui/skills/{skill_id}`
    - `/ui/skills/{skill_id}/view?path=<relative_path>`
  - UI also provides inline managed TUI on `/ui/engines`:
    - per-engine “start TUI” buttons (predefined commands only)
    - single active session globally
    - powered by `ttyd` gateway (default port `7681`)
    - compose example exposes `7681:7681` for browser access
  - Optional ttyd runtime options:
    - `UI_SHELL_TTYD_BIND_HOST` (default `0.0.0.0`)
    - `UI_SHELL_TTYD_PORT` (default `7681`)
- Default config bootstrap (inside isolated Agent Home):
  - If missing, the entrypoint writes `${SKILL_RUNNER_AGENT_HOME}/.gemini/settings.json` with:
    - `security.auth.selectedType = "oauth-personal"`
  - If missing, the entrypoint writes `${SKILL_RUNNER_AGENT_HOME}/.iflow/settings.json` with:
    - `selectedAuthType = "oauth-iflow"`
    - `baseUrl = "https://apis.iflow.cn/v1"`
  - If missing, the entrypoint writes `${SKILL_RUNNER_AGENT_HOME}/.codex/config.toml` with:
    - `cli_auth_credentials_store = "file"`
  - If missing, the entrypoint writes `${SKILL_RUNNER_AGENT_HOME}/.config/opencode/opencode.json` with:
    - `plugin = ["opencode-antigravity-auth"]`
  - Entry-point trust bootstrap (idempotent):
    - Creates/repairs `${SKILL_RUNNER_AGENT_HOME}/.gemini/trustedFolders.json` as a JSON object.
    - Adds runs parent trust to Gemini:
      - `"<SKILL_RUNNER_DATA_DIR>/runs": "TRUST_FOLDER"`
    - Adds runs parent trust to Codex:
      - `projects."<SKILL_RUNNER_DATA_DIR>/runs".trust_level = "trusted"`

### Run-folder trust lifecycle (runtime)

- For each run on `codex`/`gemini`, orchestrator writes a per-run trust entry before CLI launch.
- After execution (success/failure), orchestrator removes that per-run trust entry in `finally`.
- If cleanup fails, run status is not changed; stale entries are retried by periodic cleanup.

### Codex sandbox compatibility

Codex uses Landlock for sandboxing and requires Linux kernel >= 5.13. The
entrypoint detects the kernel version at startup and exports
`LANDLOCK_ENABLED=1/0`.

- `LANDLOCK_ENABLED=1`: Codex runs with `--full-auto`
- `LANDLOCK_ENABLED=0`: Codex runs with `--yolo`

### Agent CLI login workflows

You can authenticate the CLI tools in two ways. The service runs in isolated
Agent Home mode. If `/opt/config` is mounted, entrypoint imports **credentials only**
from `/opt/config` into isolated Agent Home (settings are not imported).

Method 1: Login inside the container (TUI)
- Start the container, then exec into it:
  - `docker exec -it <container_id> /bin/bash`
- Run the CLI login flow in TUI mode (per tool, in isolated Agent Home):
  - `codex login` (browser OAuth, creates `auth.json`)
  - `codex login --device-auth` (device auth)
  - `gemini` (creates `google_accounts.json`, `oauth_creds.json`)
  - `iflow` (creates `iflow_accounts.json`, `oauth_creds.json`)
  - `opencode` (creates `.local/share/opencode/auth.json`; plugin auth may create `.config/opencode/antigravity-accounts.json`)
- The files are stored under isolated Agent Home:
  - Codex/Gemini/iFlow: `${SKILL_RUNNER_AGENT_HOME}/.<tool>/...`
  - OpenCode: `${SKILL_RUNNER_AGENT_HOME}/.local/share/opencode/auth.json` and `${SKILL_RUNNER_AGENT_HOME}/.config/opencode/antigravity-accounts.json`

Method 2: Login on another machine and copy credentials
- Login on any machine where the CLI works.
- Copy credential files into host-mounted import source:
  - Codex → `agent_config/codex/auth.json`
  - Gemini → `agent_config/gemini/google_accounts.json`, `agent_config/gemini/oauth_creds.json`
  - iFlow → `agent_config/iflow/iflow_accounts.json`, `agent_config/iflow/oauth_creds.json`
  - OpenCode → `agent_config/opencode/auth.json` (required), `agent_config/opencode/antigravity-accounts.json` (optional)
- Restart the container (or rerun `agent_manager.py --import-credentials /opt/config`) to import.

OpenAI OAuth proxy note:
- Skill Runner `oauth_proxy` for `codex` and `opencode/openai` starts a per-session local callback listener (`127.0.0.1:1455`) and stops it when session finishes.
- `callback` 模式支持 `/input` 兜底（远程部署且本地回调不可达时可手工回填）。
- `gemini` `oauth_proxy` 提供两种模式：
  - `callback`：依赖本地 listener（`127.0.0.1:51122/oauth2callback`）
  - `auth_code_or_url`：手工码流，通过 `/input` 回填
- `gemini` `oauth_proxy` only updates `.gemini/oauth_creds.json` (and optional `google_accounts.json`), and does not write `mcp-oauth-tokens-v2.json` in phase1.
- Gemini OAuth 代理需要注入：
  - `SKILL_RUNNER_GEMINI_OAUTH_CLIENT_ID`
  - `SKILL_RUNNER_GEMINI_OAUTH_CLIENT_SECRET`
- `iflow` `oauth_proxy` 提供两种模式：
  - `callback`：自动回调优先（`127.0.0.1:11451/oauth2callback`），并支持 `/input` 兜底
  - `auth_code_or_url`：手工码流，通过 `/input` 回填
- `iflow` `oauth_proxy` 成功后会更新 `.iflow/oauth_creds.json`、`.iflow/iflow_accounts.json` 和 `.iflow/settings.json`。
- `opencode/google` `oauth_proxy` (Antigravity browser OAuth) starts a per-session local callback listener on `127.0.0.1:51121` (`/oauth-callback`) and also supports `/input` fallback.
- OpenCode Google（Antigravity）OAuth 代理需要注入：
  - `SKILL_RUNNER_OPENCODE_GOOGLE_OAUTH_CLIENT_ID`
  - `SKILL_RUNNER_OPENCODE_GOOGLE_OAUTH_CLIENT_SECRET`
- Auth session logs are separated by transport:
  - `data/engine_auth_sessions/oauth_proxy/<session_id>/events.jsonl`, `http_trace.log`
  - `data/engine_auth_sessions/cli_delegate/<session_id>/events.jsonl`, `pty.log`, `stdin.log`

### Web inline terminal notes

- In container deployments, `/ui/engines` inline terminal runs commands in managed runtime env.
- In local Windows deployments, this feature relies on `pywinpty`; if missing, the UI returns a clear dependency error.

## Start the service

```
docker compose up --build
```

The API will be available at `http://localhost:8000/v1`.

## Build and run locally

Build the image directly:

```
docker build -t skill-runner:local .
```

Run the container with the same mounts as compose (example):

```
docker run --rm -p 8000:8000 \
  -e UV_CACHE_DIR=/opt/cache/skill-runner/uv_cache \
  -e UV_PROJECT_ENVIRONMENT=/opt/cache/skill-runner/uv_venv \
  -e SKILL_RUNNER_AGENT_CACHE_DIR=/opt/cache/skill-runner \
  -e SKILL_RUNNER_AGENT_HOME=/opt/cache/skill-runner/agent-home \
  -e SKILL_RUNNER_NPM_PREFIX=/opt/cache/skill-runner/npm \
  -e NPM_CONFIG_PREFIX=/opt/cache/skill-runner/npm \
  -e SKILL_RUNNER_DATA_DIR=/data \
  -v "$(pwd)/skills:/app/skills" \
  -v "$(pwd)/agent_config:/opt/config" \
  -v skill-runner_cache:/opt/cache \
  skill-runner:local
```
