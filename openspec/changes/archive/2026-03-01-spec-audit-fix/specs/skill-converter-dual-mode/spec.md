# skill-converter-dual-mode Specification

## Purpose
定义 converter 同时支持目录源和 zip 源输入的约束。

## MODIFIED Requirements

### Requirement: Converter supports directory source input
The converter SHALL accept a local skill directory as source input for interactive-first conversion workflows.

#### Scenario: Convert from local directory
- **WHEN** the user provides a valid local source skill directory
- **THEN** the converter analyzes and converts that directory without requiring source zip upload
