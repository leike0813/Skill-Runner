from __future__ import annotations

import ast
from pathlib import Path

import yaml  # type: ignore[import-untyped]


def _is_broad_exception_handler(handler: ast.ExceptHandler) -> bool:
    exc_type = handler.type
    return (
        isinstance(exc_type, ast.Name)
        and exc_type.id == "Exception"
    ) or (
        isinstance(exc_type, ast.Attribute)
        and exc_type.attr == "Exception"
    )


def _classify_handler(handler: ast.ExceptHandler) -> str:
    first_stmt = handler.body[0] if handler.body else None
    if isinstance(first_stmt, ast.Pass):
        return "pass"
    if isinstance(first_stmt, (ast.Continue, ast.Break)):
        return "loop_control"
    if isinstance(first_stmt, ast.Return):
        return "return"
    if isinstance(first_stmt, ast.Expr) and isinstance(first_stmt.value, ast.Call):
        fn = first_stmt.value.func
        if (
            isinstance(fn, ast.Attribute)
            and isinstance(fn.value, ast.Name)
            and fn.value.id in {"logger", "logging"}
        ):
            return "log"
    return "other"


def _scan_server_broad_exception_counts(repo_root: Path) -> dict[str, dict[str, int]]:
    results: dict[str, dict[str, int]] = {}
    for py_file in sorted((repo_root / "server").rglob("*.py")):
        source = py_file.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue

        file_counts = {
            "total": 0,
            "pass": 0,
            "loop_control": 0,
            "return": 0,
            "log": 0,
            "other": 0,
        }
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if not _is_broad_exception_handler(node):
                continue
            file_counts["total"] += 1
            file_counts[_classify_handler(node)] += 1

        if file_counts["total"] > 0:
            rel = py_file.relative_to(repo_root).as_posix()
            results[rel] = file_counts
    return results


def test_no_unapproved_broad_exception_usage() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    contract_path = repo_root / "docs" / "contracts" / "exception_handling_allowlist.yaml"
    policy = yaml.safe_load(contract_path.read_text(encoding="utf-8"))

    baseline: dict[str, dict[str, int]] = policy.get("baseline", {})
    baseline_totals: dict[str, int] = policy.get("policy", {}).get("baseline_totals", {})
    actual = _scan_server_broad_exception_counts(repo_root)

    errors: list[str] = []

    # 1) New files with broad catch are forbidden until explicitly allowlisted.
    for path, counts in actual.items():
        if path not in baseline:
            errors.append(f"{path}: broad catch found but not allowlisted (counts={counts})")

    # 2) Existing allowlisted files may only stay the same or decrease by category.
    for path, counts in actual.items():
        allowed = baseline.get(path)
        if not allowed:
            continue
        for key in ("total", "pass", "loop_control", "return", "log", "other"):
            allowed_val = int(allowed.get(key, 0))
            actual_val = int(counts.get(key, 0))
            if actual_val > allowed_val:
                errors.append(
                    f"{path}: {key} broad-catch count {actual_val} exceeds allowlist {allowed_val}"
                )

    # 3) Global totals may only stay the same or decrease.
    global_actual = {
        "total": sum(item["total"] for item in actual.values()),
        "pass": sum(item["pass"] for item in actual.values()),
        "loop_control": sum(item["loop_control"] for item in actual.values()),
        "return": sum(item["return"] for item in actual.values()),
        "log": sum(item["log"] for item in actual.values()),
        "other": sum(item["other"] for item in actual.values()),
    }
    for key, allowed_total in baseline_totals.items():
        actual_total = int(global_actual.get(key, 0))
        if actual_total > int(allowed_total):
            errors.append(
                f"global {key} broad-catch count {actual_total} exceeds baseline {allowed_total}"
            )

    assert not errors, "Broad exception policy violations:\n" + "\n".join(errors)
