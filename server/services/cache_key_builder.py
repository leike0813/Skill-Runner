import hashlib
import json
from pathlib import Path
from typing import Dict, Any, List

from ..models import SkillManifest


def _stable_json_dumps(data: Any) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"))


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _hash_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def build_input_manifest(uploads_dir: Path) -> Dict[str, Any]:
    files: List[Dict[str, Any]] = []
    if uploads_dir.exists():
        for path in sorted(uploads_dir.rglob("*")):
            if not path.is_file():
                continue
            rel_path = path.relative_to(uploads_dir).as_posix()
            files.append({
                "path": rel_path,
                "sha256": _hash_file(path),
                "size": path.stat().st_size
            })
    return {"files": files}


def compute_input_manifest_hash(manifest: Dict[str, Any]) -> str:
    return _hash_text(_stable_json_dumps(manifest))


def compute_inline_input_hash(input_payload: Dict[str, Any]) -> str:
    if not input_payload:
        return ""
    return _hash_text(_stable_json_dumps(input_payload))


def compute_skill_fingerprint(skill: SkillManifest, engine: str) -> str:
    if not skill.path:
        return ""

    files: List[Path] = []
    skill_md = skill.path / "SKILL.md"
    runner_json = skill.path / "assets" / "runner.json"

    if skill_md.exists():
        files.append(skill_md)
    if runner_json.exists():
        files.append(runner_json)

    if skill.schemas:
        for rel in skill.schemas.values():
            schema_path = skill.path / rel
            if schema_path.exists():
                files.append(schema_path)

    if engine == "gemini":
        engine_cfg = skill.path / "assets" / "gemini_settings.json"
    elif engine == "iflow":
        engine_cfg = skill.path / "assets" / "iflow_settings.json"
    else:
        engine_cfg = skill.path / "assets" / "codex_config.toml"

    if engine_cfg.exists():
        files.append(engine_cfg)

    entries = []
    for path in sorted({p.resolve() for p in files}):
        entries.append(f"{path.name}:{_hash_file(path)}")

    return _hash_text("\n".join(entries))


def compute_cache_key(
    skill_id: str,
    engine: str,
    skill_fingerprint: str,
    parameter: Dict[str, Any],
    engine_options: Dict[str, Any],
    input_manifest_hash: str,
    inline_input_hash: str = "",
) -> str:
    payload = {
        "skill_id": skill_id,
        "engine": engine,
        "skill_fingerprint": skill_fingerprint,
        "parameter": parameter,
        "engine_options": engine_options,
        "input_manifest_hash": input_manifest_hash,
        "inline_input_hash": inline_input_hash,
    }
    return _hash_text(_stable_json_dumps(payload))
