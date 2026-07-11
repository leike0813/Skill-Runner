from __future__ import annotations

import json
from pathlib import Path

import jsonschema


def test_codebuddy_release_gate_matches_schema() -> None:
    schema = json.loads(
        Path("server/engines/codebuddy/schemas/release_gate.schema.json").read_text(encoding="utf-8")
    )
    gate = json.loads(Path("artifacts/codebuddy_release_gate.json").read_text(encoding="utf-8"))
    jsonschema.validate(gate, schema)
    for row in gate["providers"].values():
        assert row["status"] == "passed"
        assert set(row["checks"].values()) == {"passed"}
        assert row["checked_at"]
        assert row["evidence"]


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
