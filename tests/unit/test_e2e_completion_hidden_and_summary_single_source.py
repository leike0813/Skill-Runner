from pathlib import Path


def _template() -> str:
    return Path("e2e_client/templates/run_observe.html").read_text(encoding="utf-8")


def test_completion_event_does_not_render_chat_bubble() -> None:
    content = _template()
    assert 'if (type === "conversation.completed")' in content
    assert 'appendChatBubble("agent", "任务已完成。"' not in content
    assert "maybeAppendFinalSummary().catch(() => {});" in content


def test_structured_done_message_is_suppressed_from_chat() -> None:
    content = _template()
    assert "function isStructuredDoneMessage(text)" in content
    assert "if (cleaned && !isStructuredDoneMessage(cleaned))" in content
