import json
import logging
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from ..config import config

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelEntry:
    id: str
    display_name: Optional[str]
    deprecated: bool
    notes: Optional[str]
    supported_effort: Optional[List[str]]


@dataclass(frozen=True)
class ModelCatalog:
    engine: str
    cli_version_detected: Optional[str]
    snapshot_version_used: str
    fallback_reason: Optional[str]
    models: List[ModelEntry]


class ModelRegistry:
    def __init__(self) -> None:
        self._cache: Dict[str, ModelCatalog] = {}

    def list_engines(self) -> List[Dict[str, Optional[str]]]:
        return [
            {"engine": engine, "cli_version_detected": self._detect_cli_version(engine)}
            for engine in self._supported_engines()
        ]

    def get_models(self, engine: str, refresh: bool = False) -> ModelCatalog:
        if not refresh and engine in self._cache:
            return self._cache[engine]

        if engine not in self._supported_engines():
            raise ValueError(f"Unknown engine: {engine}")

        cli_version = self._detect_cli_version(engine)
        manifest = self._load_manifest(engine)
        snapshots = self._extract_snapshots(manifest)
        snapshot_version, fallback_reason = self._select_snapshot_version(
            cli_version,
            [snap["version"] for snap in snapshots]
        )
        snapshot_file = self._snapshot_file(manifest, snapshot_version)
        models = self._load_models(snapshot_file)

        catalog = ModelCatalog(
            engine=engine,
            cli_version_detected=cli_version,
            snapshot_version_used=snapshot_version,
            fallback_reason=fallback_reason,
            models=models
        )
        self._cache[engine] = catalog
        return catalog

    def validate_model(self, engine: str, model_spec: str) -> Dict[str, str]:
        catalog = self.get_models(engine)
        model_name, effort = self._parse_model_spec(engine, model_spec)
        model_entry = self._find_model(catalog.models, model_name)
        if not model_entry:
            raise ValueError(f"Model '{model_name}' not allowed for engine '{engine}'")
        if effort:
            allowed = model_entry.supported_effort or self._default_effort_levels()
            if effort not in allowed:
                raise ValueError(f"Reasoning effort '{effort}' not supported for model '{model_name}'")
        payload = {"model": model_name}
        if effort:
            payload["model_reasoning_effort"] = effort
        return payload

    def _supported_engines(self) -> List[str]:
        return ["codex", "gemini", "iflow"]

    def _load_manifest(self, engine: str) -> Dict[str, object]:
        manifest_path = self._models_root(engine) / "manifest.json"
        if not manifest_path.exists():
            raise ValueError(f"Model manifest not found for engine '{engine}'")
        with open(manifest_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _snapshot_file(self, manifest: Dict[str, object], version: str) -> Path:
        snapshots = self._extract_snapshots(manifest)
        engine = manifest.get("engine")
        if not isinstance(engine, str):
            raise ValueError("Invalid manifest format")
        for snap in snapshots:
            if isinstance(snap, dict) and snap.get("version") == version:
                return self._models_root(engine) / snap["file"]
        raise ValueError(f"Snapshot file not found for version {version}")

    def _models_root(self, engine: str) -> Path:
        return Path(config.SYSTEM.ROOT) / "server" / "assets" / "models" / engine

    def _extract_snapshots(self, manifest: Dict[str, object]) -> List[Dict[str, str]]:
        snapshots = manifest.get("snapshots")
        if not isinstance(snapshots, list):
            raise ValueError("Invalid manifest format")
        normalized: List[Dict[str, str]] = []
        for snap in snapshots:
            if not isinstance(snap, dict):
                raise ValueError("Invalid manifest format")
            version = snap.get("version")
            file = snap.get("file")
            if not isinstance(version, str) or not isinstance(file, str):
                raise ValueError("Invalid manifest format")
            normalized.append({"version": version, "file": file})
        return normalized

    def _load_models(self, path: Path) -> List[ModelEntry]:
        if not path.exists():
            raise ValueError(f"Model snapshot file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            payload = json.load(f)
        models: List[ModelEntry] = []
        for entry in payload.get("models", []):
            models.append(
                ModelEntry(
                    id=entry["id"],
                    display_name=entry.get("display_name"),
                    deprecated=entry.get("deprecated", False),
                    notes=entry.get("notes"),
                    supported_effort=entry.get("supported_effort")
                )
            )
        return models

    def _select_snapshot_version(
        self,
        cli_version: Optional[str],
        snapshot_versions: List[str]
    ) -> Tuple[str, Optional[str]]:
        if not snapshot_versions:
            raise ValueError("No model snapshots available")

        parsed_cli = self._parse_semver(cli_version) if cli_version else None
        candidates: List[str] = []
        if parsed_cli:
            for ver in snapshot_versions:
                parsed = self._parse_semver(ver)
                if parsed and parsed <= parsed_cli:
                    candidates.append(ver)
            if candidates:
                return max(candidates, key=self._semver_key), None
            return max(snapshot_versions, key=self._semver_key), "no_match"

        fallback_reason = "cli_version_unknown" if cli_version is None else "no_semver_match"
        return max(snapshot_versions, key=self._semver_key), fallback_reason

    def _parse_semver(self, version: Optional[str]) -> Optional[Tuple[int, ...]]:
        if not version:
            return None
        match = re.search(r"\d+(\.\d+)+", version)
        if not match:
            return None
        try:
            return tuple(int(part) for part in match.group(0).split("."))
        except ValueError:
            return None

    def _semver_key(self, version: str) -> Tuple[int, ...]:
        parsed = self._parse_semver(version)
        return parsed if parsed is not None else (0,)

    def _detect_cli_version(self, engine: str) -> Optional[str]:
        command_map = {
            "codex": ["codex", "--version"],
            "gemini": ["gemini", "--version"],
            "iflow": ["iflow", "--version"]
        }
        cmd = command_map.get(engine)
        if not cmd:
            return None
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        except FileNotFoundError:
            logger.warning("CLI not found for engine %s", engine)
            return None
        output = (result.stdout or "") + (result.stderr or "")
        return self._extract_version_string(output)

    def _extract_version_string(self, text: str) -> Optional[str]:
        match = re.search(r"\d+(\.\d+)+", text)
        return match.group(0) if match else None

    def _parse_model_spec(self, engine: str, model_spec: str) -> Tuple[str, Optional[str]]:
        if engine != "codex":
            if "@" in model_spec:
                raise ValueError(f"Engine '{engine}' does not support model reasoning suffix")
            return model_spec, None
        if "@" not in model_spec:
            return model_spec, None
        name, effort = model_spec.split("@", 1)
        if not name or not effort:
            raise ValueError("Invalid model specification format")
        return name, effort

    def _find_model(self, models: List[ModelEntry], model_id: str) -> Optional[ModelEntry]:
        for entry in models:
            if entry.id == model_id:
                return entry
        return None

    def _default_effort_levels(self) -> List[str]:
        return ["minimal", "low", "medium", "high", "xhigh"]


model_registry = ModelRegistry()
