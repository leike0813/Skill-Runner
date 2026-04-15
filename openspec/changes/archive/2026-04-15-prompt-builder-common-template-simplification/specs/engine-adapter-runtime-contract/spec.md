## ADDED Requirements

### Requirement: Prompt builder profiles MUST declare invoke-line and optional default-body extra blocks only
系统 MUST 将 adapter profile 中的 prompt builder 配置收口为 skill 调用首行模板与默认 body 前后 extra block，禁止继续声明旧的 body-template fallback、parameter-prompt、params-json、skill-dir 注入开关。

#### Scenario: adapter profile declares prompt builder
- **WHEN** 系统加载某引擎的 `adapter_profile.json`
- **THEN** `prompt_builder` MUST 至少声明 `skill_invoke_line_template`
- **AND** `prompt_builder` MUST 声明 `body_prefix_extra_block` 与 `body_suffix_extra_block`
- **AND** 系统 MUST reject removed legacy prompt-builder fields

### Requirement: Runtime prompt assembly MUST use a shared default body template
系统 MUST 在 skill 未声明 engine/common body prompt 时回退到一份共享默认 body 模板，而不是为各引擎维护重复的默认 body 模板文件。

#### Scenario: skill prompt override is absent
- **WHEN** `entrypoint.prompts[engine]` 与 `entrypoint.prompts.common` 都不存在
- **THEN** runtime MUST render the shared prompt body template
- **AND** runtime MUST apply profile prefix/suffix extra blocks around that shared body

#### Scenario: skill prompt override exists
- **WHEN** `entrypoint.prompts[engine]` 或 `.common` 命中
- **THEN** runtime MUST treat that prompt text as the full body prompt
- **AND** runtime MUST NOT wrap it with profile default-body extra blocks
