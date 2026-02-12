# AGENTS.md — Agent Skill Runner

## Overview
**Skill Runner** is a lightweight, production-grade REST service that wraps mature CLI agent runtimes (**Codex**, **Gemini**, **iFlow**) and exposes them as fully-automated, stateful "skills".
It serves as a bridge between LLM-based agentic capabilities and traditional automation pipelines, ensuring **deterministic execution**, **structured outputs**, and **artifact management**.

## Core Capabilities

### 1. Multi-Engine Support
The runner supports three distinct execution engines, selectable at runtime:
- **Codex CLI** (`codex`): Optimized for precision coding tasks and legacy automation. Uses `toml` configuration profiles.
- **Gemini CLI** (`gemini`): Google's advanced multimodal agent runtime. Uses JSON-based configuration.
- **iFlow CLI** (`iflow`): Agentic runtime with project-level isolation. Uses JSON-based configuration.

### 2. Skill Protocol
Skills are self-contained directories following a strict contract:
- **Manifest** (`assets/runner.json`): Defines runtime requirements, entrypoints, and ownership.
- **Schemas**: 
    - `input.schema.json`: Validation for file inputs (`x-type: file`).
    - `input-params.schema.json`: Validation for scalar parameters.
    - `output.schema.json`:  Validation for the returned JSON result.
- **Artifacts**: Automatic detection and harvesting of generated files.

### 3. Execution Lifecycle
1.  **Submission**: Client POSTs to `/runs` with a skill ID, engine selection, parameters, and input files (Zip).
2.  **Orchestration**:
    - **Validation**: Inputs and Parameters are validated against the skill's schemas.
    - **Context Injection**: Runner generates a deterministic prompt using Jinja2 templates (`{{ input.file }}`, `{{ parameter.value }}`).
    - **Configuration Fusion**: Merges skill defaults, user options, and system-enforced policies (e.g., sandbox settings).
3.  **Execution**: The selected adapter executes the CLI agent in a dedicated, isolated workspace (`data/runs/{uuid}`).
4.  **Harvesting**:
    - Captures `stdout`/`stderr` logs.
    - Parses structured JSON output against schema.
    - Collects generated artifacts.
5.  **Result**: Returns a standardized JSON response with status, result data, and artifact manifest.

### 4. File Management Protocol
- **Input**: Files are uploaded as a Zip archive. The runner extracts them to `uploads/` and maps them to prompt variables using **Strict Key Matching** (Zip filename must match schema key).
- **Output**: Artifacts are generated in the run workspace and exposed via distinct download endpoints.

## Architecture

```
Client  ->  [ REST API ]  ->  [ Job Orchestrator ]
                                      |
                   +------------------+------------------+
                   |                  |                  |
           [ CodexAdapter ]   [ GeminiAdapter ]   [ IFlowAdapter ]
                   |                  |                  |
               (Process)          (Process)          (Process)
```

- **Services**: `SkillRegistry`, `WorkspaceManager`, `ConfigGenerator`, `SchemaValidator`.
- **Configuration**: Uses `YACS` for global config and `jsonschema` for granular validation.
- **Testing**: Includes a table-driven integration test framework (`tests/suites/*.yaml`) supporting multi-engine verification.

## Status
- **Milestones Completed**: 1-16
- **Current Version**: v0.2.0
