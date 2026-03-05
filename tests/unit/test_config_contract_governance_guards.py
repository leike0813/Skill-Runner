from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]

FORBIDDEN_PATH_SNIPPETS = (
    "server/assets/configs/concurrency_policy.json",
    "server/assets/configs/engine_command_profiles.json",
    "server/assets/configs/engine_auth_strategy.yaml",
    "server/assets/configs/options_policy.json",
    "server/assets/configs/system_settings.bootstrap.json",
    "server/assets/schemas/protocol/runtime_contract.schema.json",
    "server/assets/schemas/adapter_profile_schema.json",
    "server/assets/schemas/engine_auth/engine_auth_strategy.schema.json",
    "server/assets/schemas/",
    "server/assets/auth_detection/",
    "server/assets/models/",
    "server/assets/configs/",
    "docs/contracts/",
)


def _scan_text_files() -> list[Path]:
    roots = [REPO_ROOT / "server", REPO_ROOT / "tests", REPO_ROOT / "docs"]
    files: list[Path] = []
    for root in roots:
        for path in root.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".md", ".yaml", ".yml", ".json"}:
                files.append(path)
    return files


def test_no_legacy_config_or_contract_path_references() -> None:
    violations: list[str] = []
    for path in _scan_text_files():
        rel = path.relative_to(REPO_ROOT).as_posix()
        # This test file intentionally contains legacy snippets as guard data.
        if rel == "tests/unit/test_config_contract_governance_guards.py":
            continue
        text = path.read_text(encoding="utf-8")
        for snippet in FORBIDDEN_PATH_SNIPPETS:
            if snippet in text:
                violations.append(f"{rel}: {snippet}")
    assert not violations, "legacy config/contract references found:\n" + "\n".join(violations)


def test_server_code_reads_contracts_via_registry_layer() -> None:
    violations: list[str] = []
    for path in (REPO_ROOT / "server").rglob("*.py"):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel.startswith("server/config_registry/"):
            continue
        text = path.read_text(encoding="utf-8")
        if "server/contracts" in text and ("read_text(" in text or "open(" in text):
            violations.append(rel)
    assert (
        not violations
    ), "direct contract file reads detected; use server.config_registry registry/loaders:\n" + "\n".join(
        violations
    )
