# Containerization Guide

This guide describes a container setup that packages backend API and built-in E2E client
into the same image with different entrypoints. Agent CLIs are still not bundled in image.

## Goals

- Use a Debian-based Node.js base image.
- Keep agent CLIs (codex/gemini/qwen/opencode/claude) out of the image for fast upgrades.
- Use host bind mount `./skills:/app/skills` by default for user skill management.
- Persist data, configs, and CLI installs via volumes.
- Centralize caches/packages under managed named volumes.

## Files

- `Dockerfile`: runtime image (Node + Python 3.11).
- `docker-compose.yml`: local development compose (build-first; `api` enabled by default; optional commented `e2e_client` block).
- `docker-compose.release.tmpl.yml`: release compose template (image-first; rendered in CI).
- `scripts/render_release_compose.py`: render `docker-compose.release.yml` from template + image tag.
- `scripts/entrypoint.sh`: runtime checks + uvicorn start (baked into image).
- `scripts/entrypoint_e2e.sh`: built-in E2E client entrypoint (same image, different startup path).
- `scripts/agent_manager.py`: cross-platform Engine manager (ensure/check/upgrade).
- `scripts/agent_manager.sh`: thin shell wrapper to `agent_manager.py`.
- `scripts/agent_harness_container.sh`: host-side wrapper to run containerized `agent-harness` through `docker compose exec api`.
- `scripts/deploy_local.sh` / `scripts/deploy_local.ps1`: one-click local deployment.
- `scripts/skill-runnerctl` / `scripts/skill-runnerctl.ps1`: plugin-friendly lifecycle control CLI (`install/preflight/up/down/status/doctor`).
- `scripts/skill-runner-install.sh` / `scripts/skill-runner-install.ps1`: release installer scripts with SHA256 verification.
- `scripts/skill-runner-uninstall.sh` / `scripts/skill-runner-uninstall.ps1`: plugin-friendly uninstall scripts with optional data/agent-home cleanup.

## Release Assets (Tag Builds)

For each `v*` tag, CI publishes installer-facing release assets:

- `docker-compose.release.yml`
- `docker-compose.release.yml.sha256`
- `skill-runner-<version>.tar.gz`
- `skill-runner-<version>.tar.gz.sha256`

The source package includes repository files plus `skills_builtin/*` submodule contents, and embeds
`release_integrity_manifest.json` for file-level preflight integrity verification.

## Volumes

The default compose file mounts:

- `./skills:/app/skills` (user skills registry; editable from host)
- `skillrunner_cache:/opt/cache` (contains isolated agent home + uv cache + npm prefix)
- *(optional)* `./data:/data` (runs.db, runs/, logs, settings)

Containers run as a fixed non-root user by default. If you enable the optional
`./data:/data` bind mount, the host `./data` directory must be writable by that
container user. A permissive fallback such as `chmod 777 ./data` works, but it
is an operator-side convenience tradeoff rather than the recommended default.

Builtin skills are packaged in-image under `/app/skills_builtin` (read-only source).
User-installable skills live under `/app/skills` (volume/bind mount target).

## Agent CLI installation

The image does not ship the agent CLIs. Install them into the mounted prefix:

```
docker compose run --rm api sh -lc "npm install -g <cli-package>"
```

Install packages that provide `codex`, `gemini`, `qwen`, `opencode`, and `claude` commands.

## Upgrading agent CLIs

Use `agent_manager.py` directly to refresh installed CLIs:

Local:

```bash
uv run python scripts/agent_manager.py --upgrade
```

Container:

```bash
docker compose exec api python3 /app/scripts/agent_manager.py --upgrade
```

Legacy helper wrappers were moved out of `scripts/` and are no longer recommended as the primary entrypoint.

## Plugin integration lifecycle (local mode)

For Zotero/local desktop integration, prefer `skill-runnerctl` instead of calling `deploy_local.*` directly:

```bash
./scripts/skill-runnerctl install --json
./scripts/skill-runnerctl preflight --json
./scripts/skill-runnerctl up --mode local --json
sh ./scripts/skill-runner-uninstall.sh --json
```

Recommended plugin chain is `preflight -> up -> acquire lease` (no regular status polling).  
`preflight` now includes file-level integrity verification against `release_integrity_manifest.json`; integrity failures should be handled as blocking and trigger reinstall guidance.  
If `up` fails, call `status --mode local --json` and `doctor --json` for diagnostics.

`skill-runnerctl` local defaults:

- Linux/macOS LocalRoot: `${SKILL_RUNNER_LOCAL_ROOT:-$HOME/.local/share/skill-runner}`
- Windows LocalRoot: `${SKILL_RUNNER_LOCAL_ROOT:-%LOCALAPPDATA%\\SkillRunner}`
- `SKILL_RUNNER_DATA_DIR` default: `<LocalRoot>/data` (override still supported via env var)
- `SKILL_RUNNER_SKILLS_DIR` default: `<LocalRoot>/skills` (override still supported via env var)
- `SKILL_RUNNER_LOCAL_PORT` default: `29813`
- `SKILL_RUNNER_LOCAL_PORT_FALLBACK_SPAN` default: `10` (tries `29813-29823`)
- `deploy_local.*` default data dir remains `PROJECT_ROOT/data`
- service general default port remains `9813` when `PORT` is unset

Uninstall options:

- `--clear-data` / `-ClearData`: also remove `<LocalRoot>/data`
- `--clear-agent-home` / `-ClearAgentHome`: also remove `<LocalRoot>/agent-cache/agent-home`
- both enabled: attempt to remove whole `<LocalRoot>`

Local mode defaults to loopback bind (`127.0.0.1`) and supports lease-driven lifecycle APIs:

- `POST /v1/local-runtime/lease/acquire`
- `POST /v1/local-runtime/lease/heartbeat`
- `POST /v1/local-runtime/lease/release`

If all leases expire or are released, local runtime can self-terminate (TTL default: 60s).

## Agent CLI status

The entrypoint and application startup refresh engine versions and persist status into SQLite:

- Database: `${SKILL_RUNNER_DATA_DIR:-/data}/runs.db`
- Table: `engine_status_cache`
- Fields: `engine`, `present`, `version`, `updated_at`

## Configuration, isolation & auth

- Skill Runner now uses an **isolated Agent Home** by default:
  - `SKILL_RUNNER_AGENT_HOME=/opt/cache/skill-runner/agent-home`
  - CLIs read/write config under:
    - `${SKILL_RUNNER_AGENT_HOME}/.codex`
    - `${SKILL_RUNNER_AGENT_HOME}/.gemini`
    - `${SKILL_RUNNER_AGENT_HOME}/.qwen`
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
- Runtime-editable system settings persist at:
  - `${SKILL_RUNNER_DATA_DIR}/system_settings.json`
  - This file stores the UI-editable logging settings shown on `/ui/settings`
  - If missing, the service bootstraps it from `server/config/policy/system_settings.bootstrap.json`
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
docker run --rm -p 9813:9813 -p 17681:17681 \
  -e UI_BASIC_AUTH_ENABLED=true \
  -e UI_BASIC_AUTH_USERNAME=admin \
  -e UI_BASIC_AUTH_PASSWORD=change-me \
  leike0813/skill-runner:v0.3.3
```
- UI includes read-only skill browser endpoints:
    - `/ui/skills/{skill_id}`
    - `/ui/skills/{skill_id}/view?path=<relative_path>`
  - UI also provides inline managed TUI on `/ui/engines`:
    - engine table reads cached versions from `runs.db.engine_status_cache`
    - per-engine “start TUI” buttons (predefined commands only)
    - single active session globally
    - powered by `ttyd` gateway (default port `17681`)
    - compose example exposes `17681:17681` for browser access
  - Optional ttyd runtime options:
    - `UI_SHELL_TTYD_BIND_HOST` (default `0.0.0.0`)
    - `UI_SHELL_TTYD_PORT` (default `17681`)
- Default config bootstrap (inside isolated Agent Home):
  - If missing, the entrypoint writes `${SKILL_RUNNER_AGENT_HOME}/.gemini/settings.json` with:
    - `security.auth.selectedType = "oauth-personal"`
  - If missing, the entrypoint writes `${SKILL_RUNNER_AGENT_HOME}/.qwen/settings.json` with:
    - `general.enableAutoUpdate = false`
    - `general.checkpointing.enabled = false`
  - If missing, the entrypoint writes `${SKILL_RUNNER_AGENT_HOME}/.codex/config.toml` with:
    - `cli_auth_credentials_store = "file"`
  - If missing, the entrypoint writes `${SKILL_RUNNER_AGENT_HOME}/.claude.json` with:
    - `hasCompletedOnboarding = true`
    - Note: Claude bootstrap writes the global state file `.claude.json`, not `.claude/settings.json`
  - If missing, the entrypoint writes `${SKILL_RUNNER_AGENT_HOME}/.config/opencode/opencode.json` with:
    - `plugin = ["opencode-antigravity-auth"]`
  - Runtime-generated OpenCode run config (`run_dir/opencode.json`) also applies an enforced provider policy:
    - known provider `options.timeout = false`
    - this is intentional to avoid long-running SSE responses being aborted by OpenCode's default 5-minute provider timeout
    - enforced config has higher priority than skill defaults and runtime `opencode_config` overrides
- Claude runtime config remains separate from bootstrap:
    - bootstrap initializes `${SKILL_RUNNER_AGENT_HOME}/.claude.json`
    - each run still generates run-local `run_dir/.claude/settings.json`
    - headless run / harness use run-local settings with:
      - `permissions.defaultMode = "bypassPermissions"`
      - `sandbox.enabled = true`
      - `sandbox.allowUnsandboxedCommands = false`
      - sandbox filesystem write scope constrained to `run_dir`
    - Claude sandbox in containerized deployments depends on both `bubblewrap` (`bwrap`) and `socat`
    - The runtime image installs both dependencies so Claude sandbox can start normally inside Docker
    - The official container image runs as a non-root user by default; this is required for Claude headless runs that rely on bypass permissions mode
    - If either dependency is missing, or sandbox initialization later fails at runtime, Skill Runner records a warning/diagnostic but does not block the run
    - inline UI shell uses a separate session-local `.claude/settings.json` with a much stricter posture:
      - `permissions.defaultMode = "dontAsk"`
      - tools denied by default, except lightweight network access used for auth / simple Q&A
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

You can authenticate the CLI tools through managed flows while running in isolated Agent Home mode.

Method 1: Login inside the container (TUI)
- Start the container, then exec into it:
  - `docker exec -it <container_id> /bin/bash`
- Run the CLI login flow in TUI mode (per tool, in isolated Agent Home):
  - `codex login` (browser OAuth, creates `auth.json`)
  - `codex login --device-auth` (device auth)
  - `gemini` (creates `google_accounts.json`, `oauth_creds.json`)
  - `qwen` (creates `.qwen/oauth_creds.json`, or writes `.qwen/settings.json` for Coding Plan API Key)
  - `opencode` (creates `.local/share/opencode/auth.json`; plugin auth may create `.config/opencode/antigravity-accounts.json`)
- The files are stored under isolated Agent Home:
  - Codex/Gemini/Qwen: `${SKILL_RUNNER_AGENT_HOME}/.<tool>/...`
  - OpenCode: `${SKILL_RUNNER_AGENT_HOME}/.local/share/opencode/auth.json` and `${SKILL_RUNNER_AGENT_HOME}/.config/opencode/antigravity-accounts.json`

Method 2: Import credential files from Admin UI
- Open `/ui/engines`.
- Choose engine/provider auth menu entry: **Import Credentials**.
- Upload required files. Service validates payload structure and writes to isolated Agent Home.

### Harness usage

- Local runtime: run `agent-harness ...` directly in the current environment.
- Container runtime: use the supported wrapper from the project root:

```bash
./scripts/agent_harness_container.sh start codex --json --full-auto -p skill-runner-harness "hello"
```

- The wrapper always targets the `api` service with `docker compose exec`; it does not change the semantics of the local `agent-harness` CLI.

OpenAI OAuth proxy note:
- Skill Runner `oauth_proxy` for `codex` and `opencode/openai` starts a per-session local callback listener (`127.0.0.1:1455`) and stops it when session finishes.
- `callback` 模式支持 `/input` 兜底（远程部署且本地回调不可达时可手工回填）。
- `/ui/engines` 的鉴权入口采用全局后台下拉（`oauth_proxy` / `cli_delegate`）+ 引擎单入口菜单；鉴权进行中会禁用后台切换。
- `gemini` `oauth_proxy` 提供两种模式：
  - `callback`：依赖本地 listener（`127.0.0.1:51122/oauth2callback`）
  - `auth_code_or_url`：手工码流，通过 `/input` 回填
- `gemini` `oauth_proxy` only updates `.gemini/oauth_creds.json` (and optional `google_accounts.json`), and does not write `mcp-oauth-tokens-v2.json` in phase1.
- Gemini OAuth 代理需要注入：
  - `SKILL_RUNNER_GEMINI_OAUTH_CLIENT_ID`
  - `SKILL_RUNNER_GEMINI_OAUTH_CLIENT_SECRET`
- `qwen(provider_id=qwen-oauth)` 使用设备码语义，服务端自动轮询并更新 `.qwen/oauth_creds.json`。
- `qwen(provider_id=coding-plan-china|coding-plan-global)` 使用 API Key，会写入 `.qwen/settings.json`。
- `opencode/google` `oauth_proxy` (Antigravity browser OAuth) starts a per-session local callback listener on `127.0.0.1:51121` (`/oauth-callback`) and also supports `/input` fallback.
- OpenCode Google（Antigravity）OAuth 代理需要注入：
  - `SKILL_RUNNER_OPENCODE_GOOGLE_OAUTH_CLIENT_ID`
  - `SKILL_RUNNER_OPENCODE_GOOGLE_OAUTH_CLIENT_SECRET`
- Auth session logs are optional debug artifacts (disabled by default).
  Enable with `ENGINE_AUTH_SESSION_LOG_PERSISTENCE_ENABLED=true`:
  - `data/engine_auth_sessions/oauth_proxy/<session_id>/events.jsonl`, `http_trace.log`
  - `data/engine_auth_sessions/cli_delegate/<session_id>/events.jsonl`, `pty.log`, `stdin.log`

### Logging settings in containers

- UI-editable logging settings are managed through `/ui/settings` and stored in `/data/system_settings.json`
- Non-UI logging inputs still come from runtime env:
  - `LOG_DIR`
  - `LOG_FILE_BASENAME`
  - `LOG_ROTATION_WHEN`
  - `LOG_ROTATION_INTERVAL`
- If you want Settings changes to survive container recreation, persist `/data`

### Web inline terminal notes

- In container deployments, `/ui/engines` inline terminal runs commands in managed runtime env.
- In local Windows deployments, this feature relies on `pywinpty`; if missing, the UI returns a clear dependency error.

## Start the service

For local development, use the repository compose file (build-first):

```
docker compose up --build

The default image runtime user is non-root. If you override the container user
to root, Claude headless runs are not guaranteed to work because Claude Code
rejects bypass-permissions mode under root/sudo in non-sandboxed launches.
```

The API will be available at `http://localhost:9813/v1`.

To enable the built-in E2E example client, uncomment the `e2e_client` service block in
`docker-compose.yml` and restart compose. The E2E UI will be available at
`http://localhost:9814`.

### Bootstrap diagnostics (agent install / startup)

Container startup now writes structured bootstrap diagnostics to:

- `${SKILL_RUNNER_DATA_DIR}/logs/bootstrap.log`
- `${SKILL_RUNNER_DATA_DIR}/agent_bootstrap_report.json`

By default, container bootstrap only ensures `opencode,codex`. Override with
`SKILL_RUNNER_BOOTSTRAP_ENGINES=all`, `none`, or a comma-separated subset such as
`gemini,qwen`.

If startup prints `Failed to install <engine>: exit=1` or later warns
`opencode CLI not found`, inspect the two files above first. The report includes
per-engine `exit_code`, `duration_ms`, summarized stderr output, and the
requested/skipped engine sets for that bootstrap run.

## Release compose asset (tag-only)

For versioned deployments, download `docker-compose.release.yml` from the GitHub release assets.
This file is generated only for `v*` tags and uses pinned image tags (no local build).

```bash
docker compose -f docker-compose.release.yml up -d
```

`docker-compose.release.yml.sha256` is published alongside for integrity verification.

## Build and run locally

Build the image directly:

```
docker build -t skill-runner:local .
```

Run the container with the same mounts as compose (example):

```
docker run --rm -p 9813:9813 \
  -e UV_CACHE_DIR=/opt/cache/skill-runner/uv_cache \
  -e UV_PROJECT_ENVIRONMENT=/opt/cache/skill-runner/uv_venv \
  -e SKILL_RUNNER_AGENT_CACHE_DIR=/opt/cache/skill-runner \
  -e SKILL_RUNNER_AGENT_HOME=/opt/cache/skill-runner/agent-home \
  -e SKILL_RUNNER_NPM_PREFIX=/opt/cache/skill-runner/npm \
  -e NPM_CONFIG_PREFIX=/opt/cache/skill-runner/npm \
  -e SKILL_RUNNER_DATA_DIR=/data \
  -v "$(pwd)/skills:/app/skills" \
  -v skillrunner_cache:/opt/cache \
  skill-runner:local
```

Run the built-in E2E client from the same image:

```bash
docker run --rm -p 9814:9814 \
  --entrypoint /entrypoint_e2e.sh \
  -e SKILL_RUNNER_E2E_CLIENT_BACKEND_BASE_URL=http://host.docker.internal:9813 \
  skill-runner:local
```
