from datetime import datetime, timedelta, timezone

from server.engines.opencode.auth.drivers.cli_delegate_flow import (
    OpencodeAuthCliFlow,
    OpencodeAuthCliSession,
)


def test_opencode_auth_cli_flow_extract_menu_options():
    flow = OpencodeAuthCliFlow()
    selected, options = flow._extract_menu_options(  # noqa: SLF001
        "\n".join(
            [
                "● OpenCode Zen (recommended)",
                "○ Anthropic",
                "○ OpenAI",
                "○ Google",
            ]
        )
    )
    assert selected == 1
    assert options[2] == "OpenAI"
    assert options[3] == "Google"


def test_opencode_auth_cli_flow_extract_auth_url():
    flow = OpencodeAuthCliFlow()
    text = (
        "OAuth URL:\n"
        "https://accounts.google.com/o/oauth2/v2/auth?redirect_uri=https%3A%2F%2Fcodeassist.google.com%2Fauthcode\n"
        "Paste the redirect URL (or just the code) here:\n"
    )
    url = flow._extract_auth_url(text)  # noqa: SLF001
    assert url is not None
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth")


def test_opencode_auth_cli_flow_extract_auth_url_ignores_guidance_text():
    flow = OpencodeAuthCliFlow()
    text = (
        "OAuth URL:\n"
        "https://accounts.google.com/o/oauth2/v2/auth?client_id=abc&prompt=consent\n"
        "Could not open browser automatically. Please open the URL above manually in your local browser.\n"
        "1. Open the URL above in your browser and complete Google sign-in.\n"
        "2. After approving, copy the full redirected localhost URL from the address bar.\n"
        "3. Paste it back here\n"
        "Paste the redirect URL (or just the code) here:\n"
    )
    url = flow._extract_auth_url(text)  # noqa: SLF001
    assert url == "https://accounts.google.com/o/oauth2/v2/auth?client_id=abc&prompt=consent"


def test_opencode_auth_cli_flow_extract_generic_openai_go_to_url():
    flow = OpencodeAuthCliFlow()
    text = (
        "Login method\n"
        "●  Go to: https://auth.openai.com/oauth/authorize?state=abc123&originator=opencode\n"
        "●  Complete authorization in your browser. This window will close automatically.\n"
        "◒  Waiting for authorization\n"
    )
    url = flow._extract_generic_auth_url(text)  # noqa: SLF001
    assert url is not None
    assert url.startswith("https://auth.openai.com/oauth/authorize?")


def test_opencode_auth_cli_flow_success_anchor():
    flow = OpencodeAuthCliFlow()
    assert flow._is_success_output("loginsuccessful")  # noqa: SLF001
    assert not flow._is_success_output("waitingforauthorization")  # noqa: SLF001


def test_opencode_auth_cli_flow_openai_waiting_anchor_without_url(tmp_path):
    class _AliveProcess:
        def poll(self):
            return None

    flow = OpencodeAuthCliFlow()
    output_path = tmp_path / "opencode_provider_auth.log"
    output_path.touch()
    now = datetime.now(timezone.utc)
    session = OpencodeAuthCliSession(
        session_id="sess-openai",
        process=_AliveProcess(),
        master_fd=0,
        output_path=output_path,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(minutes=15),
        provider_id="openai",
        provider_label="OpenAI",
        status="waiting_orchestrator",
    )

    flow._append_output_locked(session, "Waiting for authorization\n")  # noqa: SLF001
    flow._consume_output_locked(session)  # noqa: SLF001

    assert session.auth_url is None
    assert session.status == "waiting_user"


def test_opencode_auth_cli_flow_google_redirect_prompt_after_submit_allows_success(tmp_path):
    class _AliveProcess:
        def poll(self):
            return None

    flow = OpencodeAuthCliFlow()
    output_path = tmp_path / "opencode_provider_auth.log"
    output_path.touch()
    now = datetime.now(timezone.utc)
    session = OpencodeAuthCliSession(
        session_id="sess-google",
        process=_AliveProcess(),
        master_fd=0,
        output_path=output_path,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(minutes=15),
        provider_id="google",
        provider_label="Google",
        status="code_submitted_waiting_result",
        input_submitted=True,
    )

    flow._append_output_locked(  # noqa: SLF001
        session,
        (
            "Paste the redirect URL (or just the code) here:\n"
            "●  Login successful\n"
        ),
    )
    flow._consume_output_locked(session)  # noqa: SLF001

    assert session.status == "succeeded"


def test_opencode_auth_cli_flow_google_auto_decline_add_another_account(tmp_path):
    class _AliveProcess:
        def poll(self):
            return None

    flow = OpencodeAuthCliFlow()
    writes: list[str] = []
    flow._write_input_locked = lambda _session, text: writes.append(text)  # type: ignore[method-assign]

    output_path = tmp_path / "opencode_provider_auth.log"
    output_path.touch()
    now = datetime.now(timezone.utc)
    session = OpencodeAuthCliSession(
        session_id="sess-google-add-account",
        process=_AliveProcess(),
        master_fd=0,
        output_path=output_path,
        created_at=now,
        updated_at=now,
        expires_at=now + timedelta(minutes=15),
        provider_id="google",
        provider_label="Google",
        status="code_submitted_waiting_result",
        input_submitted=True,
    )

    flow._append_output_locked(session, "Add another account? (1 added) (y/n):\n")  # noqa: SLF001
    flow._consume_output_locked(session)  # noqa: SLF001

    assert "n\r" in writes
    assert session.add_another_account_declined is True
