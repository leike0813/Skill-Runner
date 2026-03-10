from pathlib import Path

import pytest

from server.engines.codex.adapter.stream_parser import CodexStreamParser
from server.engines.opencode.adapter.stream_parser import OpencodeStreamParser
from server.runtime.adapter.common.profile_loader import load_adapter_profile
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
