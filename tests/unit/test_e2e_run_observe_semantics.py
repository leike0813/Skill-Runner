from pathlib import Path


def _read_template() -> str:
    path = Path("e2e_client/templates/run_observe.html")
    return path.read_text(encoding="utf-8")


def test_run_observe_template_has_prompt_card_and_shortcut_hint():
    content = _read_template()
    assert "Pending Input Request" in content
    assert 'id="prompt-card"' in content
    assert 'id="final-summary-card"' in content
    assert "Ctrl+Enter / Cmd+Enter to send" in content
    assert "replyTextEl.addEventListener(\"keydown\"" in content


def test_run_observe_template_has_running_thinking_card():
    content = _read_template()
    assert 'id="thinking-card"' in content
    assert "Agent is thinking" in content
    assert "@keyframes thinkingPulse" in content
    assert "updateThinkingCard(currentStatus);" in content


def test_run_observe_template_removes_technical_panels():
    content = _read_template()
    assert "Event Relations" not in content
    assert "Raw Ref Preview" not in content
    assert "diagnostic-panel" not in content
    assert "stderr-panel" not in content


def test_run_observe_template_extracts_ask_user_yaml_into_prompt_card():
    content = _read_template()
    assert "extractAskUserBlocks" in content
    assert "parseAskUserYaml" in content
    assert "renderPromptCard" in content
    assert "parsed.stripped" in content
    assert "applyPendingPrompt(askPayload)" in content
    assert "ui_hints" in content
    assert "hint" in content


def test_run_observe_template_maps_user_input_required_to_agent_semantics():
    content = _read_template()
    assert "if (type === \"user.input.required\")" in content
    assert "applyPendingPrompt(payload)" in content
    assert "appendChatBubble(\"user\", text || \"(empty reply)\"" in content
    assert "response_preview" in content


def test_run_observe_template_hides_prompt_card_body_when_hint_missing():
    content = _read_template()
    assert "promptTextEl.classList.add(\"hidden\")" in content
    assert "promptTextEl.classList.remove(\"hidden\")" in content


def test_run_observe_template_appends_final_artifact_summary():
    content = _read_template()
    assert "/api/runs/${requestId}/final-summary" in content
    assert "payload.result_status" in content
    assert "buildFinalSummaryText(" in content
    assert "if (normalizedStatus === \"failed\")" in content
    assert "任务失败。" in content
    assert "if (normalizedStatus === \"canceled\")" in content
    assert "任务已取消。" in content
    assert "finalSummaryTextEl.textContent" in content
    assert "finalSummaryCardEl.classList.remove(\"hidden\")" in content
    assert "const hasResult = payload.has_result === true;" in content
    assert "scheduleFinalSummaryRetry" in content
    assert "clearFinalSummaryCard()" in content


def test_run_observe_template_renders_all_assistant_messages_as_bubbles():
    content = _read_template()
    assert "if (cleaned) {" in content
    assert "appendChatBubble(" in content
    assert "isStructuredDoneMessage" not in content


def test_run_observe_template_result_link_removed_and_file_tree_layout_stable():
    content = _read_template()
    assert "/runs/{{ request_id }}/result" not in content
    assert "file-tree-layout" in content
    assert "preview-panel" in content
