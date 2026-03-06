import io
import zipfile

from e2e_client.routes import _build_bundle_file_preview


def test_e2e_bundle_preview_gb18030_markdown_is_text():
    payload = "## TL;DR\n\n这是一个中文段落。".encode("gb18030")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("result/report.md", payload)
    preview = _build_bundle_file_preview(buffer.getvalue(), "result/report.md")
    assert preview["mode"] == "text"
    assert preview["detected_format"] == "markdown"
    assert "中文段落" in preview["content"]


def test_e2e_bundle_preview_json_pretty():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("result/result.json", '{"answer":"ok","nested":{"x":1}}')
    preview = _build_bundle_file_preview(buffer.getvalue(), "result/result.json")
    assert preview["mode"] == "text"
    assert preview["detected_format"] == "json"
    assert isinstance(preview["json_pretty"], str)
    assert '"answer": "ok"' in preview["json_pretty"]
