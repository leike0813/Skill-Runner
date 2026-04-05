from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run_chat_model_script(source: str) -> dict:
    completed = subprocess.run(
        ["node", "-e", source],
        check=True,
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    return json.loads(completed.stdout)


def test_chat_thinking_core_switches_assistant_intermediate_between_plain_and_bubble() -> None:
    script = """
const fs = require("fs");
const vm = require("vm");
const code = fs.readFileSync("server/assets/static/js/chat_thinking_core.js", "utf8");
const sandbox = { window: {} };
vm.createContext(sandbox);
vm.runInContext(code, sandbox);
const core = sandbox.window.SkillRunnerThinkingChatCore;
const model = core.createThinkingChatModel("plain");
model.consume({
  role: "assistant",
  kind: "assistant_message",
  text: "draft reply",
  attempt: 1,
  correlation: { message_id: "msg-1" },
});
const plainEntries = model.getEntries();
model.setDisplayMode("bubble");
const bubbleEntries = model.getEntries();
process.stdout.write(JSON.stringify({ plainEntries, bubbleEntries }));
"""
    payload = _run_chat_model_script(script)
    assert payload["plainEntries"][0]["type"] == "message"
    assert payload["bubbleEntries"][0]["type"] == "thinking"
    assert payload["bubbleEntries"][0]["items"][0]["itemKind"] == "assistant_message"


def test_chat_thinking_core_dedupes_final_message_by_stable_message_id() -> None:
    script = """
const fs = require("fs");
const vm = require("vm");
const code = fs.readFileSync("server/assets/static/js/chat_thinking_core.js", "utf8");
const sandbox = { window: {} };
vm.createContext(sandbox);
vm.runInContext(code, sandbox);
const core = sandbox.window.SkillRunnerThinkingChatCore;
const model = core.createThinkingChatModel("bubble");
model.consume({
  role: "assistant",
  kind: "assistant_message",
  text: "draft reply",
  attempt: 1,
  correlation: { message_id: "msg-1" },
});
model.consume({
  role: "assistant",
  kind: "assistant_final",
  text: "final reply",
  attempt: 1,
  correlation: { message_id: "msg-1" },
});
model.consume({
  role: "assistant",
  kind: "assistant_final",
  text: "final reply",
  attempt: 1,
  correlation: { message_id: "msg-1" },
});
process.stdout.write(JSON.stringify(model.getEntries()));
"""
    entries = _run_chat_model_script(script)
    assert len(entries) == 1
    assert entries[0]["type"] == "message"
    assert entries[0]["event"]["kind"] == "assistant_final"


def test_chat_thinking_core_uses_replaces_message_id_for_final_dedup() -> None:
    script = """
const fs = require("fs");
const vm = require("vm");
const code = fs.readFileSync("server/assets/static/js/chat_thinking_core.js", "utf8");
const sandbox = { window: {} };
vm.createContext(sandbox);
vm.runInContext(code, sandbox);
const core = sandbox.window.SkillRunnerThinkingChatCore;
const model = core.createThinkingChatModel("plain");
model.consume({
  role: "assistant",
  kind: "assistant_message",
  text: "draft reply",
  attempt: 1,
  correlation: { message_id: "msg-1" },
});
model.consume({
  role: "assistant",
  kind: "assistant_final",
  text: "final reply",
  attempt: 1,
  correlation: { message_id: "final-1", replaces_message_id: "msg-1" },
});
process.stdout.write(JSON.stringify(model.getEntries()));
"""
    entries = _run_chat_model_script(script)
    assert len(entries) == 1
    assert entries[0]["event"]["kind"] == "assistant_final"


def test_chat_thinking_core_switch_projection_is_based_on_canonical_events() -> None:
    script = """
const fs = require("fs");
const vm = require("vm");
const code = fs.readFileSync("server/assets/static/js/chat_thinking_core.js", "utf8");
const sandbox = { window: {} };
vm.createContext(sandbox);
vm.runInContext(code, sandbox);
const core = sandbox.window.SkillRunnerThinkingChatCore;
const model = core.createThinkingChatModel("plain");
model.consume({
  role: "assistant",
  kind: "assistant_process",
  text: "thinking step",
  attempt: 1,
  correlation: { process_type: "reasoning", message_id: "proc-1" },
});
model.consume({
  role: "assistant",
  kind: "assistant_message",
  text: "draft reply",
  attempt: 1,
  correlation: { message_id: "msg-1" },
});
const plainEntries = model.getEntries();
model.setDisplayMode("bubble");
const bubbleEntries = model.getEntries();
model.setDisplayMode("plain");
const plainEntriesAgain = model.getEntries();
process.stdout.write(JSON.stringify({ plainEntries, bubbleEntries, plainEntriesAgain }));
"""
    payload = _run_chat_model_script(script)
    assert [entry["type"] for entry in payload["plainEntries"]] == ["thinking", "message"]
    assert [entry["type"] for entry in payload["bubbleEntries"]] == ["thinking"]
    assert payload["bubbleEntries"][0]["items"][1]["itemKind"] == "assistant_message"
    assert payload["plainEntriesAgain"] == payload["plainEntries"]
