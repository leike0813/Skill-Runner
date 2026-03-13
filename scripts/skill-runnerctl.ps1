param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
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

$LocalRoot = if ($env:SKILL_RUNNER_LOCAL_ROOT) { $env:SKILL_RUNNER_LOCAL_ROOT } else { Join-Path $env:LOCALAPPDATA "SkillRunner" }
$env:SKILL_RUNNER_RUNTIME_MODE = if ($env:SKILL_RUNNER_RUNTIME_MODE) { $env:SKILL_RUNNER_RUNTIME_MODE } else { "local" }
$env:SKILL_RUNNER_LOCAL_PORT = if ($env:SKILL_RUNNER_LOCAL_PORT) { $env:SKILL_RUNNER_LOCAL_PORT } else { "29813" }
$env:SKILL_RUNNER_LOCAL_PORT_FALLBACK_SPAN = if ($env:SKILL_RUNNER_LOCAL_PORT_FALLBACK_SPAN) { $env:SKILL_RUNNER_LOCAL_PORT_FALLBACK_SPAN } else { "10" }
$env:SKILL_RUNNER_DATA_DIR = if ($env:SKILL_RUNNER_DATA_DIR) { $env:SKILL_RUNNER_DATA_DIR } else { Join-Path $LocalRoot "data" }
$env:SKILL_RUNNER_AGENT_CACHE_DIR = if ($env:SKILL_RUNNER_AGENT_CACHE_DIR) { $env:SKILL_RUNNER_AGENT_CACHE_DIR } else { Join-Path $LocalRoot "agent-cache" }
$env:SKILL_RUNNER_AGENT_HOME = if ($env:SKILL_RUNNER_AGENT_HOME) { $env:SKILL_RUNNER_AGENT_HOME } else { Join-Path $env:SKILL_RUNNER_AGENT_CACHE_DIR "agent-home" }
$env:SKILL_RUNNER_NPM_PREFIX = if ($env:SKILL_RUNNER_NPM_PREFIX) { $env:SKILL_RUNNER_NPM_PREFIX } else { Join-Path $env:SKILL_RUNNER_AGENT_CACHE_DIR "npm" }
$env:NPM_CONFIG_PREFIX = if ($env:NPM_CONFIG_PREFIX) { $env:NPM_CONFIG_PREFIX } else { $env:SKILL_RUNNER_NPM_PREFIX }
$env:UV_CACHE_DIR = if ($env:UV_CACHE_DIR) { $env:UV_CACHE_DIR } else { Join-Path $env:SKILL_RUNNER_AGENT_CACHE_DIR "uv_cache" }
$env:UV_PROJECT_ENVIRONMENT = if ($env:UV_PROJECT_ENVIRONMENT) { $env:UV_PROJECT_ENVIRONMENT } else { Join-Path $env:SKILL_RUNNER_AGENT_CACHE_DIR "uv_venv" }

New-Item -ItemType Directory -Force -Path $env:SKILL_RUNNER_DATA_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $env:SKILL_RUNNER_AGENT_CACHE_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $env:SKILL_RUNNER_AGENT_HOME | Out-Null
New-Item -ItemType Directory -Force -Path $env:SKILL_RUNNER_NPM_PREFIX | Out-Null
New-Item -ItemType Directory -Force -Path $env:UV_CACHE_DIR | Out-Null
New-Item -ItemType Directory -Force -Path $env:UV_PROJECT_ENVIRONMENT | Out-Null

$resolvedNpmCommand = Resolve-NpmCommand
if ($resolvedNpmCommand) {
    $env:SKILL_RUNNER_NPM_COMMAND = $resolvedNpmCommand
    $npmCommandDir = Split-Path -Parent $resolvedNpmCommand
    if ($npmCommandDir) {
        $env:PATH = "$npmCommandDir;$($env:PATH)"
    }
}

$env:PATH = "$($env:SKILL_RUNNER_NPM_PREFIX);$($env:SKILL_RUNNER_NPM_PREFIX)\bin;$($env:PATH)"

Set-Location $ProjectRoot
& uv run python scripts/skill_runnerctl.py @Args
exit $LASTEXITCODE
