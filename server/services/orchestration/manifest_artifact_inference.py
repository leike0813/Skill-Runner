import json
import logging
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def scan_output_schema_artifacts(schema_path: Path) -> List[Dict[str, Any]]:
    """
    Scan output schema properties and infer manifest artifacts from x-type markers.

    Compatible markers:
    - x-type: artifact
    - x-type: file
    """
    artifacts: List[Dict[str, Any]] = []
    if not schema_path.exists():
        return artifacts

    try:
        with open(schema_path, "r", encoding="utf-8") as f:
            schema = json.load(f)

        props = schema.get("properties", {})
        required_keys = set(schema.get("required", []))
        for key, val in props.items():
            x_type = val.get("x-type")
            if x_type not in {"artifact", "file"}:
                continue
            pattern = val.get("x-filename", key)
            role = val.get("x-role", "output")
            artifacts.append(
                {
                    "role": role,
                    "pattern": pattern,
                    "required": key in required_keys,
                }
            )
    except Exception:
        logger.exception("Error scanning output schema artifacts: %s", schema_path)

    return artifacts


def infer_manifest_artifacts(
    manifest_data: Dict[str, Any],
    skill_dir: Path,
) -> Dict[str, Any]:
    """
    Fill manifest artifacts from output schema when artifacts are not explicitly defined.
    """
    data = dict(manifest_data)
    if data.get("artifacts"):
        return data

    schemas = data.get("schemas")
    if not isinstance(schemas, dict):
        return data

    output_rel = schemas.get("output")
    if not isinstance(output_rel, str) or not output_rel.strip():
        return data

    output_schema_path = skill_dir / output_rel
    data["artifacts"] = scan_output_schema_artifacts(output_schema_path)
    return data
