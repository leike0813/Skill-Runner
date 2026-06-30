import hashlib
import json
import os
import shutil
import stat
from pathlib import Path

import pytest

from server.config import config
from server.services.engine_management.runtime_profile import RuntimeProfile
from server.services.engine_management.zotero_bridge_cli_bundle import (
    GLOBAL_SKILL_DIRS,
    ZoteroBridgeBundleError,
    ensure_zotero_bridge_managed_plugin,
    find_default_bundle_root,
    resolve_bundle_platform_key,
    validate_zotero_bridge_bundle_root,
    write_managed_bundle_current,
    write_zotero_bridge_bundle_state,
    zotero_bridge_bundle_status,
    zotero_bridge_bin_path,
)
from server.services.engine_management.zotero_bridge_bundle_auto_update import (
    ZoteroBridgeBundleAutoUpdateConfig,
    ZoteroBridgeBundleAutoUpdateManager,
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
    engines = ("codex", "claude", "qwen", "opencode")

    result = ensure_zotero_bridge_managed_plugin(
        profile,
        engines=engines,
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

    assert result.skill_destinations == tuple(profile.agent_home / GLOBAL_SKILL_DIRS[engine] for engine in engines)
    for engine in engines:
        relpath = GLOBAL_SKILL_DIRS[engine]
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


def test_default_bundle_root_prefers_valid_managed_bundle(tmp_path: Path) -> None:
    bundle, _digest = _write_fake_bundle(tmp_path)
    profile = _profile(tmp_path)
    write_zotero_bridge_bundle_state(
        profile,
        {
            "status": "installed",
            "active_commit": "abc123",
            "active_bundle_root": str(bundle),
        },
    )
    write_managed_bundle_current(
        profile,
        active_commit="abc123",
        active_bundle_root=bundle,
    )

    assert find_default_bundle_root(profile) == bundle
    status = zotero_bridge_bundle_status(profile)
    assert status["source"] == "managed"
    assert status["bundle_root"] == str(bundle)


def test_default_bundle_root_falls_back_when_managed_bundle_is_invalid(tmp_path: Path) -> None:
    profile = _profile(tmp_path)
    missing = tmp_path / "missing-bundle"
    write_zotero_bridge_bundle_state(
        profile,
        {
            "status": "installed",
            "active_commit": "abc123",
            "active_bundle_root": str(missing),
        },
    )

    assert find_default_bundle_root(profile) != missing
    assert zotero_bridge_bundle_status(profile)["source"] == "builtin"


def test_validate_zotero_bridge_rejects_unsafe_manifest_path(tmp_path: Path) -> None:
    bundle, _digest = _write_fake_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["wrapperSkill"]["path"] = "../outside"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ZoteroBridgeBundleError, match="unsafe"):
        validate_zotero_bridge_bundle_root(bundle)


def test_auto_update_noops_when_remote_commit_is_current(tmp_path: Path, monkeypatch) -> None:
    profile = _profile(tmp_path)
    manager = ZoteroBridgeBundleAutoUpdateManager(profile)
    write_zotero_bridge_bundle_state(
        profile,
        {
            "status": "installed",
            "active_commit": "abc123",
            "active_bundle_root": str(tmp_path / "bundle"),
        },
    )
    monkeypatch.setattr(manager, "_remote_head", lambda _cfg: "abc123")

    state = manager._check_once_sync(_auto_update_cfg())

    assert state["status"] == "up_to_date"
    assert state["active_commit"] == "abc123"


def test_auto_update_installs_new_valid_bundle(tmp_path: Path, monkeypatch) -> None:
    bundle, _digest = _write_fake_bundle(tmp_path)
    version_dir = tmp_path / "cache" / "plugin-bundles" / "zotero-bridge-cli-bundle" / "versions" / "def456"
    version_dir.parent.mkdir(parents=True)
    shutil.copytree(bundle, version_dir)
    profile = _profile(tmp_path)
    manager = ZoteroBridgeBundleAutoUpdateManager(profile)
    monkeypatch.setattr(manager, "_remote_head", lambda _cfg: "def456")
    monkeypatch.setattr(manager, "_ensure_version_dir", lambda _cfg, _commit: version_dir)

    state = manager._check_once_sync(_auto_update_cfg())

    assert state["status"] == "installed"
    assert state["active_commit"] == "def456"
    assert find_default_bundle_root(profile) == version_dir
    assert (profile.npm_prefix / "bin" / "zotero-bridge").exists()


def test_auto_update_failure_keeps_previous_state(tmp_path: Path, monkeypatch) -> None:
    profile = _profile(tmp_path)
    manager = ZoteroBridgeBundleAutoUpdateManager(profile)
    previous = {
        "status": "installed",
        "active_commit": "abc123",
        "active_bundle_root": str(tmp_path / "previous"),
    }
    write_zotero_bridge_bundle_state(profile, previous)
    monkeypatch.setattr(manager, "_remote_head", lambda _cfg: "def456")
    monkeypatch.setattr(
        manager,
        "_ensure_version_dir",
        lambda _cfg, _commit: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    state = manager._check_once_sync(_auto_update_cfg())

    assert state["status"] == "failed"
    assert state["active_commit"] == "abc123"
    assert state["error_message"] == "boom"


def test_auto_update_start_respects_disabled_config(tmp_path: Path) -> None:
    old_enabled = config.SYSTEM.ZOTERO_BRIDGE_BUNDLE_AUTO_UPDATE.ENABLED
    config.defrost()
    config.SYSTEM.ZOTERO_BRIDGE_BUNDLE_AUTO_UPDATE.ENABLED = False
    config.freeze()
    try:
        manager = ZoteroBridgeBundleAutoUpdateManager(_profile(tmp_path))
        manager.start()
        assert manager._task is None
    finally:
        config.defrost()
        config.SYSTEM.ZOTERO_BRIDGE_BUNDLE_AUTO_UPDATE.ENABLED = old_enabled
        config.freeze()


def _auto_update_cfg() -> ZoteroBridgeBundleAutoUpdateConfig:
    return ZoteroBridgeBundleAutoUpdateConfig(
        enabled=True,
        repository=str(config.SYSTEM.ZOTERO_BRIDGE_BUNDLE_AUTO_UPDATE.SOURCE_REPOSITORY),
        branch=str(config.SYSTEM.ZOTERO_BRIDGE_BUNDLE_AUTO_UPDATE.SOURCE_BRANCH),
        interval_sec=86400,
        startup_delay_sec=0,
        timeout_sec=5,
    )


def test_zotero_bridge_submodule_and_docker_wiring_are_declared() -> None:
    gitmodules = Path(".gitmodules").read_text(encoding="utf-8")
    assert '[submodule "plugins/zotero-bridge-cli-bundle"]' in gitmodules
    assert "path = plugins/zotero-bridge-cli-bundle" in gitmodules
    assert "url = https://github.com/leike0813/zotero-agents.git" in gitmodules
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
