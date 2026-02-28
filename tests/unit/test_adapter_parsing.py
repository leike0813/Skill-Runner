import json

from server.engines.gemini.adapter.execution_adapter import GeminiExecutionAdapter
from server.engines.codex.adapter.execution_adapter import CodexExecutionAdapter
from server.engines.iflow.adapter.execution_adapter import IFlowExecutionAdapter
from server.engines.opencode.adapter.execution_adapter import OpencodeExecutionAdapter
from server.models import AdapterTurnOutcome


def test_gemini_parse_output_from_envelope():
    adapter = GeminiExecutionAdapter()
    raw = json.dumps({"response": "```json\n{\"a\": 1}\n```"})
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"a": 1}
    assert result.repair_level == "deterministic_generic"


def test_gemini_parse_output_from_text():
    adapter = GeminiExecutionAdapter()
    raw = "prefix {\"x\": 2} suffix"
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"x": 2}
    assert result.repair_level == "deterministic_generic"


def test_codex_parse_output_from_stream_event():
    adapter = CodexExecutionAdapter()
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
    adapter = CodexExecutionAdapter()
    raw = "noise {\"done\": true} tail"
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"done": True}
    assert result.repair_level == "deterministic_generic"


def test_iflow_parse_output_from_code_fence():
    adapter = IFlowExecutionAdapter()
    raw = "```json\n{\"value\": 2}\n```"
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"value": 2}
    assert result.repair_level == "deterministic_generic"


def test_iflow_parse_output_from_raw_text():
    adapter = IFlowExecutionAdapter()
    raw = "start {\"v\": 3} end"
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"v": 3}
    assert result.repair_level == "deterministic_generic"


def test_gemini_parse_output_strict_json_without_repair():
    adapter = GeminiExecutionAdapter()
    raw = "{\"ok\": true}"
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"ok": True}
    assert result.repair_level == "none"


def test_opencode_parse_output_from_stream_text_event():
    adapter = OpencodeExecutionAdapter()
    raw = '{"type":"text","part":{"text":"```json\\n{\\"ok\\": true}\\n```"}}\n'
    result = adapter._parse_output(raw)
    assert result.outcome == AdapterTurnOutcome.FINAL
    assert result.final_data == {"ok": True}
    assert result.repair_level == "deterministic_generic"
