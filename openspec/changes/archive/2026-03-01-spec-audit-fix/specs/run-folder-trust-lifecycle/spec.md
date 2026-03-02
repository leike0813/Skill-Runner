# run-folder-trust-lifecycle Specification

## Purpose
定义 Codex/Gemini 的 run folder trust 注册/移除生命周期和 iFlow 的无操作行为。

## MODIFIED Requirements

### Requirement: Register and remove run folder trust for Codex and Gemini
The system MUST register trust for the current `run_dir` before invoking Codex or Gemini, and MUST remove the same trust record after execution completes.

#### Scenario: Codex run registers trust before execution
- **WHEN** a job is scheduled with engine `codex` and a resolved run directory
- **THEN** the system writes `projects."<run_dir>".trust_level = "trusted"` to Codex global config before starting Codex CLI

#### Scenario: Gemini run registers trust before execution
- **WHEN** a job is scheduled with engine `gemini` and a resolved run directory
- **THEN** the system writes `"<run_dir>": "TRUST_FOLDER"` into `~/.gemini/trustedFolders.json` before starting Gemini CLI

#### Scenario: Trust is removed after successful execution
- **WHEN** Codex or Gemini execution finishes successfully
- **THEN** the system removes the run directory trust entry from the corresponding global config

#### Scenario: Trust is removed after failed execution
- **WHEN** Codex or Gemini execution exits with error or raises exception
- **THEN** the system still attempts trust-entry removal in a finally-path cleanup
