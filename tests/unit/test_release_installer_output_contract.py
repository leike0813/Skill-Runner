from __future__ import annotations

from pathlib import Path


def _read_script(rel_path: str) -> str:
    repo_root = Path(__file__).resolve().parents[2]
    return (repo_root / rel_path).read_text(encoding="utf-8")


def test_shell_installer_exposes_json_and_legacy_install_dir_output() -> None:
    source = _read_script("scripts/skill-runner-install.sh")

    assert "--json)" in source
    assert '"ok":true' in source
    assert '"install_dir":"%s"' in source
    assert '"version":"%s"' in source
    assert '"bootstrap_exit_code":%s' in source
    assert "Installed to: ${TARGET_DIR}" in source


def test_powershell_installer_exposes_json_and_legacy_install_dir_output() -> None:
    source = _read_script("scripts/skill-runner-install.ps1")

    assert "[switch]$Json" in source
    assert "ConvertTo-Json -Compress" in source
    assert '"install_dir"' in source
    assert '"version"' in source
    assert '"bootstrap_exit_code"' in source
    assert 'Write-Output "Installed to: $targetDir"' in source
