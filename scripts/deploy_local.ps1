param(
    [int]$Port = 9813
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir

function Resolve-NpmCommand {
    $candidates = @("npm.cmd", "npm.exe", "npm.bat", "npm")
    foreach ($name in $candidates) {
        $app = Get-Command $name -ErrorAction SilentlyContinue -CommandType Application
        if ($app -and $app.Source) {
            return $app.Source
        }
    }
    $fallback = Get-Command npm -ErrorAction SilentlyContinue
    if ($fallback -and $fallback.Source) {
        $source = [string]$fallback.Source
        if ([System.IO.Path]::GetExtension($source).ToLowerInvariant() -eq ".ps1") {
            $cmdSibling = [System.IO.Path]::ChangeExtension($source, ".cmd")
            if (Test-Path $cmdSibling) {
                return $cmdSibling
            }
        }
        return $source
    }
    return $null
}

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv not found. Please install uv first: https://docs.astral.sh/uv/"
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Error "node not found. Please install Node.js 24+."
}
if (-not (Resolve-NpmCommand)) {
    Write-Error "npm not found. Please install npm."
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
$env:SKILL_RUNNER_LOCAL_BIND_HOST = if ($env:SKILL_RUNNER_LOCAL_BIND_HOST) { $env:SKILL_RUNNER_LOCAL_BIND_HOST } else { "0.0.0.0" }

New-Item -ItemType Directory -Force -Path $env:SKILL_RUNNER_DATA_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $env:SKILL_RUNNER_AGENT_CACHE_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $env:SKILL_RUNNER_AGENT_HOME | Out-Null

$resolvedNpmCommand = Resolve-NpmCommand
if ($resolvedNpmCommand) {
    $env:SKILL_RUNNER_NPM_COMMAND = $resolvedNpmCommand
    $npmCommandDir = Split-Path -Parent $resolvedNpmCommand
    if ($npmCommandDir) {
        $env:PATH = "$npmCommandDir;$($env:PATH)"
    }
}

$env:PATH = "$($env:SKILL_RUNNER_NPM_PREFIX);$($env:SKILL_RUNNER_NPM_PREFIX)\bin;$($env:PATH)"

Write-Host "=== Skill Runner Local Deploy (Windows) ==="
Write-Host "Project Root: $ProjectRoot"
Write-Host "Data Dir: $($env:SKILL_RUNNER_DATA_DIR)"
Write-Host "Agent Cache Dir: $($env:SKILL_RUNNER_AGENT_CACHE_DIR)"
Write-Host "Agent Home: $($env:SKILL_RUNNER_AGENT_HOME)"
Write-Host "NPM Prefix: $($env:SKILL_RUNNER_NPM_PREFIX)"
Write-Host "Bind Host: $($env:SKILL_RUNNER_LOCAL_BIND_HOST)"

Set-Location $ProjectRoot
uv run python scripts/skill_runnerctl.py bootstrap --json
uv run uvicorn server.main:app --host $env:SKILL_RUNNER_LOCAL_BIND_HOST --port $Port
