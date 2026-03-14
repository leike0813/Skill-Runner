param(
    [switch]$ClearData,
    [switch]$ClearAgentHome,
    [switch]$Json,
    [string]$LocalRoot
)

$ErrorActionPreference = "Stop"

function Resolve-DefaultLocalRoot {
    if ($env:SKILL_RUNNER_LOCAL_ROOT) {
        return [System.IO.Path]::GetFullPath($env:SKILL_RUNNER_LOCAL_ROOT)
    }
    return [System.IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA "SkillRunner"))
}

function Resolve-ManagedPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    try {
        return [System.IO.Path]::GetFullPath($Path)
    }
    catch {
        return $Path
    }
}

function Test-ManagedPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path,
        [Parameter(Mandatory = $true)]
        [string]$Root
    )

    if ([string]::IsNullOrWhiteSpace($Path) -or [string]::IsNullOrWhiteSpace($Root)) {
        return $false
    }
    $resolvedPath = Resolve-ManagedPath $Path
    $resolvedRoot = Resolve-ManagedPath $Root
    $rootMarker = [System.IO.Path]::GetPathRoot($resolvedPath)
    if ([string]::IsNullOrWhiteSpace($rootMarker)) {
        return $false
    }
    if ($resolvedPath -ieq $rootMarker) {
        return $false
    }
    if ($resolvedPath -ieq $resolvedRoot) {
        return $true
    }
    $normalizedRoot = $resolvedRoot.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
    return $resolvedPath.StartsWith($normalizedRoot, [System.StringComparison]::OrdinalIgnoreCase)
}

$resolvedLocalRoot = if ($LocalRoot) { Resolve-ManagedPath $LocalRoot } else { Resolve-DefaultLocalRoot }
$removedPaths = [System.Collections.Generic.List[string]]::new()
$failedPaths = [System.Collections.Generic.List[string]]::new()
$preservedPaths = [System.Collections.Generic.List[string]]::new()

function Remove-ManagedPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $resolvedPath = Resolve-ManagedPath $Path
    if (-not (Test-ManagedPath -Path $resolvedPath -Root $resolvedLocalRoot)) {
        $failedPaths.Add($resolvedPath)
        return
    }
    if (-not (Test-Path -LiteralPath $resolvedPath)) {
        $preservedPaths.Add($resolvedPath)
        return
    }
    try {
        Remove-Item -LiteralPath $resolvedPath -Recurse -Force -ErrorAction Stop
        $removedPaths.Add($resolvedPath)
    }
    catch {
        $failedPaths.Add($resolvedPath)
    }
}

$rootMarker = [System.IO.Path]::GetPathRoot($resolvedLocalRoot)
if ([string]::IsNullOrWhiteSpace($resolvedLocalRoot) -or $resolvedLocalRoot -eq $rootMarker) {
    $failedPaths.Add($resolvedLocalRoot)
}

$downResult = [ordered]@{
    invoked   = $true
    ok        = $false
    exit_code = 127
    stdout    = ""
    stderr    = ""
}

$tmpDir = Join-Path $env:TEMP ("skill-runner-uninstall-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null
$downStdoutPath = Join-Path $tmpDir "down.stdout.log"
$downStderrPath = Join-Path $tmpDir "down.stderr.log"

try {
    $ctlPath = if ($env:SKILL_RUNNER_CTL_PATH) { $env:SKILL_RUNNER_CTL_PATH } else { Join-Path $PSScriptRoot "skill-runnerctl.ps1" }
    if (Test-Path -LiteralPath $ctlPath -PathType Leaf) {
        & $ctlPath down --mode local --json 1>"$downStdoutPath" 2>"$downStderrPath"
        $downResult.exit_code = $LASTEXITCODE
        $downResult.ok = ($downResult.exit_code -eq 0)
    }
    else {
        $downResult.stderr = "skill-runnerctl not found or not executable: $ctlPath"
    }

    if (Test-Path -LiteralPath $downStdoutPath) {
        $downResult.stdout = Get-Content -LiteralPath $downStdoutPath -Raw -ErrorAction SilentlyContinue
    }
    if (Test-Path -LiteralPath $downStderrPath) {
        $stderrRaw = Get-Content -LiteralPath $downStderrPath -Raw -ErrorAction SilentlyContinue
        if (-not [string]::IsNullOrWhiteSpace($stderrRaw)) {
            $downResult.stderr = $stderrRaw
        }
    }
}
finally {
    Remove-Item -LiteralPath $tmpDir -Recurse -Force -ErrorAction SilentlyContinue
}

$releasesDir = Resolve-ManagedPath (Join-Path $resolvedLocalRoot "releases")
$agentCacheDir = Resolve-ManagedPath (Join-Path $resolvedLocalRoot "agent-cache")
$dataDir = Resolve-ManagedPath (Join-Path $resolvedLocalRoot "data")
$agentHomeDir = Resolve-ManagedPath (Join-Path $agentCacheDir "agent-home")
$npmDir = Resolve-ManagedPath (Join-Path $agentCacheDir "npm")
$uvCacheDir = Resolve-ManagedPath (Join-Path $agentCacheDir "uv_cache")
$uvVenvDir = Resolve-ManagedPath (Join-Path $agentCacheDir "uv_venv")

if (-not [string]::IsNullOrWhiteSpace($resolvedLocalRoot) -and $resolvedLocalRoot -ne $rootMarker) {
    Remove-ManagedPath $releasesDir
    Remove-ManagedPath $npmDir
    Remove-ManagedPath $uvCacheDir
    Remove-ManagedPath $uvVenvDir

    if ($ClearData) {
        Remove-ManagedPath $dataDir
    }
    else {
        $preservedPaths.Add($dataDir)
    }

    if ($ClearAgentHome) {
        Remove-ManagedPath $agentHomeDir
    }
    else {
        $preservedPaths.Add($agentHomeDir)
    }

    if ($ClearData -and $ClearAgentHome) {
        Remove-ManagedPath $resolvedLocalRoot
    }
}

$exitCode = if ($failedPaths.Count -gt 0) { 1 } else { 0 }
$message = if ($exitCode -eq 0) { "Uninstall completed." } else { "Uninstall completed with errors." }
$payload = [ordered]@{
    ok             = ($exitCode -eq 0)
    exit_code      = $exitCode
    message        = $message
    local_root     = $resolvedLocalRoot
    removed_paths  = @($removedPaths)
    failed_paths   = @($failedPaths)
    preserved_paths = @($preservedPaths)
    options        = [ordered]@{
        clear_data       = [bool]$ClearData
        clear_agent_home = [bool]$ClearAgentHome
    }
    down_result    = $downResult
}

if ($Json) {
    Write-Output ($payload | ConvertTo-Json -Compress -Depth 6)
}
else {
    Write-Output $message
    Write-Output "Local root: $resolvedLocalRoot"
    Write-Output "Down result: ok=$($downResult.ok) exit_code=$($downResult.exit_code)"
    Write-Output "Removed paths:"
    foreach ($path in $removedPaths) {
        Write-Output "  $path"
    }
    Write-Output "Failed paths:"
    foreach ($path in $failedPaths) {
        Write-Output "  $path"
    }
    Write-Output "Preserved paths:"
    foreach ($path in $preservedPaths) {
        Write-Output "  $path"
    }
}

exit $exitCode
