# ephemeral-skill-upload-and-run Specification

## Purpose
定义临时 skill 的两步上传-执行 API 和文件接受约束。

## MODIFIED Requirements

### Requirement: Two-step temporary run API
The system SHALL provide two-step endpoints under `/v1/temp-skill-runs` for temporary skill execution.

#### Scenario: Create temporary run request
- **WHEN** a client submits a create request to `/v1/temp-skill-runs`
- **THEN** the system returns a unique temporary request identifier
