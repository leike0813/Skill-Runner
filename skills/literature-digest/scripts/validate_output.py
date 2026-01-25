from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


DIGEST_FILENAME = "digest.md"
REFERENCES_FILENAME = "references.json"


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(chunk)
    return f"sha256:{sha.hexdigest()}"


def _is_utc_iso8601_z(value: object) -> bool:
    if not isinstance(value, str):
        return False
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", value))


def _as_str_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value if v is not None]
    if isinstance(value, str):
        return [value]
    return [str(value)]


def _as_int_or_none(value: object) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isfinite(value) and value.is_integer():
            return int(value)
        return None
    if isinstance(value, str):
        s = value.strip()
        if re.fullmatch(r"(19|20)\d{2}", s):
            return int(s)
        return None
    return None


def _as_confidence(value: object, default: float = 0.1) -> float:
    if value is None or isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        f = float(value)
        if not math.isfinite(f):
            return default
        return float(min(1.0, max(0.0, f)))
    if isinstance(value, str):
        try:
            f = float(value.strip())
            if not math.isfinite(f):
                return default
            return float(min(1.0, max(0.0, f)))
        except ValueError:
            return default
    return default


def _ensure_dict(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _resolve_output_root(explicit_out_dir: Path | None, md_path: Path | None) -> Path:
    # Strategy (to avoid sandbox escapes in some agents):
    # 1) Use the input md_path directory (preferred, if available)
    # 2) Explicit CLI --out-dir
    # 3) Env var LITERATURE_DIGEST_OUTPUT_DIR (plugin can set)
    # 4) OS temp dir
    if md_path is not None:
        return md_path.parent
    if explicit_out_dir is not None:
        return explicit_out_dir
    env = os.environ.get("LITERATURE_DIGEST_OUTPUT_DIR")
    if env:
        return Path(env).expanduser()
    # Last resort fallback (should be avoided when md_path is available).
    return Path.cwd()


def _normalize_reference_item(item: object, *, fix: bool, warnings: list[str]) -> dict[str, Any]:
    if isinstance(item, str):
        if not fix:
            return {}
        return {"raw": item}
    if not isinstance(item, dict):
        return {}

    out: dict[str, Any] = dict(item)

    if "doi" in out and "DOI" not in out and fix:
        out["DOI"] = out.pop("doi")
        warnings.append("references: migrated field 'doi' -> 'DOI'")

    if fix:
        out.setdefault("author", [])
        out.setdefault("title", "")
        out.setdefault("year", None)
        out.setdefault("raw", "")
        out.setdefault("confidence", 0.1)

    out["author"] = _as_str_list(out.get("author"))
    out["title"] = "" if out.get("title") is None else str(out.get("title"))
    out["year"] = _as_int_or_none(out.get("year"))
    out["raw"] = "" if out.get("raw") is None else str(out.get("raw"))
    out["confidence"] = _as_confidence(out.get("confidence"), default=0.1)

    creators = out.get("creators")
    if creators is not None and not isinstance(creators, list) and fix:
        out["creators"] = []
        warnings.append("references: coerced non-list 'creators' to []")

    return out


def _materialize_outputs(
    out: dict[str, Any],
    *,
    fix: bool,
    warnings: list[str],
    output_root: Path,
) -> None:
    if not fix:
        return

    digest_content: str | None = None
    if "digest_path" not in out or not out.get("digest_path"):
        if isinstance(out.get("digest"), str):
            digest_content = out["digest"]
            warnings.append("digest: materialized to digest_path")
        elif isinstance(out.get("digest"), dict) and "md" in out["digest"]:
            digest_content = "" if out["digest"]["md"] is None else str(out["digest"]["md"])
            warnings.append("digest: migrated object {md} and materialized to digest_path")
        elif "digest.md" in out:
            digest_content = "" if out["digest.md"] is None else str(out["digest.md"])
            warnings.append("digest: migrated field 'digest.md' and materialized to digest_path")

    references_items: list[object] | None = None
    if "references_path" not in out or not out.get("references_path"):
        if isinstance(out.get("references"), list):
            references_items = out["references"]
            warnings.append("references: materialized to references_path")
        elif isinstance(out.get("references"), dict) and "items" in out["references"]:
            references_items = out["references"]["items"]
            warnings.append("references: migrated object {items} and materialized to references_path")
        elif "references.items" in out:
            references_items = out["references.items"]
            warnings.append("references: migrated field 'references.items' and materialized to references_path")

    if digest_content is None and references_items is None:
        return

    output_root.mkdir(parents=True, exist_ok=True)
    if digest_content is not None:
        digest_file = output_root / DIGEST_FILENAME
        _write_text(digest_file, digest_content)
        out["digest_path"] = str(digest_file)
        out.pop("digest", None)
        out.pop("digest.md", None)

    if references_items is not None:
        normalized_items: list[dict[str, Any]] = []
        if isinstance(references_items, list):
            for item in references_items:
                normalized_items.append(_normalize_reference_item(item, fix=True, warnings=warnings))
        refs_file = output_root / REFERENCES_FILENAME
        _write_json(refs_file, normalized_items)
        out["references_path"] = str(refs_file)
        out.pop("references", None)
        out.pop("references.items", None)


def _normalize_top_level(
    obj: object,
    *,
    fix: bool,
    md_path: Path | None,
    output_root: Path,
) -> tuple[dict[str, Any], list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []

    if not isinstance(obj, dict):
        if not fix:
            return {}, warnings, ["output is not a JSON object"]
        obj = {}
        errors.append("output is not a JSON object; replaced with empty object")

    out: dict[str, Any] = dict(obj)

    if fix:
        out.setdefault("provenance", {"generated_at": "", "input_hash": ""})
        out.setdefault("warnings", [])
        out.setdefault("error", None)

        _materialize_outputs(out, fix=True, warnings=warnings, output_root=output_root)

        out.setdefault("digest_path", "")
        out.setdefault("references_path", "")

    for required_key in [
        "digest_path",
        "references_path",
        "provenance",
        "warnings",
        "error",
    ]:
        if required_key not in out:
            errors.append(f"missing required key: {required_key}")

    if not isinstance(out.get("digest_path"), str):
        errors.append("digest_path must be string")
        if fix:
            out["digest_path"] = "" if out.get("digest_path") is None else str(out.get("digest_path"))
            warnings.append("digest_path coerced to string")

    if not isinstance(out.get("references_path"), str):
        errors.append("references_path must be string")
        if fix:
            out["references_path"] = "" if out.get("references_path") is None else str(out.get("references_path"))
            warnings.append("references_path coerced to string")

    prov = _ensure_dict(out.get("provenance"))
    if fix:
        prov.setdefault("generated_at", "")
        prov.setdefault("input_hash", "")
    out["provenance"] = prov

    if not _is_utc_iso8601_z(prov.get("generated_at")):
        errors.append("provenance.generated_at must be UTC ISO-8601 (YYYY-MM-DDTHH:MM:SSZ)")
        if fix:
            prov["generated_at"] = utc_now_iso()
            warnings.append("provenance.generated_at regenerated")

    input_hash = prov.get("input_hash")
    if not isinstance(input_hash, str) or (input_hash and not input_hash.startswith("sha256:")):
        errors.append("provenance.input_hash must be 'sha256:<hex>' or ''")
        if fix:
            prov["input_hash"] = ""
            warnings.append("provenance.input_hash reset to ''")

    if fix and md_path is not None and prov.get("input_hash") in ("", None):
        try:
            prov["input_hash"] = sha256_file(md_path)
            warnings.append("provenance.input_hash computed from md_path")
        except Exception as e:  # noqa: BLE001
            warnings.append(f"provenance.input_hash compute failed: {e}")

    warnings_val = out.get("warnings")
    if not isinstance(warnings_val, list):
        errors.append("warnings must be array")
        if fix:
            out["warnings"] = _as_str_list(warnings_val)
            warnings.append("warnings coerced to array")

    error_val = out.get("error")
    if error_val is not None and not isinstance(error_val, dict):
        errors.append("error must be object or null")
        if fix:
            out["error"] = {"code": "INVALID_ERROR_FIELD", "message": "error was not object/null"}
            warnings.append("error replaced with object")

    if fix:
        out["warnings"] = _as_str_list(out.get("warnings")) + warnings

    # When fixing, ensure materialized files exist if paths are set.
    if fix and isinstance(out.get("digest_path"), str) and out["digest_path"]:
        if not Path(out["digest_path"]).exists():
            errors.append("digest_path does not exist")
    if fix and isinstance(out.get("references_path"), str) and out["references_path"]:
        rp = Path(out["references_path"])
        if not rp.exists():
            errors.append("references_path does not exist")
        else:
            try:
                refs = json.loads(rp.read_text(encoding="utf-8"))
                if not isinstance(refs, list):
                    errors.append("references_path must contain a JSON array")
            except Exception as e:  # noqa: BLE001
                errors.append(f"references_path unreadable JSON: {e}")

    return out, warnings, errors


def _load_input(path: Path | None) -> object:
    if path is None:
        data = sys.stdin.read()
        return json.loads(data) if data.strip() else {}
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate/fix literature-digest output JSON (file-based outputs).")
    parser.add_argument("--mode", choices=["check", "fix"], default="check")
    parser.add_argument("--in", dest="in_path", default=None, help="Input JSON file path (default: stdin)")
    parser.add_argument("--md-path", default=None, help="Optional md_path to compute provenance.input_hash")
    parser.add_argument("--out-dir", default=None, help="Directory to write digest/references files (fix mode only)")
    args = parser.parse_args()

    in_path = Path(args.in_path) if args.in_path else None
    md_path = Path(args.md_path) if args.md_path else None
    if md_path is not None and not md_path.exists():
        md_path = None

    out_dir = Path(args.out_dir).expanduser() if args.out_dir else None
    output_root = _resolve_output_root(out_dir, md_path)

    obj = _load_input(in_path)

    if args.mode == "check":
        _, _, errors = _normalize_top_level(obj, fix=False, md_path=None, output_root=output_root)
        report = {"ok": len(errors) == 0, "errors": errors}
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report["ok"] else 2

    fixed, _, _ = _normalize_top_level(obj, fix=True, md_path=md_path, output_root=output_root)
    _, _, post_errors = _normalize_top_level(fixed, fix=False, md_path=None, output_root=output_root)
    if post_errors:
        fixed.setdefault("warnings", [])
        fixed["warnings"] = _as_str_list(fixed["warnings"]) + [f"validate_output: still invalid: {e}" for e in post_errors]
        print(json.dumps(fixed, ensure_ascii=False))
        return 2

    print(json.dumps(fixed, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
