from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def sha256_file(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(chunk)
    return f"sha256:{sha.hexdigest()}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate provenance for literature_digest_v1.")
    parser.add_argument("--md-path", required=True, help="Path to the MinerU Markdown file.")
    args = parser.parse_args()

    md_path = Path(args.md_path)

    out: dict[str, object] = {"generated_at": utc_now_iso(), "input_hash": ""}
    if not md_path.exists():
        out["error"] = {"code": "FILE_NOT_FOUND", "message": f"md_path not found: {md_path}"}
        print(json.dumps(out, ensure_ascii=False))
        return 2

    try:
        out["input_hash"] = sha256_file(md_path)
        out["error"] = None
        print(json.dumps(out, ensure_ascii=False))
        return 0
    except Exception as e:  # noqa: BLE001
        out["error"] = {"code": "HASH_FAILED", "message": str(e)}
        print(json.dumps(out, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

