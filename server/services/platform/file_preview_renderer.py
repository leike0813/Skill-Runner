from __future__ import annotations

import importlib
import json
import re
from pathlib import Path
from typing import Any


PREVIEW_MAX_BYTES = 256 * 1024
TEXT_DECODE_CANDIDATES = (
    "utf-8",
    "utf-8-sig",
    "gb18030",
    "big5",
)

MARKDOWN_SUFFIXES = {".md", ".markdown", ".mdx"}
JSON_SUFFIXES = {".json"}
JSONL_SUFFIXES = {".jsonl"}
YAML_SUFFIXES = {".yaml", ".yml"}
TOML_SUFFIXES = {".toml"}
PYTHON_SUFFIXES = {".py", ".pyw"}
JAVASCRIPT_SUFFIXES = {".js", ".mjs", ".cjs", ".jsx"}

_BLEACH_TAGS = [
    "a",
    "p",
    "br",
    "hr",
    "strong",
    "em",
    "code",
    "pre",
    "blockquote",
    "ul",
    "ol",
    "li",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "table",
    "thead",
    "tbody",
    "tr",
    "th",
    "td",
]
_BLEACH_ATTRIBUTES: dict[str, list[str]] = {
    "a": ["href", "title", "rel", "target"],
    "code": ["class"],
    "th": ["colspan", "rowspan"],
    "td": ["colspan", "rowspan"],
}
_BLEACH_PROTOCOLS = ["http", "https", "mailto"]


def build_preview_payload(file_path: Path) -> dict[str, Any]:
    size = file_path.stat().st_size
    if size > PREVIEW_MAX_BYTES:
        return {
            "mode": "too_large",
            "content": None,
            "size": size,
            "meta": "无信息",
            "detected_format": "text",
            "rendered_html": None,
            "json_pretty": None,
        }
    data = file_path.read_bytes()
    return build_preview_payload_from_bytes(data=data, size=size, filename=file_path.name)


def build_preview_payload_from_bytes(
    *,
    data: bytes,
    size: int,
    filename: str | None = None,
) -> dict[str, Any]:
    if size > PREVIEW_MAX_BYTES:
        return {
            "mode": "too_large",
            "content": None,
            "size": size,
            "meta": "无信息",
            "detected_format": "text",
            "rendered_html": None,
            "json_pretty": None,
        }
    if is_binary_blob(data):
        return {
            "mode": "binary",
            "content": None,
            "size": size,
            "meta": "无信息",
            "detected_format": "text",
            "rendered_html": None,
            "json_pretty": None,
        }

    content, encoding = decode_text_blob(data)
    detected_format = detect_text_format(filename=filename, content=content)
    rendered_html: str | None = None
    json_pretty: str | None = None
    if detected_format == "markdown":
        rendered_html = render_markdown_safe(content)
    elif detected_format == "json":
        try:
            parsed = json.loads(content)
            json_pretty = json.dumps(parsed, ensure_ascii=False, indent=2)
            rendered_html = render_code_highlight(json_pretty, "json")
        except (json.JSONDecodeError, TypeError, ValueError):
            json_pretty = None
            detected_format = "text"
            rendered_html = render_code_highlight(content, "text")
    elif detected_format == "jsonl":
        rendered_html = render_jsonl_highlight(content)
    elif detected_format in {"yaml", "toml", "python", "javascript", "text"}:
        rendered_html = render_code_highlight(content, detected_format)

    return {
        "mode": "text",
        "content": content,
        "size": size,
        "meta": f"{size} bytes, {encoding}",
        "detected_format": detected_format,
        "rendered_html": rendered_html,
        "json_pretty": json_pretty,
    }


def detect_text_format(*, filename: str | None, content: str) -> str:
    suffix = Path(filename).suffix.lower() if isinstance(filename, str) and filename else ""
    if suffix in MARKDOWN_SUFFIXES:
        return "markdown"
    if suffix in JSON_SUFFIXES:
        return "json"
    if suffix in JSONL_SUFFIXES:
        return "jsonl"
    if suffix in YAML_SUFFIXES:
        return "yaml"
    if suffix in TOML_SUFFIXES:
        return "toml"
    if suffix in PYTHON_SUFFIXES:
        return "python"
    if suffix in JAVASCRIPT_SUFFIXES:
        return "javascript"
    if _looks_like_jsonl(content):
        return "jsonl"
    trimmed = content.lstrip()
    if trimmed.startswith("{") or trimmed.startswith("["):
        try:
            json.loads(content)
            return "json"
        except (json.JSONDecodeError, TypeError, ValueError):
            return "text"
    return "text"


def render_markdown_safe(content: str) -> str | None:
    markdown_module = _import_optional("markdown")
    bleach_module = _import_optional("bleach")
    if markdown_module is None or bleach_module is None:
        return None
    rendered = markdown_module.markdown(
        content,
        extensions=["fenced_code", "tables", "sane_lists", "nl2br"],
        output_format="html5",
    )
    cleaned = bleach_module.clean(
        rendered,
        tags=_BLEACH_TAGS,
        attributes=_BLEACH_ATTRIBUTES,
        protocols=_BLEACH_PROTOCOLS,
        strip=True,
    )
    return bleach_module.linkify(cleaned)


def render_code_highlight(content: str, format_name: str) -> str | None:
    pygments_module = _import_optional("pygments")
    lexers_module = _import_optional("pygments.lexers")
    formatters_module = _import_optional("pygments.formatters")
    if pygments_module is None or lexers_module is None or formatters_module is None:
        return None
    lexer_name_map = {
        "json": "json",
        "jsonl": "json",
        "yaml": "yaml",
        "toml": "toml",
        "python": "python",
        "javascript": "javascript",
        "text": "text",
    }
    lexer_name = lexer_name_map.get(format_name)
    if not lexer_name:
        return None
    try:
        lexer = lexers_module.get_lexer_by_name(lexer_name)
        formatter = formatters_module.HtmlFormatter(
            noclasses=True,
            linenos="table",
            lineanchors="L",
            nowrap=False,
            style="default",
        )
        highlighted = pygments_module.highlight(content, lexer, formatter)
        return _strip_inline_background_styles(highlighted)
    except (AttributeError, LookupError, TypeError, ValueError):
        return None


def render_jsonl_highlight(content: str) -> str | None:
    rendered_lines: list[str] = []
    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            rendered_lines.append("")
            continue
        try:
            parsed = json.loads(raw_line)
        except (json.JSONDecodeError, TypeError, ValueError):
            rendered_lines.append(raw_line)
            continue
        rendered_lines.append(json.dumps(parsed, ensure_ascii=False, indent=2))
    return render_code_highlight("\n".join(rendered_lines), "jsonl")


def _strip_inline_background_styles(html: str) -> str:
    if not isinstance(html, str) or not html:
        return ""
    no_bg = re.sub(r"background(?:-color)?\s*:\s*[^;\"']+;?", "", html, flags=re.IGNORECASE)
    return re.sub(r"style=\"\s+\"", "style=\"\"", no_bg)


def is_binary_blob(data: bytes) -> bool:
    sample = data[:4096]
    if not sample:
        return False
    if b"\x00" in sample:
        return True
    control_count = 0
    for byte in sample:
        if byte in {9, 10, 12, 13, 27}:
            continue
        if 32 <= byte <= 126:
            continue
        if byte >= 128:
            continue
        control_count += 1
    return (control_count / len(sample)) > 0.55


def decode_text_blob(data: bytes) -> tuple[str, str]:
    for encoding in TEXT_DECODE_CANDIDATES:
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace"), "utf-8-replace"


def _looks_like_jsonl(content: str) -> bool:
    lines = [line for line in content.splitlines() if line.strip()]
    if len(lines) < 2:
        return False
    valid_count = 0
    for line in lines:
        try:
            json.loads(line)
        except (json.JSONDecodeError, TypeError, ValueError):
            return False
        valid_count += 1
    return valid_count > 1


def _import_optional(module_name: str):
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError:
        return None
