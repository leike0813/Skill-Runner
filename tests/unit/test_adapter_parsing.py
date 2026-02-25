import json

from server.adapters.gemini_adapter import GeminiAdapter
from server.adapters.codex_adapter import CodexAdapter
from server.adapters.iflow_adapter import IFlowAdapter
from server.adapters.opencode_adapter import OpencodeAdapter
from server.models import AdapterTurnOutcome


def test_gemini_parse_output_from_envelope():
    adapter = GeminiAdapter()
    raw = json.dumps({"response": "```json\n{\"a\": 1}\n```"})
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"a": 1}
    assert result.repair_level == "deterministic_generic"


def test_gemini_parse_output_from_text():
    adapter = GeminiAdapter()
    raw = "prefix {\"x\": 2} suffix"
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"x": 2}
    assert result.repair_level == "deterministic_generic"


def test_codex_parse_output_from_stream_event():
    adapter = CodexAdapter()
    event = {
        "type": "item.completed",
        "item": {"type": "agent_message", "text": "```json\n{\"ok\": true}\n```"}
    }
    raw = json.dumps(event)
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"ok": True}
    assert result.repair_level == "deterministic_generic"


def test_codex_parse_output_from_raw_text():
    adapter = CodexAdapter()
    raw = "noise {\"done\": true} tail"
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"done": True}
    assert result.repair_level == "deterministic_generic"


def test_iflow_parse_output_from_code_fence():
    adapter = IFlowAdapter()
    raw = "```json\n{\"value\": 2}\n```"
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"value": 2}
    assert result.repair_level == "deterministic_generic"


def test_iflow_parse_output_from_raw_text():
    adapter = IFlowAdapter()
    raw = "start {\"v\": 3} end"
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"v": 3}
    assert result.repair_level == "deterministic_generic"


def test_gemini_parse_output_strict_json_without_repair():
    adapter = GeminiAdapter()
    raw = "{\"ok\": true}"
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"ok": True}
    assert result.repair_level == "none"


def test_opencode_parse_output_from_stream_text_event():
    adapter = OpencodeAdapter()
    raw = '{"type":"text","part":{"text":"```json\\n{\\"ok\\": true}\\n```"}}\n'
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"ok": True}
    assert result.repair_level == "deterministic_generic"
