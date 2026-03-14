from pathlib import Path


def _read_template() -> str:
    path = Path("e2e_client/templates/run_observe.html")
    return path.read_text(encoding="utf-8")


def _read_e2e_template(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_run_observe_template_has_prompt_card_and_shortcut_hint():
    content = _read_template()
    assert "Pending Input Request" in content
    assert "Authentication Required" in content
    assert 'id="prompt-card"' in content
    assert 'id="auth-card"' in content
    assert 'id="prompt-card-actions"' in content
    assert 'id="auth-card-actions"' in content
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


def test_run_observe_template_consumes_backend_ask_user_hints():
    content = _read_template()
    assert "deriveAskUserView" in content
    assert "safeText(askUser.hint).trim()" in content
    assert "renderPromptCard" in content
    assert "extractAskUserBlocks" not in content
    assert "parseAskUserYaml" not in content
    assert "applyPendingPrompt({" in content
    assert 'id="prompt-card-hint"' in content
    assert "ui_hints" in content
    assert "replyTextEl.placeholder = hint || I18N.replyPlaceholder;" in content


def test_run_observe_template_maps_user_input_required_to_agent_semantics():
    content = _read_template()
    assert "applyPendingPrompt(payload)" in content
    assert "renderActionButtons(" in content
    assert "resolveInteractionActionResponse" in content
    assert 'if (kind === "confirm" && options.length === 0)' in content
    assert '{ label: "是", value: "是" }' in content
    assert '{ label: "否", value: "否" }' in content
    assert "response: resolveInteractionActionResponse(kind, option)" in content
    assert "mode: \"interaction\"" in content
    assert "successText" not in content
    assert "successKey" not in content


def test_run_observe_template_supports_auth_challenge_and_redacted_submission():
    content = _read_template()
    assert "renderAuthCard(payload)" in content
    assert "pending_auth_method_selection" in content
    assert "/api/runs/${requestId}/auth/session" in content
    assert "executeWaitingAuthWatchdogTick" in content
    assert "maybeStartWaitingAuthWatchdog" in content
    assert "clearWaitingAuthWatchdog" in content
    assert 'selection: {' in content
    assert 'kind: "auth_method"' in content
    assert "const askUser = payload && typeof payload.ask_user === \"object\" ? payload.ask_user : null;" in content
    assert 'id="auth-card-hint"' in content
    assert "setReplyComposerVisible(false)" in content
    assert "setReplyComposerVisible(true)" in content
    assert "lastAuthRenderSignature" in content
    assert "lastPromptRenderSignature" in content
    assert 'if (currentStatus !== "waiting_auth") {' in content
    assert 'mode: "auth"' in content
    assert "submitPayload(" in content
    assert "API key submitted" not in content
    assert "Authorization code submitted" not in content
    assert "normalizeUploadFileSpecs" in content
    assert "askUser.kind).trim() === \"upload_files\"" in content
    assert "askUser.files" in content
    assert "resolveAuthImportSpec" not in content


def test_run_observe_auth_import_panel_not_cleared_before_signature_early_return():
    content = _read_template()
    signature_guard = "if (signature && signature === lastAuthRenderSignature && !authCardEl.classList.contains(\"hidden\"))"
    clear_call = "clearAuthImportPanel();"
    guard_idx = content.find(signature_guard)
    clear_idx = content.find(clear_call, guard_idx if guard_idx >= 0 else 0)
    assert guard_idx >= 0
    assert clear_idx > guard_idx


def test_run_observe_template_hides_technical_auth_details():
    content = _read_template()
    assert 'id="auth-card-kind"' not in content
    assert 'id="auth-card-methods"' not in content
    assert 'id="auth-card-instructions"' not in content


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
    assert "I18N.taskFailedPrefix" in content
    assert "if (normalizedStatus === \"canceled\")" in content
    assert "I18N.taskCanceledPrefix" in content
    assert "finalSummaryTextEl.textContent" in content
    assert "finalSummaryCardEl.classList.remove(\"hidden\")" in content
    assert "const hasResult = payload.has_result === true;" in content
    assert "scheduleFinalSummaryRetry" in content
    assert "clearFinalSummaryCard()" in content


def test_run_observe_template_renders_all_assistant_messages_as_bubbles():
    content = _read_template()
    assert "handleChatEvent(event)" in content
    assert "appendChatBubble(" in content
    assert "isStructuredDoneMessage" not in content


def test_run_observe_template_supports_assistant_process_thinking_bubble() -> None:
    content = _read_template()
    assert "/static/js/chat_thinking_core.js" in content
    assert "createThinkingChatModel()" in content
    assert "chatModel.consume(event)" in content
    assert "entry.type === \"thinking\"" in content
    assert "processTypeLabel(" in content
    assert "thinking-arrow" in content
    assert "bubble.setAttribute(\"role\", \"button\")" in content
    assert "renderChatModel({ preserveScroll: true })" in content
    assert "function isNearBottom(targetEl, thresholdPx = 24)" in content
    assert "if (entry.collapsed) {" in content
    assert "thinking-item" in content


def test_run_observe_template_keeps_stream_open_until_terminal_chat_event():
    content = _read_template()
    assert 'if (isTerminal(currentStatus)) {' in content
    assert "clearWaitingUserWatchdog();" in content
    assert "setReplyEnabled(false);" in content
    assert "clearPromptCard();" in content
    assert "await catchUpHistory();" in content
    assert "await maybeAppendFinalSummary();" in content
    assert "await maybeLoadFileTreeOnTerminal();" in content


def test_run_observe_template_catches_up_history_for_waiting_and_terminal_states():
    content = _read_template()
    assert "async function catchUpHistory()" in content
    assert "await catchUpHistory();" in content
    assert "catchUpHistory().catch(() => {});" in content
    assert "catchUpHistory()\n                .catch(() => {})" in content
    assert "function shouldShowBackendUnreachable(evt)" in content
    assert "if (shouldShowBackendUnreachable(evt)) {" in content


def test_run_observe_template_result_link_removed_and_file_tree_layout_stable():
    content = _read_template()
    assert "/runs/{{ request_id }}/result" not in content
    assert "file-tree-layout" in content
    assert "preview-panel" in content
    assert 'id="file-bundle-download"' in content
    assert "/api/runs/{{ request_id }}/bundle/download" in content
    assert "SkillRunnerFileExplorer" in content
    assert "mountFileExplorer" in content
    assert "tree-toggle-btn" in content
    assert ".preview-panel" in content
    assert "overflow: auto;" in content


def test_run_observe_template_uses_canonical_chat_replay_routes() -> None:
    content = _read_template()
    assert "/api/runs/${requestId}/chat/history" in content
    assert "/api/runs/${requestId}/chat?cursor=${cursor}" in content
    assert "/api/runs/${requestId}/events" not in content
    assert "stream.addEventListener(\"chat_event\"" in content


def test_run_observe_template_does_not_optimistically_append_chat_bubbles() -> None:
    content = _read_template()
    assert "appendChatBubble(\"user\"" not in content
    assert "response_preview" not in content
    assert "interaction.reply.accepted" not in content


def test_run_observe_template_supports_markdown_and_json_preview_modes() -> None:
    content = _read_template()
    assert "SkillRunnerFileExplorer" in content
    assert "mountFileExplorer" in content
    assert "filePreviewLoading" in content
    assert "fileFormatMarkdown" in content
    assert "fileFormatJson" in content
    assert "fileFormatYaml" in content
    assert "fileFormatToml" in content
    assert "fileFormatPython" in content
    assert "fileFormatJavascript" in content


def test_e2e_key_pages_keep_standard_table_action_button_classes() -> None:
    template_paths = [
        "e2e_client/templates/index.html",
        "e2e_client/templates/runs.html",
    ]
    for template_path in template_paths:
        content = _read_e2e_template(template_path)
        assert 'class="table-actions"' in content
        assert 'class="btn btn-secondary"' in content
