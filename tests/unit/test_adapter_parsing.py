import json
from pathlib import Path

from server.engines.claude.adapter.execution_adapter import ClaudeExecutionAdapter
from server.engines.gemini.adapter.execution_adapter import GeminiExecutionAdapter
from server.engines.codex.adapter.execution_adapter import CodexExecutionAdapter
from server.engines.iflow.adapter.execution_adapter import IFlowExecutionAdapter
from server.engines.opencode.adapter.execution_adapter import OpencodeExecutionAdapter
from server.models import EngineSessionHandle, EngineSessionHandleType
from server.models import AdapterTurnOutcome


def test_gemini_parse_output_from_envelope():
    adapter = GeminiExecutionAdapter()
    raw = json.dumps({"response": "```json\n{\"a\": 1}\n```"})
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"a": 1}
    assert result.repair_level == "deterministic_generic"


def test_gemini_parse_output_from_text():
    adapter = GeminiExecutionAdapter()
    raw = "prefix {\"x\": 2} suffix"
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"x": 2}
    assert result.repair_level == "deterministic_generic"


def test_codex_parse_output_from_stream_event():
    adapter = CodexExecutionAdapter()
    event = {
        "type": "item.completed",
        "item": {"type": "agent_message", "text": "```json\n{\"ok\": true}\n```"}
    }
    raw = json.dumps(event)
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"ok": True}
    assert result.repair_level == "deterministic_generic"


def test_codex_parse_output_from_raw_text():
    adapter = CodexExecutionAdapter()
    raw = "noise {\"done\": true} tail"
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"done": True}
    assert result.repair_level == "deterministic_generic"


def test_iflow_parse_output_from_code_fence():
    adapter = IFlowExecutionAdapter()
    raw = "```json\n{\"value\": 2}\n```"
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"value": 2}
    assert result.repair_level == "deterministic_generic"


def test_iflow_parse_output_from_raw_text():
    adapter = IFlowExecutionAdapter()
    raw = "start {\"v\": 3} end"
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"v": 3}
    assert result.repair_level == "deterministic_generic"


def test_gemini_parse_output_strict_json_without_repair():
    adapter = GeminiExecutionAdapter()
    raw = "{\"ok\": true}"
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"ok": True}
    assert result.repair_level == "none"


def test_opencode_parse_output_from_stream_text_event():
    adapter = OpencodeExecutionAdapter()
    raw = '{"type":"text","part":{"text":"```json\\n{\\"ok\\": true}\\n```"}}\n'
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"ok": True}
    assert result.repair_level == "deterministic_generic"


def test_claude_parse_output_from_stream_result_event():
    adapter = ClaudeExecutionAdapter()
    raw = json.dumps(
        {
            "type": "result",
            "subtype": "success",
            "session_id": "claude-session-1",
            "structured_output": {"ok": True},
            "result": "{\"ok\": true}",
        }
    )
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"ok": True}
    assert result.repair_level == "none"


def test_claude_build_start_command_uses_stream_json_flags(monkeypatch):
    adapter = ClaudeExecutionAdapter()
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/claude"))

    command = adapter.build_start_command(
        prompt="hello",
        options={"model": "claude-sonnet-4-6", "model_reasoning_effort": "high"},
    )

    assert command == [
        str(Path("/usr/bin/claude")),
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "--effort",
        "high",
        "hello",
    ]


def test_claude_runtime_stream_detects_not_logged_in_auth_signal():
    adapter = ClaudeExecutionAdapter()
    parsed = adapter.parse_runtime_stream(
        stdout_raw=b"",
        stderr_raw=b"Not logged in. Run claude auth login to authenticate.\n",
    )

    auth_signal = parsed.get("auth_signal")
    assert isinstance(auth_signal, dict)
    assert auth_signal.get("required") is True
    assert auth_signal.get("confidence") == "high"


def test_claude_runtime_stream_detects_not_logged_in_auth_signal_from_ndjson_login_prompt():
    adapter = ClaudeExecutionAdapter()
    stdout_raw = (
        b'{"type":"system","subtype":"init","session_id":"598c65f0-e19e-4934-9a19-ccba33cab8aa"}\n'
        b'{"type":"assistant","message":{"id":"6855d0ed-b48c-4fab-8311-cb2549387d8b","content":[{"type":"text","text":"Not logged in \\u00b7 Please run /login"}]},"session_id":"598c65f0-e19e-4934-9a19-ccba33cab8aa","error":"authentication_failed"}\n'
        b'{"type":"result","subtype":"success","is_error":true,"session_id":"598c65f0-e19e-4934-9a19-ccba33cab8aa","result":"Not logged in \\u00b7 Please run /login"}\n'
    )
    parsed = adapter.parse_runtime_stream(
        stdout_raw=stdout_raw,
        stderr_raw=b"",
    )

    auth_signal = parsed.get("auth_signal")
    assert isinstance(auth_signal, dict)
    assert auth_signal.get("required") is True
    assert auth_signal.get("confidence") == "high"
    assert auth_signal.get("matched_pattern_id") == "claude_not_logged_in"


def test_claude_runtime_stream_extracts_run_handle_and_semantic_process_events():
    adapter = ClaudeExecutionAdapter()
    parsed = adapter.parse_runtime_stream(
        stdout_raw=(
            b'{"type":"system","subtype":"init","session_id":"e46bbf28-de7c-4ec1-9c9f-6fb45495268e"}\n'
            b'{"type":"assistant","message":{"content":[{"type":"thinking","thinking":"hidden"},{"type":"text","text":"starting"},{"name":"Skill","input":{"skill":"literature-digest"},"id":"toolu_skill","type":"tool_use"}]}}\n'
            b'{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"toolu_skill","content":"Launching skill: literature-digest"}]},"tool_use_result":{"success":true,"commandName":"literature-digest"}}\n'
            b'{"type":"assistant","message":{"content":[{"name":"Bash","input":{"command":"pwd","description":"Print cwd"},"id":"toolu_bash","type":"tool_use"}]}}\n'
            b'{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"toolu_bash","content":"/tmp/run","is_error":false}]},"tool_use_result":{"stdout":"/tmp/run","stderr":"","interrupted":false,"isImage":false,"noOutputExpected":false}}\n'
            b'{"type":"assistant","message":{"content":[{"name":"Bash","input":{"command":"python missing.py","description":"Failing command"},"id":"toolu_fail","type":"tool_use"}]}}\n'
            b'{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"toolu_fail","content":"Exit code 2\\\\npython: can\'t open file","is_error":true}]},"tool_use_result":"Error: Exit code 2"}\n'
            b'{"type":"result","subtype":"success","session_id":"e46bbf28-de7c-4ec1-9c9f-6fb45495268e","usage":{"input_tokens":12},"result":"{\\"ok\\": true}","structured_output":{"ok":true}}\n'
        ),
        stderr_raw=b"",
    )

    assert parsed["session_id"] == "e46bbf28-de7c-4ec1-9c9f-6fb45495268e"
    run_handle = parsed.get("run_handle")
    assert isinstance(run_handle, dict)
    assert run_handle.get("handle_id") == "e46bbf28-de7c-4ec1-9c9f-6fb45495268e"

    messages = parsed.get("assistant_messages")
    assert isinstance(messages, list)
    assert [item["text"] for item in messages] == ["starting", '{"ok": true}']

    turn_markers = parsed.get("turn_markers")
    assert isinstance(turn_markers, list)
    assert [item.get("marker") for item in turn_markers] == ["start", "complete"]

    turn_complete_data = parsed.get("turn_complete_data")
    assert isinstance(turn_complete_data, dict)
    assert turn_complete_data.get("input_tokens") == 12
    assert turn_complete_data.get("result_subtype") == "success"

    process_events = parsed.get("process_events")
    assert isinstance(process_events, list)
    assert len(process_events) == 7
    assert process_events[0]["classification"] == "reasoning"
    assert process_events[0]["details"]["item_type"] == "thinking"
    assert process_events[0]["text"] == "hidden"
    assert parsed.get("raw_rows") == []
    assert process_events[1]["classification"] == "tool_call"
    assert process_events[1]["summary"] == "literature-digest"
    assert process_events[2]["classification"] == "tool_call"
    assert process_events[2]["details"]["item_type"] == "tool_result"
    assert process_events[3]["classification"] == "command_execution"
    assert process_events[3]["summary"] == "pwd"
    assert process_events[4]["classification"] == "command_execution"
    assert process_events[4]["details"]["tool_name"] == "Bash"
    assert process_events[5]["summary"] == "python missing.py"
    assert process_events[6]["classification"] == "command_execution"
    assert process_events[6]["details"]["is_error"] is True
    assert parsed.get("raw_rows") == []

    start_marker = turn_markers[0]
    complete_marker = turn_markers[1]
    assert start_marker["raw_ref"]["stream"] == "stdout"
    assert complete_marker["raw_ref"]["stream"] == "stdout"


def test_claude_runtime_stream_emits_sandbox_diagnostics_without_losing_success():
    adapter = ClaudeExecutionAdapter()
    parsed = adapter.parse_runtime_stream(
        stdout_raw=(
            b'{"type":"system","subtype":"init","session_id":"e46bbf28-de7c-4ec1-9c9f-6fb45495268e"}\n'
            b'{"type":"assistant","message":{"content":[{"name":"Bash","input":{"command":"python task.py","description":"run task"},"id":"toolu_bash","type":"tool_use"}]}}\n'
            b'{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"toolu_bash","content":"bwrap: loopback: Failed RTM_NEWADDR: Operation not permitted","is_error":true}]}}\n'
            b'{"type":"result","subtype":"success","session_id":"e46bbf28-de7c-4ec1-9c9f-6fb45495268e","result":"{\\"ok\\": true}","structured_output":{"ok":true}}\n'
        ),
        stderr_raw=b"socat: command not found\n",
    )

    diagnostics = parsed.get("diagnostics")
    assert isinstance(diagnostics, list)
    assert "CLAUDE_SANDBOX_DEPENDENCY_MISSING" in diagnostics
    assert "CLAUDE_SANDBOX_RUNTIME_FAILURE" in diagnostics
    assert "CLAUDE_SANDBOX_POLICY_VIOLATION" not in diagnostics
    assert parsed["turn_complete_data"]["result_subtype"] == "success"
    assert parsed["run_handle"]["handle_id"] == "e46bbf28-de7c-4ec1-9c9f-6fb45495268e"


def test_claude_runtime_stream_distinguishes_sandbox_policy_violation():
    adapter = ClaudeExecutionAdapter()
    parsed = adapter.parse_runtime_stream(
        stdout_raw=(
            b'{"type":"system","subtype":"init","session_id":"policy-run"}\n'
            b'{"type":"assistant","message":{"content":[{"name":"Bash","input":{"command":"echo test >/etc/hosts","description":"forbidden write"},"id":"toolu_bash","type":"tool_use"}]}}\n'
            b'{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"toolu_bash","content":"Permission denied: blocked by sandbox policy for write outside permitted paths","is_error":true}]}}\n'
            b'{"type":"result","subtype":"success","session_id":"policy-run","result":"{\\"ok\\": true}"}\n'
        ),
        stderr_raw=b"",
    )

    diagnostics = parsed.get("diagnostics")
    assert isinstance(diagnostics, list)
    assert "CLAUDE_SANDBOX_POLICY_VIOLATION" in diagnostics
    assert "CLAUDE_SANDBOX_RUNTIME_FAILURE" not in diagnostics


def test_claude_build_resume_command_uses_resume_flag(monkeypatch):
    adapter = ClaudeExecutionAdapter()
    monkeypatch.setattr(adapter.agent_manager, "resolve_engine_command", lambda _engine: Path("/usr/bin/claude"))

    command = adapter.build_resume_command(
        prompt="second turn",
        options={},
        session_handle=EngineSessionHandle(
            engine="claude",
            handle_type=EngineSessionHandleType.SESSION_ID,
            handle_value="session-claude-resume",
            created_at_turn=1,
        ),
    )

    assert command == [
        str(Path("/usr/bin/claude")),
        "--resume",
        "session-claude-resume",
        "-p",
        "--output-format",
        "stream-json",
        "--verbose",
        "second turn",
    ]
