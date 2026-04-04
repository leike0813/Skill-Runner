import json
from pathlib import Path

import pytest

from server.engines.claude.adapter.execution_adapter import ClaudeExecutionAdapter
from server.engines.codex.adapter.stream_parser import CodexStreamParser
from server.engines.opencode.adapter.stream_parser import OpencodeStreamParser
from server.runtime.adapter.common.profile_loader import load_adapter_profile
from server.runtime.adapter.common.live_stream_parser_common import (
    LIVE_STREAM_LINE_OVERFLOW_REPAIRED,
    NdjsonLiveStreamParserSession,
    repair_truncated_json_line,
)
from server.runtime.observability.fcmp_live_journal import fcmp_live_journal
from server.runtime.observability.rasp_live_journal import rasp_live_journal
from server.runtime.protocol.live_publish import (
    FcmpEventPublisher,
    LiveRuntimeEmitterImpl,
    RaspEventPublisher,
)


class _NoopMirrorWriter:
    def enqueue(self, *, run_dir: Path, attempt_number: int, row: dict) -> None:
        _ = run_dir
        _ = attempt_number
        _ = row


class _StubCodexAdapter:
    def __init__(self) -> None:
        self.profile = load_adapter_profile(
            "codex",
            Path("server/engines/codex/adapter/adapter_profile.json"),
        )

    def _parse_json_with_deterministic_repair(self, text: str):
        return None, "none"

    def _build_turn_result_from_payload(self, result, repair_level):
        raise AssertionError("not used")

    def _materialize_output_payload(self, turn_result):
        raise AssertionError("not used")

    def _turn_error(self, message: str):
        raise AssertionError(message)


class _RawOnlyStreamParser:
    def parse_runtime_stream(self, *, stdout_raw: bytes, stderr_raw: bytes, pty_raw: bytes = b""):
        _ = stdout_raw
        _ = stderr_raw
        _ = pty_raw
        return {
            "parser": "raw_only",
            "confidence": 1.0,
            "assistant_messages": [],
            "raw_rows": [],
            "diagnostics": [],
            "structured_types": [],
        }


class _RunHandleOnlySession:
    def __init__(self) -> None:
        self._seq = 0

    def feed(self, *, stream: str, text: str, byte_from: int, byte_to: int):
        _ = stream
        _ = text
        self._seq += 1
        return [
            {
                "kind": "run_handle",
                "handle_id": f"handle-{self._seq}",
                "raw_ref": {"stream": "stdout", "byte_from": byte_from, "byte_to": byte_to},
            }
        ]

    def finish(self, *, exit_code: int, failure_reason: str | None):
        _ = exit_code
        _ = failure_reason
        return []


class _RunHandleOnlyParser:
    def start_live_session(self):
        return _RunHandleOnlySession()


class _TerminalSemanticOnlySession:
    def __init__(self) -> None:
        self._stdout = bytearray()
        self._stderr = bytearray()

    def feed(self, *, stream: str, text: str, byte_from: int, byte_to: int):
        _ = byte_from
        _ = byte_to
        encoded = text.encode("utf-8", errors="replace")
        if stream == "stderr":
            self._stderr.extend(encoded)
        else:
            self._stdout.extend(encoded)
        return []

    def finish(self, *, exit_code: int, failure_reason: str | None):
        _ = exit_code
        _ = failure_reason
        stdout_len = len(self._stdout)
        if stdout_len <= 0:
            return []
        raw_ref = {"stream": "stdout", "byte_from": 0, "byte_to": stdout_len}
        return [
            {"kind": "run_handle", "handle_id": "session-1", "raw_ref": raw_ref},
            {"kind": "turn_marker", "marker": "start", "raw_ref": raw_ref},
            {
                "kind": "assistant_message",
                "text": "structured response",
                "raw_ref": raw_ref,
                "message_id": "m-1",
            },
            {"kind": "turn_marker", "marker": "complete", "raw_ref": raw_ref},
            {"kind": "turn_completed"},
        ]


class _TerminalSemanticOnlyParser:
    live_semantic_on_finish_only = True

    def start_live_session(self):
        return _TerminalSemanticOnlySession()


class _StubOpencodeAdapter:
    def __init__(self) -> None:
        self.profile = load_adapter_profile(
            "opencode",
            Path("server/engines/opencode/adapter/adapter_profile.json"),
        )


class _RecordingNdjsonSession(NdjsonLiveStreamParserSession):
    def __init__(self) -> None:
        super().__init__(accepted_streams={"stdout", "pty"})
        self.rows: list[tuple[str, dict, dict]] = []

    def handle_live_row(self, *, payload: dict, raw_ref: dict, stream: str):
        self.rows.append((stream, payload, raw_ref))
        return [
            {
                "kind": "diagnostic",
                "code": f"{stream}:{payload.get('id')}",
                "raw_ref": raw_ref,
            }
        ]


def test_ndjson_live_session_keeps_split_chunk_offsets_stable() -> None:
    session = _RecordingNdjsonSession()
    payload = '{"id":"row-1"}\n{"id":"row-2"}\n'
    payload_bytes = payload.encode("utf-8")
    split = 11
    first = payload_bytes[:split].decode("utf-8", errors="replace")
    second = payload_bytes[split:].decode("utf-8", errors="replace")

    emissions_first = session.feed(stream="stdout", text=first, byte_from=0, byte_to=split)
    emissions_second = session.feed(
        stream="stdout",
        text=second,
        byte_from=split,
        byte_to=len(payload_bytes),
    )

    assert emissions_first == []
    assert [item["code"] for item in emissions_second] == ["stdout:row-1", "stdout:row-2"]
    assert session.rows[0][2] == {"stream": "stdout", "byte_from": 0, "byte_to": 15}
    assert session.rows[1][2] == {"stream": "stdout", "byte_from": 15, "byte_to": len(payload_bytes)}


def test_ndjson_live_session_ignores_invalid_json_and_routes_multiple_streams() -> None:
    session = _RecordingNdjsonSession()

    stdout_emissions = session.feed(
        stream="stdout",
        text='not-json\n{"id":"row-1"}\n',
        byte_from=0,
        byte_to=len('not-json\n{"id":"row-1"}\n'.encode("utf-8")),
    )
    stderr_emissions = session.feed(
        stream="stderr",
        text='{"id":"ignored"}\n',
        byte_from=0,
        byte_to=len('{"id":"ignored"}\n'.encode("utf-8")),
    )
    pty_emissions = session.feed(
        stream="pty",
        text='{"id":"row-2"}\n',
        byte_from=0,
        byte_to=len('{"id":"row-2"}\n'.encode("utf-8")),
    )

    assert [item["code"] for item in stdout_emissions] == ["stdout:row-1"]
    assert stderr_emissions == []
    assert [item["code"] for item in pty_emissions] == ["pty:row-2"]
    assert [item[0] for item in session.rows] == ["stdout", "pty"]


def test_repair_truncated_json_line_closes_string_and_containers() -> None:
    prefix = '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"toolu_1","content":"'
    repaired = repair_truncated_json_line(prefix + ("A" * 5000))

    assert isinstance(repaired, str)
    payload = json.loads(repaired)
    assert payload["type"] == "user"
    assert payload["message"]["content"][0]["type"] == "tool_result"
    assert payload["message"]["content"][0]["tool_use_id"] == "toolu_1"
    assert "[truncated by live overflow guard]" in payload["message"]["content"][0]["content"]


def test_ndjson_live_session_repairs_overflowed_line_and_resyncs() -> None:
    session = _RecordingNdjsonSession()
    oversized = (
        '{"id":"row-1","content":"'
        + ("A" * 5000)
        + '"}\n{"id":"row-2"}\n'
    )
    payload_bytes = oversized.encode("utf-8")
    split = 2700
    first = payload_bytes[:split].decode("utf-8", errors="replace")
    second = payload_bytes[split:].decode("utf-8", errors="replace")

    emissions_first = session.feed(stream="stdout", text=first, byte_from=0, byte_to=split)
    emissions_second = session.feed(
        stream="stdout",
        text=second,
        byte_from=split,
        byte_to=len(payload_bytes),
    )

    assert emissions_first == []
    assert emissions_second[0]["kind"] == "diagnostic"
    assert emissions_second[0]["code"] == LIVE_STREAM_LINE_OVERFLOW_REPAIRED
    assert [item["code"] for item in emissions_second[1:]] == ["stdout:row-1", "stdout:row-2"]
    first_row_payload = session.rows[0][1]
    assert first_row_payload["id"] == "row-1"
    assert "[truncated by live overflow guard]" in first_row_payload["content"]
    assert session.rows[0][2]["byte_to"] > 4096
    assert session.rows[1][1]["id"] == "row-2"


def test_codex_live_session_keeps_raw_ref_stable_for_split_ndjson_line() -> None:
    parser = CodexStreamParser(_StubCodexAdapter())
    session = parser.start_live_session()
    payload = (
        '{"type":"item.completed","item":{"id":"item_cmd_1","type":"command_execution",'
        '"command":"echo hello","status":"completed","exit_code":0}}\n'
    )
    payload_bytes = payload.encode("utf-8")
    split = 41
    first = payload_bytes[:split]
    second = payload_bytes[split:]
    first_text = first.decode("utf-8", errors="replace")
    second_text = second.decode("utf-8", errors="replace")

    emissions_first = session.feed(
        stream="stdout",
        text=first_text,
        byte_from=0,
        byte_to=len(first),
    )
    emissions_second = session.feed(
        stream="stdout",
        text=second_text,
        byte_from=len(first),
        byte_to=len(payload_bytes),
    )

    assert emissions_first == []
    process = next(item for item in emissions_second if item.get("kind") == "process_event")
    raw_ref = process.get("raw_ref")
    assert isinstance(raw_ref, dict)
    assert raw_ref.get("stream") == "stdout"
    assert raw_ref.get("byte_from") == 0
    assert raw_ref.get("byte_to") == len(payload_bytes)


def test_opencode_live_session_keeps_raw_ref_stable_for_split_ndjson_line() -> None:
    parser = OpencodeStreamParser(_StubOpencodeAdapter())
    session = parser.start_live_session()
    payload = (
        '{"type":"tool_use","part":{"id":"p1","type":"tool","tool":"bash","state":{"status":"completed","input":{"command":"echo hi"},"output":"hi"}}}\n'
    )
    payload_bytes = payload.encode("utf-8")
    split = 47
    first = payload_bytes[:split]
    second = payload_bytes[split:]
    first_text = first.decode("utf-8", errors="replace")
    second_text = second.decode("utf-8", errors="replace")

    emissions_first = session.feed(
        stream="stdout",
        text=first_text,
        byte_from=0,
        byte_to=len(first),
    )
    emissions_second = session.feed(
        stream="stdout",
        text=second_text,
        byte_from=len(first),
        byte_to=len(payload_bytes),
    )

    assert emissions_first == []
    process = next(item for item in emissions_second if item.get("kind") == "process_event")
    raw_ref = process.get("raw_ref")
    assert isinstance(raw_ref, dict)
    assert raw_ref.get("stream") == "stdout"
    assert raw_ref.get("byte_from") == 0
    assert raw_ref.get("byte_to") == len(payload_bytes)


@pytest.mark.asyncio
async def test_live_runtime_emitter_publishes_reasoning_then_final_on_exit(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-live"
    run_dir.mkdir(parents=True, exist_ok=True)
    fcmp_live_journal.clear("run-live")
    rasp_live_journal.clear("run-live")
    parser = CodexStreamParser(_StubCodexAdapter())
    emitter = LiveRuntimeEmitterImpl(
        run_id="run-live",
        run_dir=run_dir,
        engine="codex",
        attempt_number=1,
        stream_parser=parser,
        fcmp_publisher=FcmpEventPublisher(mirror_writer=_NoopMirrorWriter()),
        rasp_publisher=RaspEventPublisher(mirror_writer=_NoopMirrorWriter()),
    )

    await emitter.on_stream_chunk(
        stream="stdout",
        text='{"type":"item.completed","item":{"type":"agent_message","text":"hello live"}}\n',
        byte_from=0,
        byte_to=72,
    )

    payload = fcmp_live_journal.replay(run_id="run-live", after_seq=0)

    assert any(row.get("type") == "assistant.reasoning" for row in payload["events"])
    assert not any(row.get("type") == "assistant.message.final" for row in payload["events"])

    await emitter.on_process_exit(exit_code=0, failure_reason=None)
    payload_after_exit = fcmp_live_journal.replay(run_id="run-live", after_seq=0)
    assert any(row.get("type") == "assistant.message.promoted" for row in payload_after_exit["events"])
    assert any(row.get("type") == "assistant.message.final" for row in payload_after_exit["events"])
    assistant_row = next(row for row in payload_after_exit["events"] if row.get("type") == "assistant.message.final")
    assert assistant_row["data"]["text"] == "hello live"


@pytest.mark.asyncio
async def test_live_runtime_emitter_coalesces_raw_stderr_blocks(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-live-raw-coalesced"
    run_dir.mkdir(parents=True, exist_ok=True)
    fcmp_live_journal.clear("run-live-raw-coalesced")
    rasp_live_journal.clear("run-live-raw-coalesced")
    emitter = LiveRuntimeEmitterImpl(
        run_id="run-live-raw-coalesced",
        run_dir=run_dir,
        engine="gemini",
        attempt_number=1,
        stream_parser=_RawOnlyStreamParser(),
        fcmp_publisher=FcmpEventPublisher(mirror_writer=_NoopMirrorWriter()),
        rasp_publisher=RaspEventPublisher(mirror_writer=_NoopMirrorWriter()),
    )

    await emitter.on_stream_chunk(
        stream="stderr",
        text="line-a\nline-b\nline-c\n",
        byte_from=0,
        byte_to=len("line-a\nline-b\nline-c\n".encode("utf-8")),
    )
    await emitter.on_process_exit(exit_code=0, failure_reason=None)

    rasp_payload = rasp_live_journal.replay(run_id="run-live-raw-coalesced", after_seq=0)
    raw_events = [row for row in rasp_payload["events"] if row.get("event", {}).get("type") == "raw.stderr"]
    assert len(raw_events) == 1
    assert "line-a\nline-b\nline-c" in str(raw_events[0].get("data", {}).get("line", ""))


@pytest.mark.asyncio
async def test_live_runtime_emitter_consumes_run_handle_immediately_and_warns_on_change(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-live-handle"
    run_dir.mkdir(parents=True, exist_ok=True)
    fcmp_live_journal.clear("run-live-handle")
    rasp_live_journal.clear("run-live-handle")
    current_handle: str | None = None

    async def _consume(handle_id: str) -> dict[str, str]:
        nonlocal current_handle
        if current_handle is None:
            current_handle = handle_id
            return {"status": "stored"}
        if current_handle == handle_id:
            return {"status": "unchanged"}
        previous = current_handle
        current_handle = handle_id
        return {"status": "changed", "previous_handle_id": previous}

    emitter = LiveRuntimeEmitterImpl(
        run_id="run-live-handle",
        run_dir=run_dir,
        engine="opencode",
        attempt_number=1,
        stream_parser=_RunHandleOnlyParser(),
        run_handle_consumer=_consume,
        fcmp_publisher=FcmpEventPublisher(mirror_writer=_NoopMirrorWriter()),
        rasp_publisher=RaspEventPublisher(mirror_writer=_NoopMirrorWriter()),
    )

    await emitter.on_stream_chunk(stream="stdout", text="{}\n", byte_from=0, byte_to=3)
    await emitter.on_stream_chunk(stream="stdout", text="{}\n", byte_from=3, byte_to=6)

    assert current_handle == "handle-2"
    rasp_payload = rasp_live_journal.replay(run_id="run-live-handle", after_seq=0)
    rasp_types = [row.get("event", {}).get("type") for row in rasp_payload["events"]]
    assert rasp_types.count("lifecycle.run_handle") == 2
    assert any(
        row.get("event", {}).get("type") == "diagnostic.warning"
        and row.get("data", {}).get("code") == "RUN_HANDLE_CHANGED"
        for row in rasp_payload["events"]
    )

    fcmp_payload = fcmp_live_journal.replay(run_id="run-live-handle", after_seq=0)
    assert any(
        row.get("type") == "diagnostic.warning"
        and row.get("data", {}).get("code") == "RUN_HANDLE_CHANGED"
        for row in fcmp_payload["events"]
    )


@pytest.mark.asyncio
async def test_live_runtime_emitter_delays_raw_until_finish_for_terminal_semantic_only_parser(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-live-terminal-semantic-only"
    run_dir.mkdir(parents=True, exist_ok=True)
    fcmp_live_journal.clear("run-live-terminal-semantic-only")
    rasp_live_journal.clear("run-live-terminal-semantic-only")

    emitter = LiveRuntimeEmitterImpl(
        run_id="run-live-terminal-semantic-only",
        run_dir=run_dir,
        engine="gemini",
        attempt_number=1,
        stream_parser=_TerminalSemanticOnlyParser(),
        fcmp_publisher=FcmpEventPublisher(mirror_writer=_NoopMirrorWriter()),
        rasp_publisher=RaspEventPublisher(mirror_writer=_NoopMirrorWriter()),
    )

    payload = '{"session_id":"session-1","response":"structured response"}\n'
    await emitter.on_stream_chunk(
        stream="stdout",
        text=payload,
        byte_from=0,
        byte_to=len(payload.encode("utf-8")),
    )

    running_rasp = rasp_live_journal.replay(run_id="run-live-terminal-semantic-only", after_seq=0)
    assert not any(
        row.get("event", {}).get("type") == "raw.stdout"
        for row in running_rasp["events"]
    )

    await emitter.on_process_exit(exit_code=0, failure_reason=None)
    final_rasp = rasp_live_journal.replay(run_id="run-live-terminal-semantic-only", after_seq=0)
    assert not any(
        row.get("event", {}).get("type") == "raw.stdout"
        for row in final_rasp["events"]
    )
    assert any(
        row.get("event", {}).get("type") == "lifecycle.run_handle"
        for row in final_rasp["events"]
    )


@pytest.mark.asyncio
async def test_live_runtime_emitter_suppresses_claude_raw_stdout_when_semantics_consume_rows(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-live-claude-semantic"
    run_dir.mkdir(parents=True, exist_ok=True)
    fcmp_live_journal.clear("run-live-claude-semantic")
    rasp_live_journal.clear("run-live-claude-semantic")

    adapter = ClaudeExecutionAdapter()
    emitter = LiveRuntimeEmitterImpl(
        run_id="run-live-claude-semantic",
        run_dir=run_dir,
        engine="claude",
        attempt_number=1,
        stream_parser=adapter.stream_parser,
        fcmp_publisher=FcmpEventPublisher(mirror_writer=_NoopMirrorWriter()),
        rasp_publisher=RaspEventPublisher(mirror_writer=_NoopMirrorWriter()),
    )

    first_payload = (
        '{"type":"system","subtype":"init","session_id":"session-claude-live"}\n'
        '{"type":"assistant","message":{"content":[{"type":"thinking","thinking":"draft plan"},{"type":"text","text":"hello live"}]}}\n'
        '{"type":"assistant","message":{"content":[{"name":"Bash","input":{"command":"pwd"},"id":"toolu_pwd","type":"tool_use"}]}}\n'
        '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"toolu_pwd","content":"/tmp/run","is_error":false}]}}\n'
    )
    await emitter.on_stream_chunk(
        stream="stdout",
        text=first_payload,
        byte_from=0,
        byte_to=len(first_payload.encode("utf-8")),
    )

    running_rasp = rasp_live_journal.replay(run_id="run-live-claude-semantic", after_seq=0)
    running_types = [row.get("event", {}).get("type") for row in running_rasp["events"]]
    assert "raw.stdout" not in running_types
    assert "lifecycle.run_handle" in running_types
    assert "agent.turn_start" in running_types
    assert "agent.reasoning" in running_types
    assert "agent.command_execution" in running_types
    assert running_types.index("lifecycle.run_handle") < running_types.index("agent.turn_start")
    assert running_types.index("agent.turn_start") < running_types.index("agent.reasoning")
    assert running_types.index("agent.reasoning") < running_types.index("agent.command_execution")
    reasoning_events = [
        row for row in running_rasp["events"]
        if row.get("event", {}).get("type") == "agent.reasoning"
    ]
    assert any(row.get("data", {}).get("text") == "draft plan" for row in reasoning_events)

    second_payload = (
        '{"type":"result","subtype":"success","session_id":"session-claude-live","result":"{\\"ok\\": true}","structured_output":{"ok":true}}\n'
    )
    await emitter.on_stream_chunk(
        stream="stdout",
        text=second_payload,
        byte_from=len(first_payload.encode("utf-8")),
        byte_to=len(first_payload.encode("utf-8")) + len(second_payload.encode("utf-8")),
    )

    running_fcmp = fcmp_live_journal.replay(run_id="run-live-claude-semantic", after_seq=0)
    running_fcmp_types = [row.get("type") for row in running_fcmp["events"]]
    assert "assistant.command_execution" in running_fcmp_types
    assert "assistant.message.final" in running_fcmp_types
    reasoning_fcmp = [
        row for row in running_fcmp["events"]
        if row.get("type") == "assistant.reasoning"
    ]
    assert any(row.get("data", {}).get("text") == "draft plan" for row in reasoning_fcmp)

    await emitter.on_process_exit(exit_code=0, failure_reason=None)

    final_rasp = rasp_live_journal.replay(run_id="run-live-claude-semantic", after_seq=0)
    assert not any(row.get("event", {}).get("type") == "raw.stdout" for row in final_rasp["events"])
    assert any(row.get("event", {}).get("type") == "lifecycle.run_handle" for row in final_rasp["events"])


@pytest.mark.asyncio
async def test_live_runtime_emitter_repairs_overflowed_claude_tool_result_and_resyncs(tmp_path: Path) -> None:
    run_dir = tmp_path / "run-live-claude-overflow-repaired"
    run_dir.mkdir(parents=True, exist_ok=True)
    fcmp_live_journal.clear("run-live-claude-overflow-repaired")
    rasp_live_journal.clear("run-live-claude-overflow-repaired")

    adapter = ClaudeExecutionAdapter()
    emitter = LiveRuntimeEmitterImpl(
        run_id="run-live-claude-overflow-repaired",
        run_dir=run_dir,
        engine="claude",
        attempt_number=1,
        stream_parser=adapter.stream_parser,
        fcmp_publisher=FcmpEventPublisher(mirror_writer=_NoopMirrorWriter()),
        rasp_publisher=RaspEventPublisher(mirror_writer=_NoopMirrorWriter()),
    )

    init_payload = '{"type":"system","subtype":"init","session_id":"session-claude-overflow"}\n'
    tool_use_payload = (
        '{"type":"assistant","message":{"content":[{"name":"Read","input":{"file_path":"/tmp/source.md"},'
        '"id":"toolu_read","type":"tool_use"}]}}\n'
    )
    tool_result_payload = (
        '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"toolu_read","content":"'
        + ("B" * 7000)
        + '","is_error":false}]}}\n'
    )
    result_payload = (
        '{"type":"result","subtype":"success","session_id":"session-claude-overflow","result":"done"}\n'
    )
    combined = f"{init_payload}{tool_use_payload}{tool_result_payload}{result_payload}"

    await emitter.on_stream_chunk(
        stream="stdout",
        text=combined,
        byte_from=0,
        byte_to=len(combined.encode("utf-8")),
    )
    await emitter.on_process_exit(exit_code=0, failure_reason=None)

    rasp_payload = rasp_live_journal.replay(run_id="run-live-claude-overflow-repaired", after_seq=0)
    rasp_types = [row.get("event", {}).get("type") for row in rasp_payload["events"]]
    assert "diagnostic.warning" in rasp_types
    assert "agent.tool_call" in rasp_types
    assert "agent.turn_complete" in rasp_types
    overflow_warning = next(
        row for row in rasp_payload["events"]
        if row.get("event", {}).get("type") == "diagnostic.warning"
        and row.get("data", {}).get("code") == LIVE_STREAM_LINE_OVERFLOW_REPAIRED
    )
    assert overflow_warning["data"]["stream_line_limit_bytes"] == 4096
    repaired_tool_result = next(
        row for row in rasp_payload["events"]
        if row.get("event", {}).get("type") == "agent.tool_call"
        and row.get("data", {}).get("details", {}).get("item_type") == "tool_result"
    )
    assert repaired_tool_result["data"]["classification"] == "tool_call"
    assert "[truncated by live overflow guard]" in str(repaired_tool_result["data"].get("text", ""))

    fcmp_payload = fcmp_live_journal.replay(run_id="run-live-claude-overflow-repaired", after_seq=0)
    fcmp_types = [row.get("type") for row in fcmp_payload["events"]]
    assert "diagnostic.warning" in fcmp_types
    assert "assistant.tool_call" in fcmp_types
    assert "assistant.message.final" in fcmp_types
