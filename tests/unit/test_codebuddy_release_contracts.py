from __future__ import annotations

import json
from pathlib import Path

import jsonschema


def test_codebuddy_release_gate_schema_accepts_representative_payload() -> None:
    schema = json.loads(
        Path("server/engines/codebuddy/schemas/release_gate.schema.json").read_text(encoding="utf-8")
    )
    checks = {
        "login": "not_run",
        "model_visibility": "not_run",
        "first_run": "not_run",
        "exact_resume": "not_run",
        "automatic_auth_recovery": "not_run",
        "clear_credential": "not_run",
        "provider_isolation": "not_run",
        "inline_tui": "not_run",
        "secret_scan": "not_run",
    }
    gate = {
        "version": 2,
        "engine": "codebuddy",
        "providers": {
            provider: {
                "status": "not_run",
                "checked_at": None,
                "cli_version": None,
                "checks": checks,
                "evidence": [],
            }
            for provider in ("codebuddy-cn", "codebuddy-global")
        },
    }

    jsonschema.validate(gate, schema)


def test_codebuddy_specific_contracts_stay_inside_engine_boundary() -> None:
    global_schemas = Path("server/contracts/schemas")

    assert not list(global_schemas.glob("codebuddy*.schema.json"))
    assert Path("server/engines/codebuddy/models/manifest.json").is_file()
    assert Path("server/engines/codebuddy/models/models_0.0.0.json").is_file()
    assert not Path("server/engines/codebuddy/models/catalog_service.py").exists()


def test_compose_bootstrap_defaults_match_global_contract() -> None:
    for path in (Path("docker-compose.yml"), Path("docker-compose.release.tmpl.yml")):
        text = path.read_text(encoding="utf-8")
        assert "SKILL_RUNNER_BOOTSTRAP_ENGINES: opencode,codex" in text
