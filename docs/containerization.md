# Containerization Guide

This guide describes a container setup that provides the runtime for Skill Runner
without bundling the agent CLIs into the image.

## Goals

- Use a Debian-based Node.js base image.
- Keep agent CLIs (codex/gemini/iflow) out of the image for fast upgrades.
- Mount `skills/` from the host for hot updates.
- Persist data, configs, and CLI installs via volumes.
- Centralize caches/packages under a single named volume.

## Files

- `Dockerfile`: runtime image (Node + Python 3.11).
- `docker-compose.yml`: recommended volume layout.
- `scripts/entrypoint.sh`: runtime checks + uvicorn start (baked into image).
- `scripts/agent_manager.sh`: ensures CLIs and writes status (baked into image).
- `scripts/upgrade_agents.sh`: upgrades CLIs via npm (baked into image).

## Volumes

The default compose file mounts:

- `./skills:/app/skills` (skills registry)
- `./agent_config:/opt/config` (CLI config root, symlinked to ~/.codex ~/.gemini ~/.iflow)
- `agent_cache:/opt/cache` (uv cache, uv venv, npm prefix)
- *(optional)* `./data:/data` (runs.db, runs/, requests/, logs)

## Agent CLI installation

The image does not ship the agent CLIs. Install them into the mounted prefix:

```
docker compose run --rm skill-runner sh -lc "npm install -g <cli-package>"
```

Install packages that provide `codex`, `gemini`, and `iflow` commands.

## Upgrading agent CLIs

Use the upgrade script to refresh installed CLIs inside the container:

```
./scripts/upgrade_agents.sh
```

## Agent CLI status

The entrypoint runs an agent check on startup and writes a status file:

- Path: `${SKILL_RUNNER_DATA_DIR:-/data}/agent_status.json`
- Fields: `present` and `version` per CLI

## Configuration & auth

- CLI configs are stored under `/opt/config` and symlinked to:
  - `/root/.codex`
  - `/root/.gemini`
  - `/root/.iflow`
- Provide API keys as environment variables or via CLI config files (preferred).
- Cache/package locations are centralized under `/opt/cache`:
  - `UV_CACHE_DIR=/opt/cache/uv_cache`
  - `UV_PROJECT_ENVIRONMENT=/opt/cache/uv_venv`
  - `NPM_CONFIG_PREFIX=/opt/cache/npm`
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
- Default config bootstrap:
  - If missing, the entrypoint writes `/opt/config/gemini/settings.json` with:
    - `security.auth.selectedType = "oauth-personal"`
  - If missing, the entrypoint writes `/opt/config/iflow/settings.json` with:
    - `selectedAuthType = "iflow"`

### Codex sandbox compatibility

Codex uses Landlock for sandboxing and requires Linux kernel >= 5.13. The
entrypoint detects the kernel version at startup and exports
`LANDLOCK_ENABLED=1/0`.

- `LANDLOCK_ENABLED=1`: Codex runs with `--full-auto`
- `LANDLOCK_ENABLED=0`: Codex runs with `--yolo`

### Agent CLI login workflows

You can authenticate the CLI tools in two ways. Both methods populate the
mounted `/opt/config` directory, which is symlinked to the expected `~/.codex`,
`~/.gemini`, and `~/.iflow` locations inside the container.

Method 1: Login inside the container (TUI)
- Start the container, then exec into it:
  - `docker exec -it <container_id> /bin/bash`
- Run the CLI login flow in TUI mode (per tool):
  - `codex` (creates `auth.json`)
  - `gemini` (creates `google_accounts.json`, `oauth_creds.json`)
  - `iflow` (creates `iflow_accounts.json`, `oauth_creds.json`)
- The files will appear under `/opt/config/<tool>/` via the mount.

Method 2: Login on another machine and copy credentials
- Login on any machine where the CLI works.
- Copy the credential files into the host-mounted directories:
  - Codex → `agent_config/codex/auth.json`
  - Gemini → `agent_config/gemini/google_accounts.json`, `agent_config/gemini/oauth_creds.json`
  - iFlow → `agent_config/iflow/iflow_accounts.json`, `agent_config/iflow/oauth_creds.json`
- Restart the container to pick up the new files (if needed).

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
  -e UV_CACHE_DIR=/opt/cache/uv_cache \
  -e UV_PROJECT_ENVIRONMENT=/opt/cache/uv_venv \
  -e NPM_CONFIG_PREFIX=/opt/cache/npm \
  -e SKILL_RUNNER_DATA_DIR=/data \
  -v "$(pwd)/skills:/app/skills" \
  -v "$(pwd)/agent_config:/opt/config" \
  -v skill-runner_cache:/opt/cache \
  skill-runner:local
```
