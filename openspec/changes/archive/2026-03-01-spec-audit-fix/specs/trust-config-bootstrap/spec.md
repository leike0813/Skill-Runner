# trust-config-bootstrap Specification

## Purpose
定义容器启动时 trust 配置文件的 bootstrap 和 trusted parent run 目录初始化策略。

## MODIFIED Requirements

### Requirement: Bootstrap trust config files at container startup
At container startup, the system MUST ensure trust configuration artifacts required by Codex and Gemini exist and are valid.

#### Scenario: Create missing Gemini trusted folders file
- **WHEN** `~/.gemini/trustedFolders.json` does not exist
- **THEN** the system creates the file with a top-level JSON object (`{}`)

#### Scenario: Repair invalid Gemini trusted folders file
- **WHEN** `~/.gemini/trustedFolders.json` exists but is not a valid JSON object
- **THEN** the system repairs it to a valid JSON object and preserves a backup of the previous content
