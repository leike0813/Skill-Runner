# ephemeral-skill-lifecycle Specification

## Purpose
定义临时 skill 资产在 run 终态后的自动清理生命周期。

## MODIFIED Requirements

### Requirement: Temporary skill assets must be deleted after terminal run state
The system SHALL remove temporary skill package files and extracted temporary skill content after the associated run reaches a terminal state.

#### Scenario: Cleanup after successful execution
- **WHEN** a temporary-skill run reaches `succeeded`
- **THEN** the system removes temporary-skill staging and package files for that request
