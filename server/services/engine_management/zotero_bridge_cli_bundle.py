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
LEGACY_BUNDLE_SCHEMA = "zotero-bridge-cli-bundle.v1"
SURFACE_RELEASE_SCHEMA = "host-bridge.surface-release.v1"
SURFACE_WRAPPER_SKILL_RELATIVE_PATH = Path("skills") / WRAPPER_SKILL_ID
SURFACE_PROFILE_TEMPLATE_RELATIVE_PATH = (
    SURFACE_WRAPPER_SKILL_RELATIVE_PATH / "assets" / "profile.template.json"
)

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
class ZoteroBridgeBinaryDescriptor:
    platform_key: str
    relative_path: Path
    sha256: str


@dataclass(frozen=True)
class ZoteroBridgeBundleDescriptor:
    schema: str
    version: str | None
    wrapper_skill_relative_path: Path
    profile_template_relative_path: Path
    endpoint_env: str
    token_env: str
    connection_mode_env: str
    binaries: tuple[ZoteroBridgeBinaryDescriptor, ...]

    def binary_for(self, platform_key: str) -> ZoteroBridgeBinaryDescriptor | None:
        return next(
            (binary for binary in self.binaries if binary.platform_key == platform_key),
            None,
        )


@dataclass(frozen=True)
class ZoteroBridgeInstallResult:
    bundle_root: Path | None
    platform_key: str | None
    cli_installed: bool
    profile_path: Path | None
    skill_destinations: tuple[Path, ...]
    skipped_reason: str | None = None


@dataclass(frozen=True)
class _ValidatedZoteroBridgeBundle:
    descriptor: ZoteroBridgeBundleDescriptor
    wrapper_root: Path
    profile_template: Mapping[str, Any]
    platform_key: str | None
    binary: ZoteroBridgeBinaryDescriptor | None
    binary_path: Path | None


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
        "version": read_zotero_bridge_bundle_version(default_root),
        "current_commit": (
            _managed_bundle_commit_for_root(runtime_profile, managed_root, state)
            if source == "managed" and managed_root is not None
            else None
        ),
        "bundle_root": str(default_root),
        "managed_store_root": str(managed_bundle_store_root(runtime_profile)),
        "state": state,
    }


def read_zotero_bridge_bundle_version(bundle_root: Path) -> str | None:
    """Read the version through the canonical manifest adapter."""
    try:
        descriptor = load_zotero_bridge_bundle_descriptor(bundle_root)
    except ZoteroBridgeBundleError:
        return None
    return descriptor.version


def _managed_bundle_commit_for_root(
    profile: RuntimeProfile,
    managed_root: Path,
    state: Mapping[str, Any],
) -> str | None:
    state_root = state.get("active_bundle_root")
    state_commit = state.get("active_commit")
    if (
        isinstance(state_root, str)
        and isinstance(state_commit, str)
        and state_commit
        and _paths_match(Path(state_root), managed_root)
    ):
        return state_commit

    current_path = managed_bundle_current_path(profile)
    if current_path.exists():
        try:
            current = _read_json_object(current_path)
        except ZoteroBridgeBundleError:
            try:
                legacy_commit = current_path.read_text(encoding="utf-8").strip()
            except (OSError, UnicodeDecodeError):
                legacy_commit = ""
            if legacy_commit and _paths_match(
                managed_bundle_versions_root(profile) / legacy_commit,
                managed_root,
            ):
                return legacy_commit
        else:
            current_root = current.get("active_bundle_root")
            current_commit = current.get("active_commit")
            if (
                isinstance(current_root, str)
                and isinstance(current_commit, str)
                and current_commit
                and _paths_match(Path(current_root), managed_root)
            ):
                return current_commit
    return None


def _paths_match(left: Path, right: Path) -> bool:
    try:
        return left.resolve() == right.resolve()
    except OSError:
        return left == right


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
    if normalized_system in {"darwin", "macos", "mac"}:
        if normalized_machine in {"x86_64", "amd64", "x64"}:
            return "darwin-x64"
        if normalized_machine in {"aarch64", "arm64"}:
            return "darwin-arm64"
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

    validated = _validate_zotero_bridge_bundle(
        root,
        system=system,
        machine=machine,
    )
    descriptor = validated.descriptor
    skill_destinations = _sync_wrapper_skill(
        profile,
        validated.wrapper_root,
        engines=engines,
    )
    profile_path = _install_profile(
        profile,
        validated.profile_template,
        descriptor,
    )

    platform_key = validated.platform_key
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

    binary = validated.binary
    binary_path = validated.binary_path
    if binary is None or binary_path is None:
        raise ZoteroBridgeBundleError(
            f"Zotero Bridge manifest has no entry for current platform: {platform_key}"
        )
    _install_cli(profile, binary_path, platform_key=platform_key)
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


def load_zotero_bridge_bundle_descriptor(
    bundle_root: Path,
) -> ZoteroBridgeBundleDescriptor:
    manifest = _read_json_object(bundle_root / "manifest.json")
    schema = manifest.get("schema")
    if schema == LEGACY_BUNDLE_SCHEMA:
        return _adapt_legacy_bundle_manifest(manifest)
    if schema == SURFACE_RELEASE_SCHEMA:
        return _adapt_surface_release_manifest(manifest)
    raise ZoteroBridgeBundleError(f"Unsupported Zotero Bridge manifest schema: {schema!r}")


def _adapt_legacy_bundle_manifest(
    manifest: Mapping[str, Any],
) -> ZoteroBridgeBundleDescriptor:
    wrapper = _required_mapping(manifest, "wrapperSkill", context="manifest")
    profile_template = _required_mapping(manifest, "profileTemplate", context="manifest")
    cli = _required_mapping(manifest, "cli", context="manifest")
    platforms = cli.get("platforms")
    if not isinstance(platforms, list):
        raise ZoteroBridgeBundleError("Zotero Bridge manifest is missing cli.platforms")
    return ZoteroBridgeBundleDescriptor(
        schema=LEGACY_BUNDLE_SCHEMA,
        version=_surface_version(manifest, required=False),
        wrapper_skill_relative_path=_safe_relative_path(
            _required_string(wrapper, "path", context="wrapperSkill")
        ),
        profile_template_relative_path=_safe_relative_path(
            _required_string(profile_template, "path", context="profileTemplate")
        ),
        endpoint_env=_optional_string(profile_template.get("endpointEnv"))
        or ZOTERO_BRIDGE_ENDPOINT_ENV,
        token_env=_optional_string(profile_template.get("tokenEnv"))
        or ZOTERO_BRIDGE_TOKEN_ENV,
        connection_mode_env=_optional_string(profile_template.get("connectionModeEnv"))
        or ZOTERO_BRIDGE_CONNECTION_MODE_ENV,
        binaries=_adapt_binary_entries(platforms, surface_release=False),
    )


def _adapt_surface_release_manifest(
    manifest: Mapping[str, Any],
) -> ZoteroBridgeBundleDescriptor:
    release_set = _required_mapping(manifest, "releaseSet", context="manifest")
    cli = _required_mapping(release_set, "cli", context="releaseSet")
    binaries = cli.get("binaries")
    if not isinstance(binaries, list):
        raise ZoteroBridgeBundleError(
            "Zotero Bridge manifest is missing releaseSet.cli.binaries"
        )
    return ZoteroBridgeBundleDescriptor(
        schema=SURFACE_RELEASE_SCHEMA,
        version=_surface_version(manifest, required=True),
        wrapper_skill_relative_path=SURFACE_WRAPPER_SKILL_RELATIVE_PATH,
        profile_template_relative_path=SURFACE_PROFILE_TEMPLATE_RELATIVE_PATH,
        endpoint_env=ZOTERO_BRIDGE_ENDPOINT_ENV,
        token_env=ZOTERO_BRIDGE_TOKEN_ENV,
        connection_mode_env=ZOTERO_BRIDGE_CONNECTION_MODE_ENV,
        binaries=_adapt_binary_entries(binaries, surface_release=True),
    )


def _adapt_binary_entries(
    entries: list[Any],
    *,
    surface_release: bool,
) -> tuple[ZoteroBridgeBinaryDescriptor, ...]:
    binaries: list[ZoteroBridgeBinaryDescriptor] = []
    seen_platforms: set[str] = set()
    for entry in entries:
        if not isinstance(entry, Mapping):
            raise ZoteroBridgeBundleError("Zotero Bridge manifest has an invalid binary entry")
        platform_key = _required_string(entry, "platform", context="binary entry")
        binary = _required_string(entry, "binary", context="binary entry")
        if platform_key in seen_platforms:
            raise ZoteroBridgeBundleError(
                f"Zotero Bridge manifest has duplicate platform entry: {platform_key}"
            )
        seen_platforms.add(platform_key)
        relative_path = (
            _safe_relative_path(Path("bin") / platform_key / binary)
            if surface_release
            else _safe_relative_path(binary)
        )
        binaries.append(
            ZoteroBridgeBinaryDescriptor(
                platform_key=platform_key,
                relative_path=relative_path,
                sha256=_required_string(entry, "sha256", context="binary entry"),
            )
        )
    return tuple(binaries)


def _surface_version(manifest: Mapping[str, Any], *, required: bool) -> str | None:
    surface = manifest.get("surface")
    if not isinstance(surface, Mapping):
        if required:
            raise ZoteroBridgeBundleError("Zotero Bridge manifest is missing surface")
        return None
    version = _optional_string(surface.get("version"))
    if required and version is None:
        raise ZoteroBridgeBundleError("Zotero Bridge manifest is missing surface.version")
    return version


def _required_mapping(
    payload: Mapping[str, Any],
    key: str,
    *,
    context: str,
) -> Mapping[str, Any]:
    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise ZoteroBridgeBundleError(f"Zotero Bridge {context} is missing {key}")
    return value


def _required_string(
    payload: Mapping[str, Any],
    key: str,
    *,
    context: str,
) -> str:
    value = _optional_string(payload.get(key))
    if value is None:
        raise ZoteroBridgeBundleError(f"Zotero Bridge {context} is missing {key}")
    return value


def _optional_string(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def validate_zotero_bridge_bundle_root(
    bundle_root: Path,
    *,
    system: str | None = None,
    machine: str | None = None,
) -> ZoteroBridgeBundleDescriptor:
    return _validate_zotero_bridge_bundle(
        bundle_root,
        system=system,
        machine=machine,
    ).descriptor


def _validate_zotero_bridge_bundle(
    bundle_root: Path,
    *,
    system: str | None = None,
    machine: str | None = None,
) -> _ValidatedZoteroBridgeBundle:
    manifest_path = bundle_root / "manifest.json"
    if not manifest_path.is_file():
        raise ZoteroBridgeBundleError(f"Zotero Bridge manifest is missing: {manifest_path}")

    descriptor = load_zotero_bridge_bundle_descriptor(bundle_root)
    wrapper_root = _bundle_child_path(
        bundle_root,
        descriptor.wrapper_skill_relative_path,
    )
    if not (wrapper_root / "SKILL.md").is_file():
        raise ZoteroBridgeBundleError(f"Zotero Bridge wrapper skill is missing: {wrapper_root}")

    template_path = _bundle_child_path(
        bundle_root,
        descriptor.profile_template_relative_path,
    )
    if not template_path.is_file():
        raise ZoteroBridgeBundleError(f"Zotero Bridge profile template is missing: {template_path}")
    profile_template = _read_json_object(template_path)

    platform_key = resolve_bundle_platform_key(system=system, machine=machine)
    binary: ZoteroBridgeBinaryDescriptor | None = None
    binary_path: Path | None = None
    if platform_key is not None:
        binary = descriptor.binary_for(platform_key)
        if binary is None:
            raise ZoteroBridgeBundleError(
                f"Zotero Bridge manifest has no entry for current platform: {platform_key}"
            )
        binary_path = _bundle_child_path(bundle_root, binary.relative_path)
        if not binary_path.is_file():
            raise ZoteroBridgeBundleError(f"Zotero Bridge binary is missing: {binary_path}")
        actual_sha = _sha256_file(binary_path)
        if actual_sha.lower() != binary.sha256.lower():
            raise ZoteroBridgeBundleError(
                f"Zotero Bridge binary sha256 mismatch for {binary_path}: "
                f"expected {binary.sha256}, got {actual_sha}"
            )

    return _ValidatedZoteroBridgeBundle(
        descriptor=descriptor,
        wrapper_root=wrapper_root,
        profile_template=profile_template,
        platform_key=platform_key,
        binary=binary,
        binary_path=binary_path,
    )


def _install_cli(
    profile: RuntimeProfile,
    source: Path,
    *,
    platform_key: str,
) -> Path:
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
    template: Mapping[str, Any],
    descriptor: ZoteroBridgeBundleDescriptor,
) -> Path:
    profile_payload = _managed_profile_payload(template, descriptor)
    target = zotero_bridge_profile_path(profile)
    target.parent.mkdir(parents=True, exist_ok=True)
    _write_text_atomically(
        target,
        json.dumps(profile_payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
    )
    return target


def _managed_profile_payload(
    template: Mapping[str, Any],
    descriptor: ZoteroBridgeBundleDescriptor,
) -> dict[str, Any]:
    auth = template.get("auth")
    auth_type = auth.get("type") if isinstance(auth, Mapping) else "bearer"
    payload: dict[str, Any] = {
        "schema": template.get("schema", "zotero-bridge.profile.v1"),
        "protocol": template.get("protocol", "host-bridge.v1"),
        "auth": {
            "type": auth_type or "bearer",
            "tokenEnv": descriptor.token_env,
        },
        "endpointEnv": descriptor.endpoint_env,
        "connectionModeEnv": descriptor.connection_mode_env,
        "source": "skill-runner-managed-profile",
    }
    return payload


def _sync_wrapper_skill(
    profile: RuntimeProfile,
    source: Path,
    *,
    engines: Iterable[str],
) -> tuple[Path, ...]:
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


def _safe_relative_path(relpath: str | Path) -> Path:
    path = Path(relpath)
    if path.is_absolute() or ".." in path.parts:
        raise ZoteroBridgeBundleError(f"Zotero Bridge bundle path is unsafe: {relpath}")
    return path


def _bundle_child_path(bundle_root: Path, relpath: str | Path) -> Path:
    path = _safe_relative_path(relpath)
    try:
        resolved_root = bundle_root.resolve()
        candidate = (bundle_root / path).resolve()
        candidate.relative_to(resolved_root)
    except (OSError, RuntimeError, ValueError) as exc:
        raise ZoteroBridgeBundleError(
            f"Zotero Bridge bundle path is unsafe: {relpath}"
        ) from exc
    return candidate


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
