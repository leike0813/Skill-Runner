from __future__ import annotations

from types import SimpleNamespace

import pytest

from server.engines.codebuddy.adapter.execution_adapter import CodeBuddyExecutionAdapter
from server.engines.codebuddy.secret_redaction import CodeBuddySecretRedactor, redact_codebuddy_text


def test_secret_redactor_masks_exact_and_pattern_secrets_with_equal_bytes() -> None:
    source = "用户 abc-用户 Bearer top-secret eyJabc.def.ghi?token=callback-secret"
    redacted = redact_codebuddy_text(source, secrets=("abc-用户",))

    assert len(redacted.encode("utf-8")) == len(source.encode("utf-8"))
    for secret in ("abc-用户", "top-secret", "eyJabc.def.ghi", "callback-secret"):
        assert secret not in redacted


def test_secret_redactor_detects_secret_split_across_chunks() -> None:
    redactor = CodeBuddySecretRedactor(secrets=("cross-chunk-token",))
    first = redactor.feed("before cross-")
    second = redactor.feed("chunk-token after\n")
    tail = redactor.flush()
    output = first + second + tail

    assert first == ""
    assert second
    assert tail == ""
    assert "cross-chunk-token" not in output
    assert len(output.encode("utf-8")) == len("before cross-chunk-token after\n".encode("utf-8"))


def test_secret_redactor_fails_closed_when_unterminated_record_exceeds_limit() -> None:
    redactor = CodeBuddySecretRedactor(secrets=(), max_pending_bytes=8)

    with pytest.raises(RuntimeError, match="pending byte limit"):
        redactor.feed("unterminated")


def test_execution_adapter_builds_post_auth_redactor_from_provider_credential(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.engines.codebuddy.adapter.execution_adapter.codebuddy_credential_store.get",
        lambda _provider_id: SimpleNamespace(token="provider-token", user_id="provider-user"),
    )

    redactor = CodeBuddyExecutionAdapter().create_output_redactor(
        options={"provider_id": "codebuddy-cn"},
        stream_name="stdout",
    )
    source = "token=provider-token user=provider-user"
    output = redactor.feed(source) + redactor.flush()

    assert "provider-token" not in output
    assert "provider-user" not in output
    assert len(output.encode("utf-8")) == len(source.encode("utf-8"))
