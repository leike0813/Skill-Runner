import json
from pathlib import Path

from server.engines.qwen.adapter.execution_adapter import QwenExecutionAdapter
from server.models import SkillManifest
from server.runtime.adapter.contracts import AdapterExecutionContext


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_qwen_config_composer_merges_default_skill_runtime_and_enforced(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    run_dir.mkdir()
    skill_dir = tmp_path / "skill"
    skill_assets = skill_dir / "assets"
    skill_assets.mkdir(parents=True)
    (skill_assets / "qwen_config.json").write_text(
        json.dumps(
            {
                "model": {"name": "qwen3.6-plus"},
                "env": {"SOURCE": "skill"},
                "tools": {"sandbox": True},
            }
        ),
        encoding="utf-8",
    )

    adapter = QwenExecutionAdapter()
    ctx = AdapterExecutionContext(
        skill=SkillManifest(id="test-skill", path=skill_dir),
        run_dir=run_dir,
        input_data={},
        options={
            "model": "qwen3-coder-plus",
            "qwen_config": {
                "env": {"SOURCE": "runtime", "EXTRA": "runtime"},
                "tools": {"sandbox": True},
                "permissions": {"defaultMode": "custom"},
            },
        },
    )

    assert adapter.config_composer is not None
    config_path = adapter.config_composer.compose(ctx)
    payload = _read_json(config_path)

    assert payload["model"]["name"] == "qwen3-coder-plus"
    assert payload["env"]["SOURCE"] == "runtime"
    assert payload["env"]["EXTRA"] == "runtime"
    assert payload["output"]["format"] == "stream-json"
    assert payload["tools"]["approvalMode"] == "yolo"
    assert payload["tools"]["sandbox"] is False
    assert payload["permissions"]["defaultMode"] == "bypassPermissions"


def test_qwen_parse_runtime_stream_detects_oauth_waiting_from_stderr_banner() -> None:
    adapter = QwenExecutionAdapter()
    stderr_banner = (
        "╭──────────────────────────────╮\n"
        "│ Qwen OAuth Device Authorization │\n"
        "╰──────────────────────────────╯\n"
        "Open this URL in your browser:\n"
        "https://chat.qwen.ai/authorize?user_code=TEST-123\n"
        "Waiting for authorization to complete...\n"
    ).encode("utf-8")

    result = adapter.parse_runtime_stream(
        stdout_raw=b"",
        stderr_raw=stderr_banner,
        pty_raw=b"",
    )

    assert result["parser"] == "qwen_ndjson"
    assert result["assistant_messages"] == []
    assert result["turn_started"] is False
    assert result["turn_completed"] is False
    assert result["turn_markers"] == []
    assert result["auth_signal"] == {
        "required": True,
        "confidence": "high",
        "subcategory": None,
        "provider_id": None,
        "reason_code": "QWEN_OAUTH_WAITING_AUTHORIZATION",
        "matched_pattern_id": "qwen_oauth_waiting_authorization",
    }


def test_qwen_live_session_remains_stdout_pty_ndjson_only() -> None:
    adapter = QwenExecutionAdapter()
    assert adapter.stream_parser is not None
    session = adapter.stream_parser.start_live_session()
    stderr_banner = (
        "Qwen OAuth Device Authorization\n"
        "https://chat.qwen.ai/authorize?user_code=TEST-123\n"
        "Waiting for authorization to complete...\n"
    )

    emissions = session.feed(
        stream="stderr",
        text=stderr_banner,
        byte_from=0,
        byte_to=len(stderr_banner.encode("utf-8")),
    )

    assert emissions == []


def test_qwen_parse_runtime_stream_extracts_run_handle_process_events_and_turn_markers() -> None:
    adapter = QwenExecutionAdapter()
    stdout_raw = (
        b'{"type":"system","subtype":"init","session_id":"session-qwen-live"}\n'
        b'{"type":"assistant","message":{"id":"msg-think","content":[{"type":"thinking","thinking":"draft plan"}]}}\n'
        b'{"type":"assistant","message":{"id":"msg-skill","content":[{"type":"tool_use","id":"toolu_skill","name":"skill","input":{"skill":"literature-digest"}}]}}\n'
        b'{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"toolu_skill","content":"Launching skill","is_error":false}]}}\n'
        b'{"type":"assistant","message":{"id":"msg-bash","content":[{"type":"tool_use","id":"toolu_bash","name":"run_shell_command","input":{"command":"pwd","description":"Print cwd"}}]}}\n'
        b'{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"toolu_bash","content":"/tmp/run","is_error":false}]}}\n'
        b'{"type":"assistant","message":{"id":"msg-text","content":[{"type":"text","text":"Preparing final payload"}]}}\n'
        b'{"type":"result","subtype":"success","session_id":"session-qwen-live","usage":{"input_tokens":12},"result":"{\\"ok\\": true}"}\n'
    )

    parsed = adapter.parse_runtime_stream(stdout_raw=stdout_raw, stderr_raw=b"")

    assert parsed["parser"] == "qwen_ndjson"
    assert parsed["session_id"] == "session-qwen-live"
    assert parsed["run_handle"]["handle_id"] == "session-qwen-live"
    run_handle = parsed["run_handle"]
    raw_ref = run_handle.get("raw_ref")
    assert isinstance(raw_ref, dict)
    assert raw_ref["stream"] == "stdout"
    assert parsed["turn_started"] is True
    assert parsed["turn_completed"] is True
    assert [item["marker"] for item in parsed["turn_markers"]] == ["start", "complete"]
    assert parsed["turn_complete_data"]["usage"]["input_tokens"] == 12
    assert parsed["turn_complete_data"]["result_subtype"] == "success"
    assert [item["text"] for item in parsed["assistant_messages"]] == [
        "Preparing final payload",
        '{"ok": true}',
    ]

    process_events = parsed["process_events"]
    assert [item["classification"] for item in process_events] == [
        "reasoning",
        "tool_call",
        "tool_call",
        "command_execution",
        "command_execution",
    ]
    assert process_events[0]["text"] == "draft plan"
    assert process_events[1]["summary"] == "literature-digest"
    assert process_events[2]["details"]["item_type"] == "tool_result"
    assert process_events[3]["summary"] == "pwd"
    assert process_events[4]["details"]["is_error"] is False
    assert parsed["raw_rows"] == []


def test_qwen_live_session_emits_process_events_and_dedupes_final_result_text() -> None:
    adapter = QwenExecutionAdapter()
    assert adapter.stream_parser is not None
    session = adapter.stream_parser.start_live_session()
    payload = (
        '{"type":"system","subtype":"init","session_id":"session-qwen-live"}\n'
        '{"type":"assistant","message":{"id":"msg-think","content":[{"type":"thinking","thinking":"draft plan"}]}}\n'
        '{"type":"assistant","message":{"id":"msg-bash","content":[{"type":"tool_use","id":"toolu_bash","name":"run_shell_command","input":{"command":"pwd"}}]}}\n'
        '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"toolu_bash","content":"/tmp/run","is_error":false}]}}\n'
        '{"type":"assistant","message":{"id":"msg-final","content":[{"type":"text","text":"{\\"ok\\": true}"}]}}\n'
        '{"type":"result","subtype":"success","session_id":"session-qwen-live","usage":{"input_tokens":4},"result":"{\\"ok\\": true}"}\n'
    )

    emissions = session.feed(
        stream="stdout",
        text=payload,
        byte_from=0,
        byte_to=len(payload.encode("utf-8")),
    )

    assert [item["kind"] for item in emissions].count("run_handle") == 1
    assert [item["kind"] for item in emissions].count("turn_completed") == 1
    assert [
        item["process_type"]
        for item in emissions
        if item["kind"] == "process_event"
    ] == ["reasoning", "command_execution", "command_execution"]
    assistant_texts = [
        item["text"]
        for item in emissions
        if item["kind"] == "assistant_message"
    ]
    assert assistant_texts == ['{"ok": true}']
