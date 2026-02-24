from pathlib import Path


def _template() -> str:
    return Path("e2e_client/templates/run_observe.html").read_text(encoding="utf-8")


def test_template_uses_history_then_stream_and_no_replay():
    content = _template()
    assert "await loadHistory();" in content
    assert "await startStream();" in content
    assert "recordings" not in content


def test_template_renders_reply_accepted_as_user_when_preview_available():
    content = _template()
    assert "if (type === \"interaction.reply.accepted\")" in content
    assert "response_preview" in content
    assert "appendChatBubble(\"user\", preview" in content


def test_template_user_input_required_only_updates_prompt_card():
    content = _template()
    assert "if (type === \"user.input.required\")" in content
    assert "handleUserInputRequired(event);" in content
    assert "applyPendingPrompt(payload);" in content
    assert "user.input.required.prompt:" not in content
