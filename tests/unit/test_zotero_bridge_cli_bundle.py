import hashlib
import json
import os
import stat
from pathlib import Path

import pytest

from server.services.engine_management.runtime_profile import RuntimeProfile
from server.services.engine_management.zotero_bridge_cli_bundle import (
    GLOBAL_SKILL_DIRS,
    ZoteroBridgeBundleError,
    ensure_zotero_bridge_managed_plugin,
    resolve_bundle_platform_key,
    zotero_bridge_bin_path,
)


def _profile(root: Path, *, platform: str = "linux") -> RuntimeProfile:
    cache_root = root / "cache"
    return RuntimeProfile(
        mode="local",
        platform=platform,
        data_dir=root / "data",
        agent_cache_root=cache_root,
        agent_home=cache_root / "agent-home",
        npm_prefix=cache_root / "npm",
        uv_cache_dir=cache_root / "uv_cache",
        uv_project_environment=cache_root / "uv_venv",
    )


def _write_fake_bundle(root: Path, *, binary_name: str = "zotero-bridge") -> tuple[Path, str]:
    bundle = root / "bundle"
    binary = bundle / "bin" / "linux-x64" / binary_name
    binary.parent.mkdir(parents=True)
    binary.write_bytes(b"fake-zotero-bridge\n")
    digest = hashlib.sha256(binary.read_bytes()).hexdigest()
    skill_root = bundle / "skills" / "zotero-bridge-cli"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("# Zotero Bridge CLI\n", encoding="utf-8")
    profile_template = bundle / "assets" / "profile.template.json"
    profile_template.parent.mkdir(parents=True)
    profile_template.write_text(
        json.dumps(
            {
                "schema": "zotero-bridge.profile.v1",
                "protocol": "host-bridge.v1",
                "endpoint": "http://127.0.0.1:26570/bridge/v1",
                "connectionMode": "local",
                "auth": {"type": "bearer", "tokenEnv": "ZOTERO_BRIDGE_TOKEN"},
                "source": "published-bundle-template",
            }
        ),
        encoding="utf-8",
    )
    manifest = {
        "schema": "zotero-bridge-cli-bundle.v1",
        "cli": {
            "name": "zotero-bridge",
            "platforms": [
                {
                    "platform": "linux-x64",
                    "binary": f"bin/linux-x64/{binary_name}",
                    "sha256": digest,
                    "size": binary.stat().st_size,
                },
                {
                    "platform": "win32-x64",
                    "binary": f"bin/linux-x64/{binary_name}",
                    "sha256": digest,
                    "size": binary.stat().st_size,
                },
            ],
        },
        "wrapperSkill": {
            "id": "zotero-bridge-cli",
            "path": "skills/zotero-bridge-cli",
            "entrypoint": "skills/zotero-bridge-cli/SKILL.md",
        },
        "profileTemplate": {
            "path": "assets/profile.template.json",
            "endpointEnv": "ZOTERO_BRIDGE_ENDPOINT",
            "tokenEnv": "ZOTERO_BRIDGE_TOKEN",
            "connectionModeEnv": "ZOTERO_BRIDGE_CONNECTION_MODE",
        },
    }
    (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return bundle, digest


@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    [
        ("Linux", "x86_64", "linux-x64"),
        ("Linux", "aarch64", "linux-arm64"),
        ("Linux", "armv7l", "linux-arm"),
        ("Linux", "i686", "linux-x86"),
        ("Windows", "AMD64", "win32-x64"),
        ("Darwin", "arm64", None),
    ],
)
def test_resolve_bundle_platform_key(system: str, machine: str, expected: str | None) -> None:
    assert resolve_bundle_platform_key(system=system, machine=machine) == expected


def test_ensure_zotero_bridge_installs_posix_cli_profile_and_global_skills(tmp_path: Path) -> None:
    bundle, _digest = _write_fake_bundle(tmp_path)
    profile = _profile(tmp_path)

    result = ensure_zotero_bridge_managed_plugin(
        profile,
        engines=("codex", "claude", "qwen", "opencode"),
        bundle_root=bundle,
        system="Linux",
        machine="x86_64",
    )

    installed = zotero_bridge_bin_path(profile)
    assert result.cli_installed is True
    assert result.platform_key == "linux-x64"
    assert installed.exists()
    assert profile.build_subprocess_env({})["ZOTERO_BRIDGE_BIN"] == str(installed)
    assert stat.S_IMODE(installed.stat().st_mode) & stat.S_IXUSR
    profile_payload = json.loads(
        (profile.agent_cache_root / "zotero-bridge" / "bridge-profile.json").read_text(
            encoding="utf-8"
        )
    )
    assert "endpoint" not in profile_payload
    assert "connectionMode" not in profile_payload
    assert profile_payload["endpointEnv"] == "ZOTERO_BRIDGE_ENDPOINT"
    assert profile_payload["connectionModeEnv"] == "ZOTERO_BRIDGE_CONNECTION_MODE"
    assert profile_payload["auth"]["tokenEnv"] == "ZOTERO_BRIDGE_TOKEN"
    assert "127.0.0.1:26570" not in json.dumps(profile_payload)

    for relpath in GLOBAL_SKILL_DIRS.values():
        assert (profile.agent_home / relpath / "SKILL.md").read_text(
            encoding="utf-8"
        ) == "# Zotero Bridge CLI\n"


def test_ensure_zotero_bridge_installs_windows_exe_and_cmd_shim(tmp_path: Path) -> None:
    bundle, _digest = _write_fake_bundle(tmp_path)
    profile = _profile(tmp_path, platform="windows")

    ensure_zotero_bridge_managed_plugin(
        profile,
        engines=("codex",),
        bundle_root=bundle,
        system="Windows",
        machine="AMD64",
    )

    assert zotero_bridge_bin_path(profile).exists()
    assert profile.build_subprocess_env({})["ZOTERO_BRIDGE_BIN"] == str(
        zotero_bridge_bin_path(profile)
    )
    shim = profile.npm_prefix / "bin" / "zotero-bridge.cmd"
    assert shim.exists()
    assert "zotero-bridge.exe" in shim.read_text(encoding="utf-8")


def test_ensure_zotero_bridge_rejects_sha_mismatch(tmp_path: Path) -> None:
    bundle, _digest = _write_fake_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["cli"]["platforms"][0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ZoteroBridgeBundleError, match="sha256 mismatch"):
        ensure_zotero_bridge_managed_plugin(
            _profile(tmp_path),
            engines=("codex",),
            bundle_root=bundle,
            system="Linux",
            machine="x86_64",
        )

    assert not (tmp_path / "cache" / "npm" / "bin" / "zotero-bridge").exists()


def test_ensure_zotero_bridge_skips_missing_bundle(tmp_path: Path) -> None:
    result = ensure_zotero_bridge_managed_plugin(
        _profile(tmp_path),
        engines=("codex",),
        bundle_root=tmp_path / "missing",
        system="Linux",
        machine="x86_64",
    )

    assert result.cli_installed is False
    assert result.skipped_reason == "bundle_missing"


def test_zotero_bridge_submodule_and_docker_wiring_are_declared() -> None:
    gitmodules = Path(".gitmodules").read_text(encoding="utf-8")
    assert '[submodule "plugins/zotero-bridge-cli-bundle"]' in gitmodules
    assert "path = plugins/zotero-bridge-cli-bundle" in gitmodules
    assert "url = https://github.com/leike0813/Zotero-Skills.git" in gitmodules
    assert "branch = host-bridge/zotero-bridge-cli-bundle" in gitmodules

    bundle = Path("plugins/zotero-bridge-cli-bundle")
    assert (bundle / "manifest.json").exists()
    assert (bundle / "bin").is_dir()
    assert (bundle / "skills" / "zotero-bridge-cli" / "SKILL.md").exists()
    assert (bundle / "assets" / "profile.template.json").exists()

    dockerfile = Path("Dockerfile").read_text(encoding="utf-8")
    assert "COPY plugins ./plugins" in dockerfile
    assert "ZOTERO_BRIDGE_BIN=/opt/cache/skill-runner/npm/bin/zotero-bridge" in dockerfile

    for compose_path in ("docker-compose.yml", "docker-compose.release.tmpl.yml"):
        compose = Path(compose_path).read_text(encoding="utf-8")
        assert "ZOTERO_BRIDGE_BIN: /opt/cache/skill-runner/npm/bin/zotero-bridge" in compose

    for script_path in ("scripts/skill-runnerctl", "scripts/deploy_local.sh"):
        script = Path(script_path).read_text(encoding="utf-8")
        assert (
            'ZOTERO_BRIDGE_BIN="${ZOTERO_BRIDGE_BIN:-$SKILL_RUNNER_NPM_PREFIX/bin/zotero-bridge}"'
            in script
        )

    for script_path in ("scripts/skill-runnerctl.ps1", "scripts/deploy_local.ps1"):
        script = Path(script_path).read_text(encoding="utf-8")
        assert "ZOTERO_BRIDGE_BIN" in script
        assert "zotero-bridge.exe" in script
