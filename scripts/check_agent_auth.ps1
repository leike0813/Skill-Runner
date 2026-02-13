param(
    [ValidateSet("local", "container")]
    [string]$Mode = "local"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

if ($Mode -eq "container") {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Write-Error "docker not found"
    }
    docker compose run --rm api sh -lc "python3 /app/scripts/agent_manager.py --check-auth"
    exit 0
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv not found. Please install uv first: https://docs.astral.sh/uv/"
}

$LocalRoot = if ($env:SKILL_RUNNER_LOCAL_ROOT) { $env:SKILL_RUNNER_LOCAL_ROOT } else { Join-Path $env:LOCALAPPDATA "SkillRunner" }
$env:SKILL_RUNNER_RUNTIME_MODE = if ($env:SKILL_RUNNER_RUNTIME_MODE) { $env:SKILL_RUNNER_RUNTIME_MODE } else { "local" }
$env:SKILL_RUNNER_DATA_DIR = if ($env:SKILL_RUNNER_DATA_DIR) { $env:SKILL_RUNNER_DATA_DIR } else { Join-Path $ProjectRoot "data" }
$env:SKILL_RUNNER_AGENT_CACHE_DIR = if ($env:SKILL_RUNNER_AGENT_CACHE_DIR) { $env:SKILL_RUNNER_AGENT_CACHE_DIR } else { Join-Path $LocalRoot "agent-cache" }
$env:SKILL_RUNNER_AGENT_HOME = if ($env:SKILL_RUNNER_AGENT_HOME) { $env:SKILL_RUNNER_AGENT_HOME } else { Join-Path $env:SKILL_RUNNER_AGENT_CACHE_DIR "agent-home" }
$env:SKILL_RUNNER_NPM_PREFIX = if ($env:SKILL_RUNNER_NPM_PREFIX) { $env:SKILL_RUNNER_NPM_PREFIX } else { Join-Path $env:SKILL_RUNNER_AGENT_CACHE_DIR "npm" }
$env:NPM_CONFIG_PREFIX = if ($env:NPM_CONFIG_PREFIX) { $env:NPM_CONFIG_PREFIX } else { $env:SKILL_RUNNER_NPM_PREFIX }
$env:UV_CACHE_DIR = if ($env:UV_CACHE_DIR) { $env:UV_CACHE_DIR } else { Join-Path $env:SKILL_RUNNER_AGENT_CACHE_DIR "uv_cache" }
$env:UV_PROJECT_ENVIRONMENT = if ($env:UV_PROJECT_ENVIRONMENT) { $env:UV_PROJECT_ENVIRONMENT } else { Join-Path $env:SKILL_RUNNER_AGENT_CACHE_DIR "uv_venv" }

New-Item -ItemType Directory -Force -Path $env:SKILL_RUNNER_DATA_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $env:SKILL_RUNNER_AGENT_CACHE_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $env:SKILL_RUNNER_AGENT_HOME | Out-Null

Set-Location $ProjectRoot
uv run python scripts/agent_manager.py --check-auth

