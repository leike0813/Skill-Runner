import json
from pathlib import Path

from server.adapters.opencode_adapter import OpencodeAdapter
from server.models import SkillManifest


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_construct_config_auto_mode_uses_engine_default_and_enforced(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    skill_dir = tmp_path / "skill"
    skill_assets = skill_dir / "assets"
    skill_assets.mkdir(parents=True)
    (skill_assets / "opencode_config.json").write_text(
        json.dumps(
            {
                "model": "anthropic/claude-sonnet-4.5",
                "permission": {"read": "deny", "question": "allow"},
                "skill_setting": "from-skill",
            }
        ),
        encoding="utf-8",
    )
    skill = SkillManifest(id="test-skill", path=skill_dir)
    adapter = OpencodeAdapter()

    config_path = adapter._construct_config(
        skill,
        run_dir,
        options={
            "execution_mode": "auto",
            "opencode_config": {
                "permission": {"skill": "deny"},
                "skill_setting": "from-runtime",
            },
        },
    )
    payload = _read_json(config_path)

    assert payload["model"] == "anthropic/claude-sonnet-4.5"
    assert payload["skill_setting"] == "from-runtime"
    assert payload["permission"]["question"] == "deny"
    assert payload["permission"]["external_directory"] == "deny"
    assert payload["permission"]["read"] == "allow"
    assert payload["permission"]["skill"] == "allow"


def test_construct_config_interactive_mode_sets_question_allow(tmp_path):
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    skill = SkillManifest(id="test-skill", path=tmp_path)
    adapter = OpencodeAdapter()

    config_path = adapter._construct_config(
        skill,
        run_dir,
        options={"execution_mode": "interactive"},
    )
    payload = _read_json(config_path)

    assert payload["model"] == "opencode/gpt-5-nano"
    assert payload["permission"]["question"] == "allow"
