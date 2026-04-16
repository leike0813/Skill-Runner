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
    assert 'id="prompt-card-files"' in content
    assert 'id="final-summary-card"' in content
    assert 'id="final-summary-status"' in content
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
    assert "safeText(uiHints.prompt).trim()" in content
    assert "safeText(uiHints.hint).trim()" in content
    assert "normalizeUploadFileSpecs(uiHints.files)" in content
    assert "renderPromptCard" in content
    assert "extractAskUserBlocks" not in content
    assert "parseAskUserYaml" not in content
    assert "applyPendingPrompt({" in content
    assert 'id="prompt-card-hint"' in content
    assert 'id="prompt-card-files"' in content
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
    assert "async function restartStreamAfterWaitingExit()" in content
    assert "await restartStreamAfterWaitingExit();" in content
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
    assert 'kind: authInputKind || "auth_code_or_url"' in content


def test_run_observe_template_supports_custom_provider_auth_panel():
    content = _read_template()
    assert 'id="auth-provider-config-panel"' in content
    assert 'id="auth-provider-select"' in content
    assert 'id="auth-provider-model-select"' in content
    assert 'id="auth-provider-id-input"' in content
    assert 'id="auth-provider-api-key-input"' in content
    assert 'id="auth-provider-base-url-input"' in content
    assert 'id="auth-provider-model-input"' in content
    assert "renderAuthProviderConfigPanel(payload, hint)" in content
    assert "submitAuthProviderConfig()" in content
    assert 'kind: "custom_provider"' in content
    assert 'widget).trim() === "provider_config"' in content


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


def test_run_observe_template_keeps_status_only_final_summary_card():
    content = _read_template()
    assert "/api/runs/${requestId}/final-summary" not in content
    assert "buildFinalSummaryText(" not in content
    assert "maybeAppendFinalSummary" not in content
    assert "scheduleFinalSummaryRetry" not in content
    assert "taskCompletedStructuredHint" not in content
    assert "resultErrorLabel" not in content
    assert "artifactsLabel" not in content
    assert "resultPreviewLabel" not in content
    assert "unknownError" not in content
    assert "canceledError" not in content
    assert "clearFinalSummaryCard()" in content
    assert "renderFinalSummaryCard(currentStatus);" in content
    assert "buildFinalSummaryStatus(status)" in content
    assert "finalSummaryStatusEl.textContent = buildFinalSummaryStatus(status);" in content
    assert "finalSummaryCardEl.classList.remove(\"hidden\")" in content


def test_run_observe_template_defaults_to_plain_mode_for_assistant_messages():
    content = _read_template()
    assert 'id="chat-mode-plain"' in content
    assert 'id="chat-mode-bubble"' in content
    assert "setChatDisplayMode(\"plain\")" in content
    assert "chatModel.setDisplayMode(chatDisplayMode);" in content
    assert "function createCompatibleThinkingChatModel(initialMode)" in content
    assert "handleChatEvent(event)" in content
    assert "appendChatBubble(" in content
    assert 'chatEl.classList.toggle("plain-mode", mode === "plain")' in content
    assert 'chatEl.classList.toggle("bubble-mode", mode === "bubble")' in content
    assert 'item.className = `chat-plain-entry ${role}`' in content
    assert "isStructuredDoneMessage" not in content


def test_run_observe_template_supports_assistant_process_thinking_bubble() -> None:
    content = _read_template()
    assert "/static/js/chat_thinking_core.js?v=20260416b" in content
    assert "createCompatibleThinkingChatModel(chatDisplayMode)" in content
    assert "chatModel.consume(event)" in content
    assert "entry.type === \"thinking\"" in content
    assert "entry.type === \"revision\"" in content
    assert "processTypeLabel(" in content
    assert "thinking-arrow" in content
    assert "bubble.setAttribute(\"role\", \"button\")" in content
    assert "renderChatModel({ preserveScroll: true })" in content
    assert "function isNearBottom(targetEl, thresholdPx = 24)" in content
    assert "if (entry.collapsed) {" in content
    assert "thinking-item" in content
    assert 'item.className = "chat-plain-process"' in content
    assert 'meta.className = "chat-plain-process-item-meta"' in content
    assert 'textEl.className = "chat-plain-process-item-body"' in content
    assert 'bubble.className = "chat-bubble agent thinking-bubble"' in content


def test_run_observe_template_keeps_stream_open_until_terminal_chat_event():
    content = _read_template()
    assert 'if (isTerminal(currentStatus)) {' in content
    assert "renderFinalSummaryCard(currentStatus);" in content
    assert "clearWaitingUserWatchdog();" in content
    assert "setReplyEnabled(false);" in content
    assert "clearPromptCard();" in content
    assert "await catchUpHistory();" in content
    assert "await maybeLoadFileTreeOnTerminal();" in content


def test_run_observe_template_catches_up_history_for_waiting_and_terminal_states():
    content = _read_template()
    assert "async function catchUpHistory()" in content
    assert "await catchUpHistory();" in content
    assert "catchUpHistory().catch(() => {});" in content
    assert "catchUpHistory()\n                .catch(() => {})" in content
    assert "function shouldShowBackendUnreachable(evt)" in content
    assert "if (shouldShowBackendUnreachable(evt)) {" in content


def test_run_observe_template_reports_client_init_failures_separately_from_backend_errors():
    content = _read_template()
    assert "clientInitFailedPrefix" in content
    assert "showClientInitError(error);" in content
    assert "showReplyError(I18N.submitFailedNetwork);" in content
    assert "console.error(\"run observe initialization failed\", error);" in content


def test_run_observe_template_restarts_stream_after_waiting_exit_even_if_existing_stream_is_open() -> None:
    content = _read_template()
    assert "await restartStreamAfterWaitingExit();" in content
    waiting_user_idx = content.find("async function executeWaitingUserWatchdogTick()")
    waiting_auth_idx = content.find("async function executeWaitingAuthWatchdogTick()")
    assert waiting_user_idx >= 0
    assert waiting_auth_idx >= 0
    assert "if (!stream && !isTerminal(currentStatus))" not in content[waiting_user_idx:waiting_auth_idx]
    assert "if (!stream && !isTerminal(currentStatus))" not in content[waiting_auth_idx:content.find("async function restartStreamAfterWaitingExit()")]
    assert "if (isTerminal(currentStatus)) return;" in content
    assert "await startStream();" in content


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


def test_run_observe_template_consumes_assistant_revision_without_rendering_plain_bubble() -> None:
    content = _read_template()
    assert 'kind !== "assistant_revision"' in content
    assert 'kind === "assistant_revision"' in content
    assert 'if (kind === "assistant_revision") {' in content
    assert "chatModel.consume(event);" in content
    assert "revision-bubble" in content
    assert "chatModel.toggleRevision" in content


def test_run_observe_revision_renders_collapsed_placeholder_only_and_expanded_body_once() -> None:
    content = _read_template()
    assert "const previewText = I18N.revisionCollapsedPrefix;" in content
    assert 'if (entry.collapsed) {' in content
    assert 'latestLine.className = "revision-latest"' in content
    assert 'body.className = "revision-body"' in content
    assert 'latestLine.className = "chat-plain-revision-latest"' in content
    assert 'body.className = "chat-plain-revision-body"' in content


def test_run_observe_revision_uses_rejected_final_reply_wording() -> None:
    content = _read_template()
    assert 'default="Rejected Final Reply"' in content
    assert 'default="(collapsed)"' in content
    assert 'default="Show rejected final reply"' in content
    assert 'default="Hide rejected final reply"' in content


def test_run_observe_revision_uses_plain_structure_in_plain_mode_and_has_single_bubble_title() -> None:
    content = _read_template()
    assert 'if (mode === "plain") {' in content
    assert 'item.className = "chat-plain-entry"' in content
    assert 'header.className = "chat-plain-revision-header"' in content
    assert 'title.className = "chat-plain-role"' in content
    assert 'bubble.className = "chat-bubble agent revision-bubble"' in content
    revision_start = content.index('if (entry.type === "revision") {')
    revision_end = content.index('if (entry.type === "thinking") {')
    revision_block = content[revision_start:revision_end]
    assert 'roleEl.className = "chat-role"' not in revision_block


def test_run_observe_template_does_not_optimistically_append_chat_bubbles() -> None:
    content = _read_template()
    assert "appendChatBubble(\"user\"" not in content
    assert "response_preview" not in content
    assert "interaction.reply.accepted" not in content


def test_run_observe_template_supports_markdown_and_json_preview_modes() -> None:
    content = _read_template()
    assert "SkillRunnerFileExplorer" in content
    assert "mountFileExplorer" in content
    assert "/static/js/chat_markdown.js?v=20260415a" in content
    assert "/static/css/chat_markdown.css?v=20260415a" in content
    assert "SkillRunnerChatMarkdown.createRenderer()" in content
    assert "/static/vendor/katex/katex.min.js" in content
    assert "/static/vendor/markdown-it-texmath/texmath.min.js" in content
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
