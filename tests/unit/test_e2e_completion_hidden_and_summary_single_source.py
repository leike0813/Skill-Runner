from pathlib import Path


def _template() -> str:
    return Path("e2e_client/templates/run_observe.html").read_text(encoding="utf-8")


def test_completion_event_does_not_render_chat_bubble() -> None:
    content = _template()
    assert '/api/runs/${requestId}/chat/history' in content
    assert 'stream.addEventListener("chat_event"' in content
    assert 'appendChatBubble("agent", "任务已完成。"' not in content
    assert "await maybeAppendFinalSummary();" in content


def test_agent_messages_are_not_filtered_by_legacy_done_message_guard() -> None:
    content = _template()
    assert "function isStructuredDoneMessage(text)" not in content
    assert "if (cleaned && !isStructuredDoneMessage(cleaned))" not in content
    assert "function appendChatBubble(role, text, key)" in content
