#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import stat
import sys
from pathlib import Path


PATTERNS = {
    "bearer": re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]+"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    "token_key": re.compile(r'(?i)["\']?(?:access_token|auth_token|api_key)["\']?\s*[:=]\s*["\']?[^\s,"\']+'),
}


def _load_secrets(path: Path | None) -> tuple[str, ...]:
    if path is None:
        return ()
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
        raise ValueError("secret file must have mode 0600")
    return tuple(line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip())


def _iter_files(paths: list[Path]):
    for path in paths:
        if not path.exists():
            raise FileNotFoundError(f"artifact path does not exist: {path}")
        if path.is_file():
            yield path
        elif path.is_dir():
            yield from (item for item in path.rglob("*") if item.is_file())
        else:
            raise OSError(f"artifact path is not readable: {path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fail closed when CodeBuddy secrets appear in runtime artifacts")
    parser.add_argument("paths", nargs="+", type=Path)
    parser.add_argument("--secret-file", type=Path)
    parser.add_argument("--allowed-vault", type=Path)
    args = parser.parse_args()
    try:
        secrets = _load_secrets(args.secret_file)
        allowed_vault = args.allowed_vault.resolve() if args.allowed_vault else None
        findings: list[tuple[Path, str]] = []
        for path in _iter_files(args.paths):
            resolved = path.resolve()
            if allowed_vault is not None and resolved == allowed_vault:
                continue
            text = path.read_text(encoding="utf-8", errors="replace")
            for secret in secrets:
                if secret in text:
                    findings.append((path, "exact_secret"))
                    break
            for name, pattern in PATTERNS.items():
                if pattern.search(text):
                    findings.append((path, name))
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"CodeBuddy secret scan failed: {exc}", file=sys.stderr)
        return 2
    for path, rule in sorted(set(findings)):
        print(f"{path}\t{rule}")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
