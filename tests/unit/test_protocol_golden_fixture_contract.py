from __future__ import annotations

from tests.common.protocol_golden_fixture_contract import (
    fixture_supports_engine,
    list_protocol_golden_fixtures,
    load_protocol_golden_fixture,
    load_protocol_golden_fixture_manifest,
    protocol_golden_fixture_manifest_path,
    protocol_golden_fixture_schema_path,
)


def test_protocol_golden_fixture_contract_paths_exist() -> None:
    assert protocol_golden_fixture_manifest_path().exists()
    assert protocol_golden_fixture_schema_path().exists()


def test_protocol_golden_fixture_manifest_is_loadable_and_ids_are_unique() -> None:
    manifest = load_protocol_golden_fixture_manifest()
    assert manifest["version"] == 1
    fixture_ids = [item["fixture_id"] for item in list_protocol_golden_fixtures()]
    assert len(fixture_ids) == len(set(fixture_ids))


def test_protocol_golden_fixtures_validate_and_align_with_manifest() -> None:
    fixtures = list_protocol_golden_fixtures()
    assert fixtures
    for entry in fixtures:
        fixture = load_protocol_golden_fixture(entry["fixture_id"])
        assert fixture["fixture_id"] == entry["fixture_id"]
        assert fixture["layer"] == entry["layer"]
        assert fixture["engine"] == entry["engine"]
        assert fixture["source"] == entry["source"]
        assert isinstance(fixture["capability_requirements"], list)
        assert isinstance(fixture["expected"], dict)


def test_protocol_golden_fixture_capability_gating_respects_parser_capability_contract() -> None:
    codex_fixture = load_protocol_golden_fixture("codex_turn_failed_protocol_smoke")
    assert fixture_supports_engine(codex_fixture)
    assert fixture_supports_engine(codex_fixture, target_engine="codex") is True
    assert fixture_supports_engine(codex_fixture, target_engine="gemini") is False

    common_fixture = load_protocol_golden_fixture("common_outcome_waiting_auth_smoke")
    assert fixture_supports_engine(common_fixture, target_engine="codex") is True
    assert fixture_supports_engine(common_fixture, target_engine="gemini") is True
