from __future__ import annotations

import pytest

from server.services.platform import file_preview_renderer as renderer


def test_build_preview_payload_from_bytes_marks_binary() -> None:
    preview = renderer.build_preview_payload_from_bytes(
        data=b"\x00\x01\x02",
        size=3,
        filename="artifact.bin",
    )
    assert preview["mode"] == "binary"
    assert preview["detected_format"] == "text"
    assert preview["content"] is None


def test_build_preview_payload_from_bytes_marks_too_large() -> None:
    size = renderer.PREVIEW_MAX_BYTES + 1
    preview = renderer.build_preview_payload_from_bytes(
        data=b"x" * size,
        size=size,
        filename="large.txt",
    )
    assert preview["mode"] == "too_large"
    assert preview["detected_format"] == "text"


def test_build_preview_payload_from_bytes_json_pretty() -> None:
    preview = renderer.build_preview_payload_from_bytes(
        data=b'{"ok":true,"nested":{"value":1}}',
        size=31,
        filename="result.json",
    )
    assert preview["mode"] == "text"
    assert preview["detected_format"] == "json"
    assert '"ok": true' in (preview["json_pretty"] or "")


def test_build_preview_payload_from_bytes_code_highlight_for_structured_formats(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakePygmentsModule:
        @staticmethod
        def highlight(content: str, lexer: object, formatter: object) -> str:
            _ = formatter
            return f"<pre data-lexer='{lexer}'>{content}</pre>"

    class _FakeLexersModule:
        @staticmethod
        def get_lexer_by_name(name: str) -> str:
            return name

    class _FakeFormattersModule:
        class HtmlFormatter:
            def __init__(self, **_: object) -> None:
                pass

    def _fake_import_optional(module_name: str):
        if module_name == "pygments":
            return _FakePygmentsModule
        if module_name == "pygments.lexers":
            return _FakeLexersModule
        if module_name == "pygments.formatters":
            return _FakeFormattersModule
        return None

    monkeypatch.setattr(renderer, "_import_optional", _fake_import_optional)

    yaml_preview = renderer.build_preview_payload_from_bytes(
        data=b"name: demo\nactive: true\n",
        size=24,
        filename="config.yaml",
    )
    assert yaml_preview["detected_format"] == "yaml"
    assert "data-lexer='yaml'" in (yaml_preview["rendered_html"] or "")

    toml_preview = renderer.build_preview_payload_from_bytes(
        data=b'[tool]\nname = "demo"\n',
        size=21,
        filename="pyproject.toml",
    )
    assert toml_preview["detected_format"] == "toml"
    assert "data-lexer='toml'" in (toml_preview["rendered_html"] or "")

    py_preview = renderer.build_preview_payload_from_bytes(
        data=b"def f():\n    return 1\n",
        size=22,
        filename="app.py",
    )
    assert py_preview["detected_format"] == "python"
    assert "data-lexer='python'" in (py_preview["rendered_html"] or "")

    js_preview = renderer.build_preview_payload_from_bytes(
        data=b"const x = 1;\n",
        size=13,
        filename="app.js",
    )
    assert js_preview["detected_format"] == "javascript"
    assert "data-lexer='javascript'" in (js_preview["rendered_html"] or "")


def test_build_preview_payload_from_bytes_markdown_sanitized(monkeypatch: pytest.MonkeyPatch) -> None:
    class _FakeMarkdownModule:
        @staticmethod
        def markdown(content: str, **_: object) -> str:
            assert content.startswith("# Heading")
            return "<h1>Heading</h1><script>alert(1)</script><p>safe</p>"

    class _FakeBleachModule:
        @staticmethod
        def clean(content: str, **_: object) -> str:
            return content.replace("<script>alert(1)</script>", "")

        @staticmethod
        def linkify(content: str) -> str:
            return content

    def _fake_import_optional(module_name: str):
        if module_name == "markdown":
            return _FakeMarkdownModule
        if module_name == "bleach":
            return _FakeBleachModule
        return None

    monkeypatch.setattr(renderer, "_import_optional", _fake_import_optional)

    preview = renderer.build_preview_payload_from_bytes(
        data=b"# Heading\n\nsafe",
        size=len(b"# Heading\n\nsafe"),
        filename="README.md",
    )
    assert preview["mode"] == "text"
    assert preview["detected_format"] == "markdown"
    assert isinstance(preview["rendered_html"], str)
    assert "<script>" not in preview["rendered_html"]
    assert "<h1>Heading</h1>" in preview["rendered_html"]
