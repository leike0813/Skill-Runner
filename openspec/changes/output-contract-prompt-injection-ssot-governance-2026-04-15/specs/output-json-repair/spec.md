## ADDED Requirements

### Requirement: Repair prompts MUST reuse the runtime output contract builder
系统 MUST 让 repair prompt 复用与 runtime `SKILL.md` 注入相同的动态 output contract builder，避免维护第二套 prompt summary wording。

#### Scenario: build repair prompt contract
- **WHEN** orchestrator 为某个 attempt 构建 schema repair prompt
- **THEN** repair prompt 中的 contract details MUST 来自统一动态 builder
- **AND** 该文本 MUST 与当前引擎有效的 prompt contract 保持一致

#### Scenario: prompt contract artifact removed
- **WHEN** run 目录中不存在 prompt-facing schema Markdown artifact
- **THEN** repair prompt 构建 MUST 仍然成功
- **AND** 系统 MUST NOT 依赖 `.audit/contracts/*.md` summary 文件
