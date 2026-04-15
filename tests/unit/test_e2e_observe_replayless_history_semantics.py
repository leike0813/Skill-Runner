from pathlib import Path


def _template() -> str:
    return Path("e2e_client/templates/run_observe.html").read_text(encoding="utf-8")


def test_template_uses_history_then_stream_and_no_replay():
    content = _template()
    assert "await loadHistory();" in content
    assert "await startStream();" in content
    assert "recordings" not in content


def test_template_uses_canonical_chat_history_and_stream():
    content = _template()
    assert "/api/runs/${requestId}/chat/history" in content
    assert "/api/runs/${requestId}/chat?cursor=${cursor}" in content
    assert "handleChatEvent(event)" in content


def test_template_pending_cards_are_separate_from_chat_replay():
    content = _template()
    assert "applyPendingPrompt({" in content
    assert "appendChatBubble(\"user\"" not in content
    assert "safeText(uiHints.prompt).trim()" in content
    assert "safeText(uiHints.hint).trim()" in content
