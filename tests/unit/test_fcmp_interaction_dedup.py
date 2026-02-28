from datetime import datetime

from server.models import RuntimeEventCategory, RuntimeEventSource
from server.runtime.protocol.factories import make_rasp_event
from server.runtime.protocol.event_protocol import build_fcmp_events


def test_build_fcmp_events_deduplicates_waiting_prompt_and_keeps_reply_preview():
    source = RuntimeEventSource(engine="gemini", parser="test", confidence=0.95)
    ask_text = (
        "你最近有没有遇到哪些烦恼或困扰？\n\n"
        "<ASK_USER_YAML>\n"
        "ask_user:\n"
        "  kind: open_text\n"
        "</ASK_USER_YAML>"
    )
    rasp_events = [
        make_rasp_event(
            run_id="run-1",
            seq=1,
            source=source,
            category=RuntimeEventCategory.LIFECYCLE,
            type_name="lifecycle.run.status",
            data={"status": "waiting_user"},
            attempt_number=2,
            ts=datetime.utcnow(),
        ),
        make_rasp_event(
            run_id="run-1",
            seq=2,
            source=source,
            category=RuntimeEventCategory.AGENT,
            type_name="agent.message.final",
            data={"message_id": "m2", "text": ask_text},
            attempt_number=2,
            ts=datetime.utcnow(),
        ),
        make_rasp_event(
            run_id="run-1",
            seq=3,
            source=source,
            category=RuntimeEventCategory.INTERACTION,
            type_name="interaction.user_input.required",
            data={"interaction_id": 2, "kind": "free_text", "prompt": ask_text},
            attempt_number=2,
            ts=datetime.utcnow(),
        ),
    ]
    history = [
        {
            "event_type": "reply",
            "interaction_id": 1,
            "created_at": "2026-02-24T00:00:01",
            "payload": {
                "resolution_mode": "user_reply",
                "resolved_at": "2026-02-24T00:00:02",
                "response": {"text": "我的回复"},
            },
        },
        {
            "event_type": "reply",
            "interaction_id": 7,
            "created_at": "2026-02-24T00:00:03",
            "payload": {
                "resolution_mode": "user_reply",
                "resolved_at": "2026-02-24T00:00:04",
                "response": {"text": "旧回复"},
            },
        },
    ]
    orchestrator_events = [
        {
            "ts": "2026-02-24T00:00:00",
            "attempt_number": 2,
            "seq": 1,
            "category": "lifecycle",
            "type": "lifecycle.run.started",
            "data": {"status": "running"},
        },
        {
            "ts": "2026-02-24T00:00:01",
            "attempt_number": 2,
            "seq": 2,
            "category": "interaction",
            "type": "interaction.user_input.required",
            "data": {"interaction_id": 2, "kind": "open_text"},
        },
    ]

    events = build_fcmp_events(
        rasp_events,
        status="waiting_user",
        pending_interaction={"interaction_id": 2, "kind": "open_text", "prompt": ask_text},
        interaction_history=history,
        orchestrator_events=orchestrator_events,
        completion=None,
    )

    assistant_rows = [evt for evt in events if evt.type == "assistant.message.final"]
    assert len(assistant_rows) == 1
    assert "<ASK_USER_YAML>" not in assistant_rows[0].data["text"]

    required_rows = [evt for evt in events if evt.type == "user.input.required"]
    assert len(required_rows) == 1
    assert required_rows[0].data["prompt"] == "你最近有没有遇到哪些烦恼或困扰？"
    assert required_rows[0].data["prompt"] != "Provide next user turn"

    reply_rows = [evt for evt in events if evt.type == "interaction.reply.accepted"]
    assert len(reply_rows) == 1
    assert reply_rows[0].data["interaction_id"] == 1
    assert reply_rows[0].data["response_preview"] == "我的回复"
