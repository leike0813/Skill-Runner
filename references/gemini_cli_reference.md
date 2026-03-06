# Gemini CLI Reference Guide

## 1. Overview
The Gemini CLI supports a **Headless Mode** designed for automation, making it suitable for the Agent Skill Runner.

## 2. Invocation modes
### 2.1 Headless Mode
- **Flag**: `--prompt` or `-p`
- **Example**: `gemini -p "Analyze this file" --output-format json`
- **Stdin Support**: `cat file.txt | gemini -p "Summarize"`

### 2.2 Output Formats
- **Text (Default)**: Human-readable string.
- **JSON**: Structured output including `response`, `stats`, and `error`.
  - **Flag**: `--output-format json`
  - **Schema**:
    ```json
    {
      "response": "The answer string...",
      "stats": { ... },
      "error": { "type": "...", "message": "..." }
    }
    ```
- **Stream JSON**: Real-time events (JSONL).
  - **Flag**: `--output-format stream-json`
  - **Useful for**: Monitoring timeouts or long-running tasks.

## 3. Configuration
### 3.1 Precedence
1. Command Link Args (Highest)
2. Env Vars
3. System/Project/User Settings Files

### 3.2 Settings File (`settings.json`)
- **Location**: `.gemini/settings.json` (Project) or custom path via `--config` (if supported, otherwise must rely on env or mount).
- **Key Fields**:
  - `model.name`: e.g. `gemini-2.5-pro`
  - `output.format`: `json`
  - `tools.autoAccept`: `true` (Crucial for automation)
  - `security.disableYoloMode`: `false` (Enable YOLO for no confirmations)

### 3.3 Environment Variables
- `GEMINI_API_KEY`: Auth token.
- Strings in `settings.json` can reference vars: `"apiKey": "$GEMINI_API_KEY"`.

## 4. Key Automation Flags
- `--yolo` (`-y`): Auto-approve all actions (Essential for headless tool use).
- `--include-directories`: Whitelist dirs for read access.
- `--model`: Force specific model.

## 5. Input Context
- **Files**: `@path/to/file` in prompt.
- **Stdin**: Pipe content directly.

## 6. Development Tips
- **Exit Codes**: Headless mode provides consistent exit codes.
- **Debugging**: Use `--debug` to trace issues.
- **Tool Truncation**: Settings allow truncating large tool outputs (`tools.truncateToolOutputThreshold`).
