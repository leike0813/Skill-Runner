# skill-converter-agent Specification

## Purpose
定义 converter skill 的输入接受、interactive 决策流和 agent 驱动转换约束。

## MODIFIED Requirements

### Requirement: Converter skill accepts an existing generic skill package as input
The converter skill SHALL accept a source skill package and use it as the input for conversion.

#### Scenario: Convert from provided source package
- **WHEN** the user provides a valid source skill package path or archive
- **THEN** the converter loads that package and starts conversion analysis
