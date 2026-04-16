from __future__ import annotations

import json
import subprocess
from pathlib import Path


def _run_chat_model_script(source: str) -> dict | list:
    completed = subprocess.run(
        ["node", "-e", source],
        check=True,
        capture_output=True,
        text=True,
        cwd=Path.cwd(),
    )
    return json.loads(completed.stdout)


def test_chat_thinking_core_keeps_e2e_bubble_semantics_for_intermediate_and_process() -> None:
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
  kind: "assistant_process",
  text: "thinking step",
  attempt: 1,
  correlation: { message_id: "proc-1", process_type: "reasoning" },
});
model.consume({
  role: "assistant",
  kind: "assistant_message",
  text: "draft reply",
  attempt: 1,
  correlation: { message_id: "msg-1", message_family_id: "family-1" },
});
process.stdout.write(JSON.stringify(model.getEntries()));
"""
    entries = _run_chat_model_script(script)
    assert len(entries) == 1
    assert entries[0]["type"] == "thinking"
    assert [item["itemKind"] for item in entries[0]["items"]] == [
        "assistant_process",
        "assistant_message",
    ]


def test_chat_thinking_core_promotes_bubble_generation_to_final() -> None:
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
  correlation: { message_id: "item-1", message_family_id: "family-1" },
});
model.consume({
  role: "assistant",
  kind: "assistant_final",
  text: "winner final",
  attempt: 1,
  correlation: { message_id: "item-1", message_family_id: "family-1", replaces_message_id: "item-1" },
});
process.stdout.write(JSON.stringify(model.getEntries()));
"""
    entries = _run_chat_model_script(script)
    assert len(entries) == 1
    assert entries[0]["type"] == "message"
    assert entries[0]["event"]["kind"] == "assistant_final"
    assert entries[0]["event"]["text"] == "winner final"


def test_chat_thinking_core_turns_superseded_final_into_folded_revision() -> None:
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
  kind: "assistant_final",
  text: "invalid final",
  attempt: 1,
  correlation: { message_id: "msg-1", message_family_id: "family-1" },
});
model.consume({
  role: "assistant",
  kind: "assistant_revision",
  text: "",
  attempt: 1,
  correlation: { message_id: "msg-1", message_family_id: "family-1", reason: "output_repair_started" },
});
model.consume({
  role: "assistant",
  kind: "assistant_final",
  text: "winner final",
  attempt: 1,
  correlation: { message_id: "msg-2", message_family_id: "family-1" },
});
process.stdout.write(JSON.stringify(model.getEntries()));
"""
    entries = _run_chat_model_script(script)
    assert [entry["type"] for entry in entries] == ["revision", "message"]
    assert entries[0]["originalEvent"]["text"] == "invalid final"
    assert entries[0]["collapsed"] is True
    assert entries[1]["event"]["text"] == "winner final"


def test_chat_thinking_core_starts_new_generation_after_supersede() -> None:
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
  kind: "assistant_final",
  text: "invalid final",
  attempt: 3,
  correlation: { message_id: "item_1", message_family_id: "item_1" },
});
model.consume({
  role: "assistant",
  kind: "assistant_revision",
  text: "",
  attempt: 3,
  correlation: { message_id: "item_1", message_family_id: "item_1", reason: "output_repair_started" },
});
model.consume({
  role: "assistant",
  kind: "assistant_message",
  text: "我在核对当前 run 的机器输出 schema，确认为什么引擎把这一轮判成 pending 分支。",
  attempt: 3,
  correlation: { message_id: "item_1", message_family_id: "item_1" },
});
process.stdout.write(JSON.stringify(model.getEntries()));
"""
    entries = _run_chat_model_script(script)
    assert [entry["type"] for entry in entries] == ["revision", "thinking"]
    assert entries[1]["items"][0]["itemKind"] == "assistant_message"
    assert entries[1]["items"][0]["text"] == "我在核对当前 run 的机器输出 schema，确认为什么引擎把这一轮判成 pending 分支。"


def test_chat_thinking_core_keeps_process_bubble_after_final_promotes_same_chain_message() -> None:
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
  kind: "assistant_process",
  text: "checking schema",
  attempt: 1,
  correlation: { message_id: "proc-1", process_type: "reasoning" },
});
model.consume({
  role: "assistant",
  kind: "assistant_message",
  text: "draft reply",
  attempt: 1,
  correlation: { message_id: "msg-1", message_family_id: "family-1" },
});
model.consume({
  role: "assistant",
  kind: "assistant_final",
  text: "winner final",
  attempt: 1,
  correlation: { message_id: "msg-1", message_family_id: "family-1", replaces_message_id: "msg-1" },
});
process.stdout.write(JSON.stringify(model.getEntries()));
"""
    entries = _run_chat_model_script(script)
    assert [entry["type"] for entry in entries] == ["thinking", "message"]
    assert [item["itemKind"] for item in entries[0]["items"]] == ["assistant_process"]
    assert entries[1]["event"]["kind"] == "assistant_final"


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
  correlation: { message_id: "msg-1", message_family_id: "family-1" },
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
