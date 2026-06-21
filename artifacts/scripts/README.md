Forensic or one-off utility scripts live here.

These scripts are intentionally not part of the supported runtime/deployment surface.

## chat_replay_to_markdown.py

Render a `chat_replay.jsonl` audit stream as a human-readable Markdown transcript:

```bash
uv run --project="$HOME/.ar" --locked -- python artifacts/scripts/chat_replay_to_markdown.py \
  data/workspaces/<run-id>/.audit/<namespace>/chat_replay.jsonl \
  --full \
  -o data/workspaces/<run-id>/.audit/<namespace>/chat_replay.md
```
