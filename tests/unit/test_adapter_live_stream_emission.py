from pathlib import Path

import pytest

from server.engines.codex.adapter.stream_parser import CodexStreamParser
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
    def _parse_json_with_deterministic_repair(self, text: str):
        return None, "none"

    def _build_turn_result_from_payload(self, result, repair_level):
        raise AssertionError("not used")

    def _materialize_output_payload(self, turn_result):
        raise AssertionError("not used")

    def _turn_error(self, message: str):
        raise AssertionError(message)


@pytest.mark.asyncio
async def test_live_runtime_emitter_publishes_final_message_before_audit_backfill(tmp_path: Path) -> None:
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

    assert any(row.get("type") == "assistant.message.final" for row in payload["events"])
    assistant_row = next(row for row in payload["events"] if row.get("type") == "assistant.message.final")
    assert assistant_row["data"]["text"] == "hello live"
