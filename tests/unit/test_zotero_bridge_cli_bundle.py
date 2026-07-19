import hashlib
import json
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
    load_zotero_bridge_bundle_descriptor,
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
    ZoteroBridgeBundleUpdateConflict,
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


def _write_fake_bundle(
    root: Path,
    *,
    manifest_schema: str = "legacy",
    version: str | None = "0.3.0",
    platform_keys: tuple[str, ...] = ("linux-x64", "win32-x64"),
) -> tuple[Path, str]:
    bundle = root / "bundle"
    skill_root = bundle / "skills" / "zotero-bridge-cli"
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("# Zotero Bridge CLI\n", encoding="utf-8")
    profile_template = (
        skill_root / "assets" / "profile.template.json"
        if manifest_schema == "surface"
        else bundle / "assets" / "profile.template.json"
    )
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
    entries = []
    digests: dict[str, str] = {}
    for platform_key in platform_keys:
        binary_name = "zotero-bridge.exe" if platform_key.startswith("win32-") else "zotero-bridge"
        binary = bundle / "bin" / platform_key / binary_name
        binary.parent.mkdir(parents=True)
        binary.write_bytes(f"fake-zotero-bridge:{platform_key}\n".encode())
        digest = hashlib.sha256(binary.read_bytes()).hexdigest()
        digests[platform_key] = digest
        entries.append(
            {
                "platform": platform_key,
                "binary": (
                    binary_name
                    if manifest_schema == "surface"
                    else f"bin/{platform_key}/{binary_name}"
                ),
                "sha256": digest,
                "bytes": binary.stat().st_size,
            }
        )
    if manifest_schema == "surface":
        manifest = {
            "schema": "host-bridge.surface-release.v1",
            "surface": {"version": version},
            "releaseSet": {"cli": {"binaries": entries}},
        }
    else:
        manifest = {
            "schema": "zotero-bridge-cli-bundle.v1",
            "cli": {"name": "zotero-bridge", "platforms": entries},
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
    if version is not None:
        manifest["surface"] = {"version": version}
    elif manifest_schema == "surface":
        manifest["surface"] = {}
    (bundle / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return bundle, digests.get("linux-x64", next(iter(digests.values())))


@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    [
        ("Linux", "x86_64", "linux-x64"),
        ("Linux", "aarch64", "linux-arm64"),
        ("Linux", "armv7l", "linux-arm"),
        ("Linux", "i686", "linux-x86"),
        ("Windows", "AMD64", "win32-x64"),
        ("Darwin", "x86_64", "darwin-x64"),
        ("Darwin", "arm64", "darwin-arm64"),
    ],
)
def test_resolve_bundle_platform_key(system: str, machine: str, expected: str | None) -> None:
    assert resolve_bundle_platform_key(system=system, machine=machine) == expected


@pytest.mark.parametrize(
    ("manifest_schema", "expected_profile"),
    [
        ("legacy", Path("assets/profile.template.json")),
        (
            "surface",
            Path("skills/zotero-bridge-cli/assets/profile.template.json"),
        ),
    ],
)
def test_bundle_descriptor_normalizes_supported_manifest_schemas(
    tmp_path: Path,
    manifest_schema: str,
    expected_profile: Path,
) -> None:
    bundle, digest = _write_fake_bundle(tmp_path, manifest_schema=manifest_schema)

    descriptor = load_zotero_bridge_bundle_descriptor(bundle)
    binary = descriptor.binary_for("linux-x64")

    assert descriptor.version == "0.3.0"
    assert descriptor.wrapper_skill_relative_path == Path("skills/zotero-bridge-cli")
    assert descriptor.profile_template_relative_path == expected_profile
    assert binary is not None
    assert binary.relative_path == Path("bin/linux-x64/zotero-bridge")
    assert binary.sha256 == digest


@pytest.mark.parametrize("manifest_schema", ["legacy", "surface"])
def test_ensure_zotero_bridge_installs_posix_cli_profile_and_global_skills(
    tmp_path: Path,
    manifest_schema: str,
) -> None:
    bundle, _digest = _write_fake_bundle(tmp_path, manifest_schema=manifest_schema)
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


@pytest.mark.parametrize("manifest_schema", ["legacy", "surface"])
def test_ensure_zotero_bridge_installs_windows_exe_and_cmd_shim(
    tmp_path: Path,
    manifest_schema: str,
) -> None:
    bundle, _digest = _write_fake_bundle(tmp_path, manifest_schema=manifest_schema)
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


@pytest.mark.parametrize("manifest_schema", ["legacy", "surface"])
def test_ensure_zotero_bridge_rejects_sha_mismatch(
    tmp_path: Path,
    manifest_schema: str,
) -> None:
    bundle, _digest = _write_fake_bundle(tmp_path, manifest_schema=manifest_schema)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = (
        manifest["releaseSet"]["cli"]["binaries"]
        if manifest_schema == "surface"
        else manifest["cli"]["platforms"]
    )
    entries[0]["sha256"] = "0" * 64
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
    assert not (tmp_path / "cache" / "zotero-bridge" / "bridge-profile.json").exists()
    assert not (tmp_path / "cache" / "agent-home" / ".codex" / "skills").exists()


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
    assert status["version"] == "0.3.0"
    assert status["current_commit"] == "abc123"
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


def test_bundle_status_allows_legacy_manifest_without_version(tmp_path: Path) -> None:
    bundle, _digest = _write_fake_bundle(tmp_path, version=None)
    profile = _profile(tmp_path)
    write_zotero_bridge_bundle_state(
        profile,
        {
            "status": "installed",
            "active_commit": "abc123",
            "active_bundle_root": str(bundle),
        },
    )

    status = zotero_bridge_bundle_status(profile)

    assert status["source"] == "managed"
    assert status["version"] is None


def test_validate_zotero_bridge_rejects_unsafe_manifest_path(tmp_path: Path) -> None:
    bundle, _digest = _write_fake_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["wrapperSkill"]["path"] = "../outside"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ZoteroBridgeBundleError, match="unsafe"):
        validate_zotero_bridge_bundle_root(bundle)


def test_validate_surface_release_rejects_unsafe_binary_path(tmp_path: Path) -> None:
    bundle, _digest = _write_fake_bundle(tmp_path, manifest_schema="surface")
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["releaseSet"]["cli"]["binaries"][0]["platform"] = "../outside"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ZoteroBridgeBundleError, match="unsafe"):
        validate_zotero_bridge_bundle_root(bundle)


def test_validate_rejects_unknown_manifest_schema(tmp_path: Path) -> None:
    bundle, _digest = _write_fake_bundle(tmp_path)
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema"] = "zotero-bridge.unknown.v1"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    with pytest.raises(ZoteroBridgeBundleError, match="Unsupported"):
        validate_zotero_bridge_bundle_root(bundle)


@pytest.mark.parametrize("missing_artifact", ["wrapper", "profile", "binary"])
def test_validate_surface_release_rejects_missing_artifacts(
    tmp_path: Path,
    missing_artifact: str,
) -> None:
    bundle, _digest = _write_fake_bundle(tmp_path, manifest_schema="surface")
    paths = {
        "wrapper": bundle / "skills" / "zotero-bridge-cli" / "SKILL.md",
        "profile": (
            bundle
            / "skills"
            / "zotero-bridge-cli"
            / "assets"
            / "profile.template.json"
        ),
        "binary": bundle / "bin" / "linux-x64" / "zotero-bridge",
    }
    paths[missing_artifact].unlink()

    with pytest.raises(ZoteroBridgeBundleError, match="missing"):
        validate_zotero_bridge_bundle_root(
            bundle,
            system="Linux",
            machine="x86_64",
        )


@pytest.mark.parametrize(
    ("machine", "platform_key"),
    [("x86_64", "darwin-x64"), ("arm64", "darwin-arm64")],
)
def test_surface_release_validates_darwin_binaries(
    tmp_path: Path,
    machine: str,
    platform_key: str,
) -> None:
    bundle, _digest = _write_fake_bundle(
        tmp_path,
        manifest_schema="surface",
        platform_keys=(platform_key,),
    )

    descriptor = validate_zotero_bridge_bundle_root(
        bundle,
        system="Darwin",
        machine=machine,
    )

    assert descriptor.binary_for(platform_key) is not None


def test_auto_update_noops_when_remote_commit_is_current(tmp_path: Path, monkeypatch) -> None:
    bundle, _digest = _write_fake_bundle(tmp_path)
    profile = _profile(tmp_path)
    manager = ZoteroBridgeBundleAutoUpdateManager(profile)
    write_zotero_bridge_bundle_state(
        profile,
        {
            "status": "installed",
            "active_commit": "abc123",
            "active_bundle_root": str(bundle),
        },
    )
    monkeypatch.setattr(manager, "_remote_head", lambda _cfg: "abc123")
    monkeypatch.setattr(
        manager,
        "_ensure_version_dir",
        lambda _cfg, _commit: pytest.fail("check must not download a bundle"),
    )

    state = manager._check_update_sync(_auto_update_cfg())

    assert state["status"] == "up_to_date"
    assert state["active_commit"] == "abc123"
    assert state["available_commit"] is None


def test_auto_update_installs_new_valid_bundle(tmp_path: Path, monkeypatch) -> None:
    bundle, _digest = _write_fake_bundle(tmp_path, manifest_schema="surface")
    version_dir = tmp_path / "cache" / "plugin-bundles" / "zotero-bridge-cli-bundle" / "versions" / "def456"
    version_dir.parent.mkdir(parents=True)
    shutil.copytree(bundle, version_dir)
    profile = _profile(tmp_path)
    manager = ZoteroBridgeBundleAutoUpdateManager(profile)
    monkeypatch.setattr(manager, "_remote_head", lambda _cfg: "def456")
    monkeypatch.setattr(manager, "_ensure_version_dir", lambda _cfg, _commit: version_dir)

    checked = manager._check_update_sync(_auto_update_cfg())

    assert checked["status"] == "update_available"
    assert checked["available_commit"] == "def456"
    assert find_default_bundle_root(profile) != version_dir

    state = manager._install_update_sync(_auto_update_cfg())

    assert state["status"] == "installed"
    assert state["active_commit"] == "def456"
    assert find_default_bundle_root(profile) == version_dir
    assert (profile.npm_prefix / "bin" / "zotero-bridge").exists()


def test_auto_update_failure_keeps_previous_state(tmp_path: Path, monkeypatch) -> None:
    previous_bundle, _digest = _write_fake_bundle(tmp_path)
    profile = _profile(tmp_path)
    manager = ZoteroBridgeBundleAutoUpdateManager(profile)
    previous = {
        "status": "installed",
        "active_commit": "abc123",
        "active_bundle_root": str(previous_bundle),
    }
    write_zotero_bridge_bundle_state(profile, previous)
    monkeypatch.setattr(manager, "_remote_head", lambda _cfg: "def456")
    monkeypatch.setattr(
        manager,
        "_ensure_version_dir",
        lambda _cfg, _commit: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    state = manager._check_and_install_sync(_auto_update_cfg())

    assert state["status"] == "failed"
    assert state["active_commit"] == "abc123"
    assert state["error_message"] == "boom"
    assert find_default_bundle_root(profile) == previous_bundle


def test_auto_update_invalid_surface_candidate_keeps_previous_active_bundle(
    tmp_path: Path,
    monkeypatch,
) -> None:
    previous_bundle, _digest = _write_fake_bundle(tmp_path / "previous")
    candidate_bundle, _digest = _write_fake_bundle(
        tmp_path / "candidate",
        manifest_schema="surface",
    )
    manifest_path = candidate_bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["releaseSet"]["cli"]["binaries"][0]["sha256"] = "0" * 64
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    profile = _profile(tmp_path)
    manager = ZoteroBridgeBundleAutoUpdateManager(profile)
    write_zotero_bridge_bundle_state(
        profile,
        {
            "status": "installed",
            "active_commit": "abc123",
            "active_bundle_root": str(previous_bundle),
        },
    )
    monkeypatch.setattr(manager, "_remote_head", lambda _cfg: "def456")
    monkeypatch.setattr(
        manager,
        "_ensure_version_dir",
        lambda _cfg, _commit: candidate_bundle,
    )

    state = manager._check_and_install_sync(_auto_update_cfg())

    assert state["status"] == "failed"
    assert state["active_commit"] == "abc123"
    assert find_default_bundle_root(profile) == previous_bundle


def test_manual_install_rejects_candidate_when_remote_branch_moves(
    tmp_path: Path,
    monkeypatch,
) -> None:
    profile = _profile(tmp_path)
    manager = ZoteroBridgeBundleAutoUpdateManager(profile)
    write_zotero_bridge_bundle_state(
        profile,
        {
            "status": "update_available",
            "available_commit": "abc123",
        },
    )
    monkeypatch.setattr(manager, "_remote_head", lambda _cfg: "def456")

    with pytest.raises(ZoteroBridgeBundleUpdateConflict):
        manager._install_update_sync(_auto_update_cfg())

    status = manager.management_status()
    assert status["update_status"] == "failed"
    assert status["available_commit"] is None


def test_manual_install_is_idempotent_when_candidate_is_already_active(
    tmp_path: Path,
    monkeypatch,
) -> None:
    bundle, _digest = _write_fake_bundle(tmp_path)
    profile = _profile(tmp_path)
    manager = ZoteroBridgeBundleAutoUpdateManager(profile)
    write_zotero_bridge_bundle_state(
        profile,
        {
            "status": "update_available",
            "active_commit": "abc123",
            "active_bundle_root": str(bundle),
            "available_commit": "abc123",
        },
    )
    monkeypatch.setattr(manager, "_remote_head", lambda _cfg: "abc123")
    monkeypatch.setattr(
        manager,
        "_ensure_version_dir",
        lambda _cfg, _commit: pytest.fail("idempotent install must not download"),
    )

    state = manager._install_update_sync(_auto_update_cfg())

    assert state["status"] == "installed"
    assert state["active_commit"] == "abc123"
    assert state["available_commit"] is None


@pytest.mark.asyncio
async def test_manual_update_remains_available_when_auto_update_is_disabled(
    tmp_path: Path,
    monkeypatch,
) -> None:
    profile = _profile(tmp_path)
    manager = ZoteroBridgeBundleAutoUpdateManager(profile)
    disabled_cfg = ZoteroBridgeBundleAutoUpdateConfig(
        **{**_auto_update_cfg().__dict__, "enabled": False}
    )
    monkeypatch.setattr(manager, "load_config", lambda: disabled_cfg)
    monkeypatch.setattr(manager, "_remote_head", lambda _cfg: "def456")

    state = await manager.check_update()

    assert state["status"] == "update_available"
    assert state["available_commit"] == "def456"


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


def test_zotero_bridge_submodule_checkout_and_deployment_wiring_are_valid() -> None:
    gitmodules = Path(".gitmodules").read_text(encoding="utf-8")
    assert '[submodule "plugins/zotero-bridge-cli-bundle"]' in gitmodules
    assert "path = plugins/zotero-bridge-cli-bundle" in gitmodules
    assert "url = https://github.com/leike0813/zotero-agents.git" in gitmodules
    assert "branch = host-bridge/zotero-bridge-cli-bundle" in gitmodules

    bundle = Path("plugins/zotero-bridge-cli-bundle")
    validate_zotero_bridge_bundle_root(bundle)

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
