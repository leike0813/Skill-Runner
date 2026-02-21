import io
import json
import re
import shutil
import zipfile
from pathlib import Path
from typing import Any, Optional, Tuple

import yaml  # type: ignore

_packaging_version: Any = None
try:
    import packaging.version as _packaging_version  # type: ignore
except Exception:  # pragma: no cover
    _packaging_version = None


class SkillPackageValidator:
    """Shared validator for persistent and temporary skill package uploads."""

    SUPPORTED_ENGINES = ("codex", "gemini", "iflow")

    REQUIRED_FILES = (
        "SKILL.md",
        "assets/runner.json",
    )

    def inspect_zip_top_level_from_bytes(self, payload: bytes) -> str:
        try:
            with zipfile.ZipFile(io.BytesIO(payload), "r") as zf:
                return self.inspect_zip_top_level(zf.namelist())
        except zipfile.BadZipFile as exc:
            raise ValueError("Invalid zip package") from exc

    def inspect_zip_top_level_from_path(self, package_path: Path) -> str:
        try:
            with zipfile.ZipFile(package_path, "r") as zf:
                return self.inspect_zip_top_level(zf.namelist())
        except zipfile.BadZipFile as exc:
            raise ValueError("Invalid zip package") from exc

    def inspect_zip_top_level(self, names: list[str]) -> str:
        top_levels = set()
        for name in names:
            clean = name.strip("/")
            if not clean:
                continue
            self._validate_zip_entry(clean)
            top = clean.split("/", 1)[0]
            if top == "__MACOSX":
                continue
            top_levels.add(top)
        if len(top_levels) != 1:
            raise ValueError("Skill package must contain exactly one top-level directory")
        return next(iter(top_levels))

    def extract_zip_safe(self, package_path: Path, target_dir: Path) -> None:
        if target_dir.exists():
            shutil.rmtree(target_dir, ignore_errors=True)
        target_dir.mkdir(parents=True, exist_ok=True)
        target_root = target_dir.resolve()
        try:
            with zipfile.ZipFile(package_path, "r") as zf:
                for member in zf.infolist():
                    clean = member.filename.strip("/")
                    if not clean or clean.startswith("__MACOSX/"):
                        continue
                    self._validate_zip_entry(clean)
                    out_path = (target_dir / clean).resolve()
                    if not str(out_path).startswith(str(target_root)):
                        raise ValueError(f"Unsafe zip entry path: {clean}")
                    if member.is_dir():
                        out_path.mkdir(parents=True, exist_ok=True)
                        continue
                    out_path.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(member, "r") as src, open(out_path, "wb") as dst:
                        dst.write(src.read())
        except zipfile.BadZipFile as exc:
            raise ValueError("Invalid zip package") from exc

    def validate_skill_dir(
        self,
        skill_dir: Path,
        top_level_dir: str,
        *,
        require_version: bool
    ) -> Tuple[str, Optional[str]]:
        missing = []
        for rel in self.REQUIRED_FILES:
            if not (skill_dir / rel).exists():
                missing.append(rel)
        if missing:
            raise ValueError(f"Skill package missing required files: {', '.join(missing)}")

        runner_path = skill_dir / "assets" / "runner.json"
        try:
            runner = json.loads(runner_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Invalid assets/runner.json") from exc

        runner_id = runner.get("id")
        if not isinstance(runner_id, str) or not runner_id.strip():
            raise ValueError("runner.json must define a non-empty id")
        skill_id = runner_id.strip()

        skill_name = self._extract_skill_name(skill_dir / "SKILL.md")
        if not skill_name:
            raise ValueError("SKILL.md must define frontmatter name")
        if skill_id != top_level_dir or skill_name != skill_id:
            raise ValueError("Skill identity mismatch: directory, runner.json id, and SKILL.md name must match")

        schemas = runner.get("schemas")
        if not isinstance(schemas, dict):
            raise ValueError("runner.json must define schemas")
        for key in ("input", "parameter", "output"):
            schema_rel = schemas.get(key)
            if not isinstance(schema_rel, str) or not schema_rel.strip():
                raise ValueError("runner.json schemas must define input, parameter and output")
            if not (skill_dir / schema_rel).exists():
                missing.append(schema_rel)
        if missing:
            raise ValueError(f"Skill package missing required files: {', '.join(missing)}")

        self.resolve_manifest_engines(runner)

        artifacts = runner.get("artifacts")
        if artifacts is not None and not isinstance(artifacts, list):
            raise ValueError("runner.json artifacts must be a list when provided")

        version = runner.get("version")
        if require_version:
            if not isinstance(version, str) or not version.strip():
                raise ValueError("runner.json must define a non-empty version")
            version = version.strip()
            self.parse_version(version)
        elif isinstance(version, str) and version.strip():
            version = version.strip()
            self.parse_version(version)
        else:
            version = None

        return skill_id, version

    def resolve_manifest_engines(self, runner: dict[str, Any]) -> list[str]:
        supported = set(self.SUPPORTED_ENGINES)

        allowlist_raw = runner.get("engines")
        blocklist_raw = runner.get("unsupported_engines")

        if allowlist_raw is not None and not isinstance(allowlist_raw, list):
            raise ValueError("runner.json engines must be a list when provided")
        if blocklist_raw is not None and not isinstance(blocklist_raw, list):
            raise ValueError("runner.json unsupported_engines must be a list when provided")

        allowlist = self._normalize_engine_list("engines", allowlist_raw or [], supported)
        blocklist = self._normalize_engine_list("unsupported_engines", blocklist_raw or [], supported)

        base_engines = allowlist if allowlist else list(self.SUPPORTED_ENGINES)
        overlap = sorted(set(allowlist) & set(blocklist))
        if overlap:
            raise ValueError(
                "runner.json engines and unsupported_engines must not overlap: "
                + ", ".join(overlap)
            )

        blockset = set(blocklist)
        effective = [engine for engine in base_engines if engine not in blockset]
        if not effective:
            raise ValueError("runner.json resolves to no supported engines")
        return effective

    def _normalize_engine_list(self, field: str, values: list[Any], supported: set[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for item in values:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"runner.json {field} must contain non-empty engine names")
            engine = item.strip()
            if engine not in supported:
                raise ValueError(f"runner.json {field} contains unsupported engine: {engine}")
            if engine in seen:
                continue
            seen.add(engine)
            normalized.append(engine)
        return normalized

    def parse_version(self, raw: str) -> Any:
        if _packaging_version is not None:
            try:
                return _packaging_version.Version(raw)
            except _packaging_version.InvalidVersion as exc:
                raise ValueError(f"Invalid skill version: {raw}") from exc

        if not re.match(r"^\d+(\.\d+)*$", raw):
            raise ValueError(f"Invalid skill version: {raw}")
        return tuple(int(part) for part in raw.split("."))

    def ensure_version_upgrade(self, old_version: str, new_version: str) -> None:
        old_parsed = self.parse_version(old_version)
        new_parsed = self.parse_version(new_version)
        if new_parsed <= old_parsed:
            raise ValueError(
                f"Skill update requires strictly higher version: installed={old_version}, uploaded={new_version}"
            )

    def _extract_skill_name(self, skill_md_path: Path) -> Optional[str]:
        content = skill_md_path.read_text(encoding="utf-8")
        match = re.match(r"^---\n(.*?)\n---\n", content, re.DOTALL)
        if not match:
            return None
        frontmatter = yaml.safe_load(match.group(1)) or {}
        name = frontmatter.get("name")
        if not isinstance(name, str):
            return None
        return name.strip() or None

    def _validate_zip_entry(self, clean_name: str) -> None:
        if clean_name.startswith("/") or clean_name.startswith("\\"):
            raise ValueError(f"Unsafe zip entry path: {clean_name}")
        p = Path(clean_name)
        if p.is_absolute():
            raise ValueError(f"Unsafe zip entry path: {clean_name}")
        parts = p.parts
        if any(part == ".." for part in parts):
            raise ValueError(f"Unsafe zip entry path: {clean_name}")
        if len(parts) > 0 and parts[0].endswith(":"):
            raise ValueError(f"Unsafe zip entry path: {clean_name}")
