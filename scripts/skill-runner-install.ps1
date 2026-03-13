param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [string]$Repo = "leike0813/Skill-Runner",
    [string]$InstallRoot = "$env:LOCALAPPDATA\SkillRunner\releases"
)

$ErrorActionPreference = "Stop"

$artifact = "skill-runner-$Version.tar.gz"
$checksum = "$artifact.sha256"
$baseUrl = "https://github.com/$Repo/releases/download/$Version"
$artifactUrl = "$baseUrl/$artifact"
$checksumUrl = "$baseUrl/$checksum"

$tmpDir = Join-Path $env:TEMP ("skill-runner-install-" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $tmpDir -Force | Out-Null

try {
    $artifactPath = Join-Path $tmpDir $artifact
    $checksumPath = Join-Path $tmpDir $checksum

    Write-Host "Downloading $artifactUrl"
    Invoke-WebRequest -Uri $artifactUrl -OutFile $artifactPath
    Write-Host "Downloading $checksumUrl"
    Invoke-WebRequest -Uri $checksumUrl -OutFile $checksumPath

    $expected = (Get-Content $checksumPath -Raw).Split()[0].Trim().ToLowerInvariant()
    $actual = (Get-FileHash -Path $artifactPath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($expected -ne $actual) {
        throw "SHA256 mismatch."
    }

    $targetDir = Join-Path $InstallRoot $Version
    New-Item -ItemType Directory -Path $targetDir -Force | Out-Null
    tar -xzf $artifactPath -C $targetDir

    $bootstrapCtl = Join-Path $targetDir "scripts\skill-runnerctl.ps1"
    if (Test-Path $bootstrapCtl) {
        Write-Host "Running bootstrap (same strategy as agent_manager --ensure)..."
        & $bootstrapCtl bootstrap --json
        $bootstrapExit = $LASTEXITCODE
        if ($bootstrapExit -ne 0) {
            Write-Warning "Bootstrap returned exit code $bootstrapExit. Installation will continue; check bootstrap diagnostics logs."
        }
    }
    else {
        Write-Warning "Bootstrap script not found at $bootstrapCtl. Installation will continue without bootstrap."
    }

    Write-Host "Installed to: $targetDir"
    Write-Host "Next:"
    Write-Host "  $targetDir\scripts\skill-runnerctl.ps1 install --json"
    Write-Host "  $targetDir\scripts\skill-runnerctl.ps1 up --mode local --json"
}
finally {
    Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue
}
