## MODIFIED Requirements

### Requirement: Harness accepts Claude custom-provider model selection

The external runtime harness SHALL let Claude runs specify a strict custom provider model independently from the normal official model option.

#### Scenario: pass custom model to Claude harness

- **WHEN** a caller launches `agent_harness` with `engine=claude` and `--custom-model provider/model`
- **THEN** the harness MUST accept the argument
- **AND** it MUST forward the custom model through Claude runtime options
- **AND** non-Claude engines MUST reject `--custom-model`
