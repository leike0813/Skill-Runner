import json

from server.adapters.gemini_adapter import GeminiAdapter
from server.adapters.codex_adapter import CodexAdapter
from server.adapters.iflow_adapter import IFlowAdapter


def test_gemini_parse_output_from_envelope():
    adapter = GeminiAdapter()
    raw = json.dumps({"response": "```json\n{\"a\": 1}\n```"})
    result, repair_level = adapter._parse_output(raw)
    assert result == {"a": 1}
    assert repair_level == "deterministic_generic"


def test_gemini_parse_output_from_text():
    adapter = GeminiAdapter()
    raw = "prefix {\"x\": 2} suffix"
    result, repair_level = adapter._parse_output(raw)
    assert result == {"x": 2}
    assert repair_level == "deterministic_generic"


def test_codex_parse_output_from_stream_event():
    adapter = CodexAdapter()
    event = {
        "type": "item.completed",
        "item": {"type": "agent_message", "text": "```json\n{\"ok\": true}\n```"}
    }
    raw = json.dumps(event)
    result, repair_level = adapter._parse_output(raw)
    assert result == {"ok": True}
    assert repair_level == "deterministic_generic"


def test_codex_parse_output_from_raw_text():
    adapter = CodexAdapter()
    raw = "noise {\"done\": true} tail"
    result, repair_level = adapter._parse_output(raw)
    assert result == {"done": True}
    assert repair_level == "deterministic_generic"


def test_iflow_parse_output_from_code_fence():
    adapter = IFlowAdapter()
    raw = "```json\n{\"value\": 2}\n```"
    result, repair_level = adapter._parse_output(raw)
    assert result == {"value": 2}
    assert repair_level == "deterministic_generic"


def test_iflow_parse_output_from_raw_text():
    adapter = IFlowAdapter()
    raw = "start {\"v\": 3} end"
    result, repair_level = adapter._parse_output(raw)
    assert result == {"v": 3}
    assert repair_level == "deterministic_generic"


def test_gemini_parse_output_strict_json_without_repair():
    adapter = GeminiAdapter()
    raw = "{\"ok\": true}"
    result, repair_level = adapter._parse_output(raw)
    assert result == {"ok": True}
    assert repair_level == "none"
