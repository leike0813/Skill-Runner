## ADDED Requirements

### Requirement: Prompt organization SSOT MUST separate patched SKILL instructions from assembled body prompt defaults
系统 MUST 明确区分 runtime-patched `SKILL.md` 与 adapter prompt builder 的默认 body 模板，禁止将旧 prompt-builder 兼容变量继续视为 runtime instruction source。

#### Scenario: documentation describes prompt assembly
- **WHEN** 系统文档描述 skill prompt assembly
- **THEN** 文档 MUST 将 body 默认模板描述为共享模板加 profile extra block
- **AND** 文档 MUST NOT 继续声明 `params_json`、`input_prompt`、`skill_dir`、`input_file` 为 prompt-builder 提供的兼容上下文
