from __future__ import annotations

import re
from pathlib import Path


FORBIDDEN_PATTERNS = (
    re.compile(r'["\']status\.json["\']'),
    re.compile(r'["\']current/projection\.json["\']'),
    re.compile(r'["\']interactions/pending\.json["\']'),
    re.compile(r'["\']interactions/pending_auth\.json["\']'),
    re.compile(r'["\']interactions/pending_auth_method_selection\.json["\']'),
    re.compile(r'["\']interactions/history\.jsonl["\']'),
    re.compile(r'["\']interactions/runtime_state\.json["\']'),
    re.compile(r'["\']logs/stdout\.txt["\']'),
    re.compile(r'["\']logs/stderr\.txt["\']'),
    re.compile(r'["\']raw/output\.json["\']'),
    re.compile(r'["\']input\.json["\']'),
)

ALLOWED_PATHS = {
    "docs/run_artifacts.md",
    "openspec/specs/job-orchestrator-modularization/spec.md",
    "tests/unit/test_runtime_file_contract_scan.py",
}


def _scan_paths(paths: list[Path]) -> list[str]:
    violations: list[str] = []
    repo_root = Path(__file__).resolve().parents[2]
    for path in paths:
        rel = path.relative_to(repo_root).as_posix()
        if rel in ALLOWED_PATHS:
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in FORBIDDEN_PATTERNS:
            if pattern.search(text):
                violations.append(f"{rel}: {pattern.pattern}")
    return violations


def test_runtime_file_contract_scan_blocks_legacy_paths() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    scan_roots = [
        repo_root / "server",
        repo_root / "tests" / "unit",
        repo_root / "tests" / "api_integration",
        repo_root / "tests" / "engine_integration",
        repo_root / "agent_harness",
    ]
    files = [path for root in scan_roots for path in root.rglob("*.py")]
    violations = _scan_paths(files)
    assert not violations, "legacy runtime file contract references found:\n" + "\n".join(violations)
