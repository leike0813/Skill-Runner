param(
    [Parameter(Mandatory = $true)]
    [string]$Version,
    [string]$Repo = "leike0813/Skill-Runner",
    [string]$InstallRoot = "$env:LOCALAPPDATA\SkillRunner\releases",
    [switch]$Json
)

$ErrorActionPreference = "Stop"

function Write-InstallerInfo {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Message
    )

    if ($Json) {
        [Console]::Error.WriteLine($Message)
    }
    else {
        Write-Output $Message
    }
}

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

    Write-InstallerInfo "Downloading $artifactUrl"
    Invoke-WebRequest -Uri $artifactUrl -OutFile $artifactPath
    Write-InstallerInfo "Downloading $checksumUrl"
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
    $bootstrapExit = $null
    if (Test-Path $bootstrapCtl) {
        Write-InstallerInfo "Running bootstrap (same strategy as agent_manager --ensure)..."
        if ($Json) {
            & $bootstrapCtl bootstrap --json | Out-Null
        }
        else {
            & $bootstrapCtl bootstrap --json
        }
        $bootstrapExit = $LASTEXITCODE
        if ($bootstrapExit -ne 0) {
            Write-Warning "Bootstrap returned exit code $bootstrapExit. Installation will continue; check bootstrap diagnostics logs."
        }
    }
    else {
        Write-Warning "Bootstrap script not found at $bootstrapCtl. Installation will continue without bootstrap."
    }

    if ($Json) {
        $payload = [ordered]@{
            "ok"                  = $true
            "install_dir"         = $targetDir
            "version"             = $Version
            "bootstrap_exit_code" = $bootstrapExit
        }
        Write-Output ($payload | ConvertTo-Json -Compress)
    }
    else {
        Write-Output "Installed to: $targetDir"
        Write-Output "Next:"
        Write-Output "  $targetDir\scripts\skill-runnerctl.ps1 install --json"
        Write-Output "  $targetDir\scripts\skill-runnerctl.ps1 up --mode local --json"
    }
}
finally {
    Remove-Item -Recurse -Force $tmpDir -ErrorAction SilentlyContinue
}
