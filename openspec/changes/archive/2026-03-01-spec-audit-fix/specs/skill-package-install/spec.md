# skill-package-install Specification

## Purpose
定义 skill 包上传、根目录校验和异步安装的 API 约束。

## MODIFIED Requirements

### Requirement: Accept skill package upload for async install
The system SHALL provide an API endpoint to accept a skill package as a zip upload and initiate an asynchronous installation job.

#### Scenario: Create an async install job
- **WHEN** a client uploads a zip package to the skill-install endpoint
- **THEN** the system returns a unique install request identifier and initial status
