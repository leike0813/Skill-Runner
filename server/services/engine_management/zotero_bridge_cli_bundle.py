import hashlib
import json
import logging
import os
import platform as platform_module
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping

from server.services.engine_management.runtime_profile import RuntimeProfile, get_runtime_profile

logger = logging.getLogger(__name__)

PLUGIN_SUBMODULE_RELATIVE_PATH = Path("plugins") / "zotero-bridge-cli-bundle"
MANAGED_BUNDLE_STORE_RELATIVE_PATH = Path("plugin-bundles") / "zotero-bridge-cli-bundle"
MANAGED_BUNDLE_STATE_NAME = "state.json"
MANAGED_BUNDLE_CURRENT_NAME = "current"
ZOTERO_BRIDGE_PROFILE_ENV = "ZOTERO_BRIDGE_PROFILE"
ZOTERO_BRIDGE_ENDPOINT_ENV = "ZOTERO_BRIDGE_ENDPOINT"
ZOTERO_BRIDGE_TOKEN_ENV = "ZOTERO_BRIDGE_TOKEN"
ZOTERO_BRIDGE_CONNECTION_MODE_ENV = "ZOTERO_BRIDGE_CONNECTION_MODE"
ZOTERO_BRIDGE_PROFILE_RELATIVE_PATH = Path("zotero-bridge") / "bridge-profile.json"
WRAPPER_SKILL_ID = "zotero-bridge-cli"

GLOBAL_SKILL_DIRS: Mapping[str, Path] = {
    "codex": Path(".codex") / "skills" / WRAPPER_SKILL_ID,
    "claude": Path(".claude") / "skills" / WRAPPER_SKILL_ID,
    "qwen": Path(".qwen") / "skills" / WRAPPER_SKILL_ID,
    "opencode": Path(".opencode") / "skills" / WRAPPER_SKILL_ID,
    "kilo": Path(".kilo") / "skills" / WRAPPER_SKILL_ID,
}


class ZoteroBridgeBundleError(RuntimeError):
    """Raised when a present Zotero Bridge bundle is invalid."""


@dataclass(frozen=True)
class ZoteroBridgeInstallResult:
    bundle_root: Path | None
    platform_key: str | None
    cli_installed: bool
    profile_path: Path | None
    skill_destinations: tuple[Path, ...]
    skipped_reason: str | None = None


def zotero_bridge_profile_path(profile: RuntimeProfile) -> Path:
    return profile.agent_cache_root / ZOTERO_BRIDGE_PROFILE_RELATIVE_PATH


def zotero_bridge_bin_path(profile: RuntimeProfile) -> Path:
    return profile.zotero_bridge_bin_path


def managed_bundle_store_root(profile: RuntimeProfile) -> Path:
    return profile.agent_cache_root / MANAGED_BUNDLE_STORE_RELATIVE_PATH


def managed_bundle_state_path(profile: RuntimeProfile) -> Path:
    return managed_bundle_store_root(profile) / MANAGED_BUNDLE_STATE_NAME


def managed_bundle_versions_root(profile: RuntimeProfile) -> Path:
    return managed_bundle_store_root(profile) / "versions"


def managed_bundle_current_path(profile: RuntimeProfile) -> Path:
    return managed_bundle_store_root(profile) / MANAGED_BUNDLE_CURRENT_NAME


def builtin_bundle_root() -> Path:
    candidates = [
        Path.cwd() / PLUGIN_SUBMODULE_RELATIVE_PATH,
        Path(__file__).resolve().parents[3] / PLUGIN_SUBMODULE_RELATIVE_PATH,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def find_default_bundle_root(profile: RuntimeProfile | None = None) -> Path:
    runtime_profile = profile or get_runtime_profile()
    managed_root = resolve_managed_bundle_root(runtime_profile)
    if managed_root is not None:
        return managed_root
    return builtin_bundle_root()


def resolve_managed_bundle_root(profile: RuntimeProfile) -> Path | None:
    state = read_zotero_bridge_bundle_state(profile)
    state_root = state.get("active_bundle_root")
    candidates: list[Path] = []
    if isinstance(state_root, str) and state_root:
        candidates.append(Path(state_root))
    current_path = managed_bundle_current_path(profile)
    if current_path.exists():
        try:
            current_payload = _read_json_object(current_path)
            current_root = current_payload.get("active_bundle_root")
            if isinstance(current_root, str) and current_root:
                candidates.append(Path(current_root))
        except ZoteroBridgeBundleError:
            try:
                current_commit = current_path.read_text(encoding="utf-8").strip()
                if current_commit:
                    candidates.append(managed_bundle_versions_root(profile) / current_commit)
            except (OSError, UnicodeDecodeError):
                pass

    for candidate in candidates:
        try:
            validate_zotero_bridge_bundle_root(candidate)
        except ZoteroBridgeBundleError:
            logger.warning(
                "Managed Zotero Bridge CLI bundle is invalid; ignoring managed bundle",
                extra={
                    "component": "engine_management.zotero_bridge_cli_bundle",
                    "action": "resolve_managed_bundle",
                    "bundle_root": str(candidate),
                },
                exc_info=True,
            )
            continue
        return candidate
    return None


def read_zotero_bridge_bundle_state(profile: RuntimeProfile) -> dict[str, Any]:
    path = managed_bundle_state_path(profile)
    if not path.exists():
        return {
            "status": "missing",
            "active_commit": None,
            "active_bundle_root": None,
            "state_path": str(path),
        }
    try:
        payload = _read_json_object(path)
    except ZoteroBridgeBundleError as exc:
        return {
            "status": "unreadable",
            "active_commit": None,
            "active_bundle_root": None,
            "state_path": str(path),
            "error_code": "state_unreadable",
            "error_message": str(exc),
        }
    payload.setdefault("state_path", str(path))
    return payload


def write_zotero_bridge_bundle_state(
    profile: RuntimeProfile,
    payload: Mapping[str, Any],
) -> None:
    state_path = managed_bundle_state_path(profile)
    content = dict(payload)
    content["state_path"] = str(state_path)
    _write_text_atomically(
        state_path,
        json.dumps(content, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )


def write_managed_bundle_current(
    profile: RuntimeProfile,
    *,
    active_commit: str,
    active_bundle_root: Path,
) -> None:
    _write_text_atomically(
        managed_bundle_current_path(profile),
        json.dumps(
            {
                "active_commit": active_commit,
                "active_bundle_root": str(active_bundle_root),
            },
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        )
        + "\n",
    )


def zotero_bridge_bundle_status(profile: RuntimeProfile | None = None) -> dict[str, Any]:
    runtime_profile = profile or get_runtime_profile()
    state = read_zotero_bridge_bundle_state(runtime_profile)
    managed_root = resolve_managed_bundle_root(runtime_profile)
    default_root = find_default_bundle_root(runtime_profile)
    source = "managed" if managed_root is not None and default_root == managed_root else "builtin"
    return {
        "source": source,
        "bundle_root": str(default_root),
        "managed_store_root": str(managed_bundle_store_root(runtime_profile)),
        "state": state,
    }


def find_builtin_bundle_root() -> Path:
    return builtin_bundle_root()


def resolve_bundle_platform_key(
    *,
    system: str | None = None,
    machine: str | None = None,
) -> str | None:
    normalized_system = (system or platform_module.system()).strip().lower()
    normalized_machine = (machine or platform_module.machine()).strip().lower()

    if normalized_system.startswith("win"):
        if normalized_machine in {"amd64", "x86_64", "x64"}:
            return "win32-x64"
        return None
    if normalized_system == "linux":
        if normalized_machine in {"x86_64", "amd64", "x64"}:
            return "linux-x64"
        if normalized_machine in {"aarch64", "arm64"}:
            return "linux-arm64"
        if normalized_machine in {"armv6l", "armv7l", "arm"}:
            return "linux-arm"
        if normalized_machine in {"i386", "i686", "x86"}:
            return "linux-x86"
    return None


def ensure_zotero_bridge_managed_plugin(
    profile: RuntimeProfile,
    *,
    engines: Iterable[str],
    bundle_root: Path | None = None,
    system: str | None = None,
    machine: str | None = None,
) -> ZoteroBridgeInstallResult:
    root = bundle_root or find_default_bundle_root(profile)
    manifest_path = root / "manifest.json"
    if not manifest_path.exists():
        logger.warning(
            "Zotero Bridge CLI bundle is unavailable; skipping managed plugin install",
            extra={
                "component": "engine_management.zotero_bridge_cli_bundle",
                "action": "ensure_managed_plugin",
                "bundle_root": str(root),
            },
        )
        return ZoteroBridgeInstallResult(
            bundle_root=None,
            platform_key=None,
            cli_installed=False,
            profile_path=None,
            skill_destinations=(),
            skipped_reason="bundle_missing",
        )

    manifest = _read_json_object(manifest_path)
    skill_destinations = _sync_wrapper_skill(
        profile,
        root,
        manifest,
        engines=engines,
    )
    profile_path = _install_profile(profile, root, manifest)

    platform_key = resolve_bundle_platform_key(system=system, machine=machine)
    if platform_key is None:
        logger.warning(
            "Zotero Bridge CLI bundle has no supported platform mapping; skipping CLI install",
            extra={
                "component": "engine_management.zotero_bridge_cli_bundle",
                "action": "resolve_platform",
                "system": system or platform_module.system(),
                "machine": machine or platform_module.machine(),
            },
        )
        return ZoteroBridgeInstallResult(
            bundle_root=root,
            platform_key=None,
            cli_installed=False,
            profile_path=profile_path,
            skill_destinations=skill_destinations,
            skipped_reason="unsupported_platform",
        )

    platform_entry = _platform_entry(manifest, platform_key)
    if platform_entry is None:
        logger.warning(
            "Zotero Bridge CLI manifest has no entry for current platform; skipping CLI install",
            extra={
                "component": "engine_management.zotero_bridge_cli_bundle",
                "action": "select_manifest_platform",
                "platform_key": platform_key,
            },
        )
        return ZoteroBridgeInstallResult(
            bundle_root=root,
            platform_key=platform_key,
            cli_installed=False,
            profile_path=profile_path,
            skill_destinations=skill_destinations,
            skipped_reason="manifest_platform_missing",
        )

    _install_cli(profile, root, platform_entry, platform_key=platform_key)
    return ZoteroBridgeInstallResult(
        bundle_root=root,
        platform_key=platform_key,
        cli_installed=True,
        profile_path=profile_path,
        skill_destinations=skill_destinations,
        skipped_reason=None,
    )


def _read_json_object(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ZoteroBridgeBundleError(f"Invalid Zotero Bridge JSON file: {path}") from exc
    if not isinstance(payload, dict):
        raise ZoteroBridgeBundleError(f"Zotero Bridge JSON file is not an object: {path}")
    return payload


def _platform_entry(
    manifest: Mapping[str, Any],
    platform_key: str,
) -> Mapping[str, Any] | None:
    cli = manifest.get("cli")
    platforms = cli.get("platforms") if isinstance(cli, Mapping) else None
    if not isinstance(platforms, list):
        raise ZoteroBridgeBundleError("Zotero Bridge manifest is missing cli.platforms")
    for entry in platforms:
        if isinstance(entry, Mapping) and entry.get("platform") == platform_key:
            return entry
    return None


def validate_zotero_bridge_bundle_root(
    bundle_root: Path,
    *,
    system: str | None = None,
    machine: str | None = None,
) -> dict[str, Any]:
    manifest_path = bundle_root / "manifest.json"
    if not manifest_path.is_file():
        raise ZoteroBridgeBundleError(f"Zotero Bridge manifest is missing: {manifest_path}")

    manifest = _read_json_object(manifest_path)
    wrapper = manifest.get("wrapperSkill")
    if not isinstance(wrapper, Mapping):
        raise ZoteroBridgeBundleError("Zotero Bridge manifest is missing wrapperSkill")
    wrapper_path = wrapper.get("path")
    if not isinstance(wrapper_path, str) or not wrapper_path:
        raise ZoteroBridgeBundleError("Zotero Bridge manifest wrapperSkill.path is missing")
    wrapper_root = _bundle_child_path(bundle_root, wrapper_path)
    if not (wrapper_root / "SKILL.md").is_file():
        raise ZoteroBridgeBundleError(f"Zotero Bridge wrapper skill is missing: {wrapper_root}")

    template_path = _manifest_profile_template_path(bundle_root, manifest)
    if not template_path.is_file():
        raise ZoteroBridgeBundleError(f"Zotero Bridge profile template is missing: {template_path}")

    platform_key = resolve_bundle_platform_key(system=system, machine=machine)
    if platform_key is not None:
        platform_entry = _platform_entry(manifest, platform_key)
        if platform_entry is None:
            raise ZoteroBridgeBundleError(
                f"Zotero Bridge manifest has no entry for current platform: {platform_key}"
            )
        binary_relpath = platform_entry.get("binary")
        expected_sha = platform_entry.get("sha256")
        if not isinstance(binary_relpath, str) or not binary_relpath:
            raise ZoteroBridgeBundleError("Zotero Bridge platform entry is missing binary")
        if not isinstance(expected_sha, str) or not expected_sha:
            raise ZoteroBridgeBundleError("Zotero Bridge platform entry is missing sha256")
        binary_path = _bundle_child_path(bundle_root, binary_relpath)
        if not binary_path.is_file():
            raise ZoteroBridgeBundleError(f"Zotero Bridge binary is missing: {binary_path}")
        actual_sha = _sha256_file(binary_path)
        if actual_sha.lower() != expected_sha.lower():
            raise ZoteroBridgeBundleError(
                f"Zotero Bridge binary sha256 mismatch for {binary_path}: "
                f"expected {expected_sha}, got {actual_sha}"
            )

    return {
        "manifest": manifest,
        "platform_key": platform_key,
    }


def _install_cli(
    profile: RuntimeProfile,
    bundle_root: Path,
    entry: Mapping[str, Any],
    *,
    platform_key: str,
) -> Path:
    binary_relpath = entry.get("binary")
    expected_sha = entry.get("sha256")
    if not isinstance(binary_relpath, str) or not binary_relpath:
        raise ZoteroBridgeBundleError("Zotero Bridge platform entry is missing binary")
    if not isinstance(expected_sha, str) or not expected_sha:
        raise ZoteroBridgeBundleError("Zotero Bridge platform entry is missing sha256")

    source = _bundle_child_path(bundle_root, binary_relpath)
    if not source.is_file():
        raise ZoteroBridgeBundleError(f"Zotero Bridge binary is missing: {source}")
    actual_sha = _sha256_file(source)
    if actual_sha.lower() != expected_sha.lower():
        raise ZoteroBridgeBundleError(
            f"Zotero Bridge binary sha256 mismatch for {source}: "
            f"expected {expected_sha}, got {actual_sha}"
        )

    bin_dir = profile.npm_prefix / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    target = zotero_bridge_bin_path(profile)
    _copy_file_atomically(source, target)
    if not platform_key.startswith("win32-"):
        os.chmod(target, 0o755)
    else:
        cmd_target = bin_dir / "zotero-bridge.cmd"
        _write_text_atomically(cmd_target, '@echo off\r\n"%~dp0zotero-bridge.exe" %*\r\n')
    return target


def _install_profile(
    profile: RuntimeProfile,
    bundle_root: Path,
    manifest: Mapping[str, Any],
) -> Path:
    template_path = _manifest_profile_template_path(bundle_root, manifest)
    template = _read_json_object(template_path)
    profile_payload = _managed_profile_payload(template, manifest)
    target = zotero_bridge_profile_path(profile)
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_text_atomically(
        target,
        json.dumps(profile_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )
    return target


def _manifest_profile_template_path(
    bundle_root: Path,
    manifest: Mapping[str, Any],
) -> Path:
    profile_template = manifest.get("profileTemplate")
    if not isinstance(profile_template, Mapping):
        raise ZoteroBridgeBundleError("Zotero Bridge manifest is missing profileTemplate")
    path = profile_template.get("path")
    if not isinstance(path, str) or not path:
        raise ZoteroBridgeBundleError("Zotero Bridge manifest profileTemplate.path is missing")
    return _bundle_child_path(bundle_root, path)


def _managed_profile_payload(
    template: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, Any]:
    profile_template = manifest.get("profileTemplate")
    profile_template = profile_template if isinstance(profile_template, Mapping) else {}
    token_env = profile_template.get("tokenEnv") or ZOTERO_BRIDGE_TOKEN_ENV
    endpoint_env = profile_template.get("endpointEnv") or ZOTERO_BRIDGE_ENDPOINT_ENV
    connection_mode_env = (
        profile_template.get("connectionModeEnv") or ZOTERO_BRIDGE_CONNECTION_MODE_ENV
    )

    auth = template.get("auth")
    auth_type = auth.get("type") if isinstance(auth, Mapping) else "bearer"
    payload: dict[str, Any] = {
        "schema": template.get("schema", "zotero-bridge.profile.v1"),
        "protocol": template.get("protocol", "host-bridge.v1"),
        "auth": {
            "type": auth_type or "bearer",
            "tokenEnv": token_env,
        },
        "endpointEnv": endpoint_env,
        "connectionModeEnv": connection_mode_env,
        "source": "skill-runner-managed-profile",
    }
    return payload


def _sync_wrapper_skill(
    profile: RuntimeProfile,
    bundle_root: Path,
    manifest: Mapping[str, Any],
    *,
    engines: Iterable[str],
) -> tuple[Path, ...]:
    wrapper = manifest.get("wrapperSkill")
    if not isinstance(wrapper, Mapping):
        raise ZoteroBridgeBundleError("Zotero Bridge manifest is missing wrapperSkill")
    wrapper_path = wrapper.get("path")
    if not isinstance(wrapper_path, str) or not wrapper_path:
        raise ZoteroBridgeBundleError("Zotero Bridge manifest wrapperSkill.path is missing")

    source = _bundle_child_path(bundle_root, wrapper_path)
    if not (source / "SKILL.md").is_file():
        raise ZoteroBridgeBundleError(f"Zotero Bridge wrapper skill is missing: {source}")

    destinations: list[Path] = []
    for engine in engines:
        relpath = GLOBAL_SKILL_DIRS.get(engine)
        if relpath is None:
            continue
        destination = profile.agent_home / relpath
        _replace_tree(source, destination)
        destinations.append(destination)
    return tuple(destinations)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bundle_child_path(bundle_root: Path, relpath: str) -> Path:
    path = Path(relpath)
    if path.is_absolute() or ".." in path.parts:
        raise ZoteroBridgeBundleError(f"Zotero Bridge bundle path is unsafe: {relpath}")
    return bundle_root / path


def _copy_file_atomically(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.tmp")
    try:
        shutil.copyfile(source, tmp)
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()


def _write_text_atomically(target: Path, content: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_name(f".{target.name}.tmp")
    try:
        tmp.write_text(content, encoding="utf-8")
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()


def _replace_tree(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_name(f".{destination.name}.tmp")
    if tmp.exists():
        shutil.rmtree(tmp)
    _copy_tree_contents(source, tmp)
    if destination.exists():
        shutil.rmtree(destination)
    os.replace(tmp, destination)


def _copy_tree_contents(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=False)
    for child in source.iterdir():
        target = destination / child.name
        if child.is_dir():
            _copy_tree_contents(child, target)
        elif child.is_file():
            shutil.copyfile(child, target)
