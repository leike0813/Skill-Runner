import json
from pathlib import Path

from server.engines.opencode.adapter.execution_adapter import OpencodeExecutionAdapter
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
    adapter = OpencodeExecutionAdapter()

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
    adapter = OpencodeExecutionAdapter()

    config_path = adapter._construct_config(
        skill,
        run_dir,
        options={"execution_mode": "interactive"},
    )
    payload = _read_json(config_path)

    assert payload["model"] == "opencode/gpt-5-nano"
    assert payload["permission"]["question"] == "allow"


def test_parse_runtime_stream_keeps_latest_step_only():
    adapter = OpencodeExecutionAdapter()
    parsed = adapter.parse_runtime_stream(
        stdout_raw=(
            b'{"type":"step_start","id":"s1"}\n'
            b'{"type":"text","text":"old step"}\n'
            b'{"type":"step_finish","id":"s1"}\n'
            b'{"type":"step_start","id":"s2"}\n'
            b'{"type":"text","text":"latest step"}\n'
            b'{"type":"step_finish","id":"s2"}\n'
        ),
        stderr_raw=b"",
        pty_raw=b"",
    )
    assert parsed["assistant_messages"]
    assert [msg["text"] for msg in parsed["assistant_messages"]] == ["latest step"]


def test_parse_runtime_stream_emits_turn_markers_and_process_events() -> None:
    adapter = OpencodeExecutionAdapter()
    parsed = adapter.parse_runtime_stream(
        stdout_raw=(
            b'{"type":"step_start","id":"s1","sessionID":"ses-op-1"}\n'
            b'{"type":"tool_use","part":{"type":"tool","id":"p1","tool":"bash","state":{"status":"completed","input":{"command":"echo hi"},"output":"hi"}}}\n'
            b'{"type":"step_finish","id":"s1","part":{"reason":"stop","cost":0,"tokens":{"total":12,"input":9,"output":3}}}\n'
        ),
        stderr_raw=b"",
        pty_raw=b"",
    )
    turn_markers = parsed.get("turn_markers", [])
    assert isinstance(turn_markers, list)
    assert [item.get("marker") for item in turn_markers] == ["start", "complete"]
    run_handle = parsed.get("run_handle")
    assert isinstance(run_handle, dict)
    assert run_handle.get("handle_id") == "ses-op-1"
    process_events = parsed.get("process_events", [])
    assert isinstance(process_events, list) and process_events
    assert process_events[0].get("process_type") == "command_execution"
    assert process_events[0].get("summary") == "echo hi"
    turn_complete_data = parsed.get("turn_complete_data")
    assert isinstance(turn_complete_data, dict)
    assert turn_complete_data.get("cost") == 0
    tokens = turn_complete_data.get("tokens")
    assert isinstance(tokens, dict)
    assert tokens.get("total") == 12
