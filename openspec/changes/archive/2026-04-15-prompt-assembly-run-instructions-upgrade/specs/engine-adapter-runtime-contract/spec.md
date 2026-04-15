## ADDED Requirements

### Requirement: Run-root instruction files MUST carry engine-agnostic global execution constraints
系统 MUST 在 run materialization 阶段将 engine-agnostic 全局执行约束渲染到 `run_dir` 根目录的引擎约定文件中，而不是在 first-attempt prompt 中追加隐藏前缀。

#### Scenario: materialize run-root instruction file
- **WHEN** 系统为某个 run 物化 run-local skill snapshot
- **THEN** Claude MUST 生成 `run_dir/CLAUDE.md`
- **AND** Gemini MUST 生成 `run_dir/GEMINI.md`
- **AND** 其他引擎 MUST 生成 `run_dir/AGENTS.md`
- **AND** 系统 MUST NOT 在 engine workspace 子目录再写第二份同类文件

### Requirement: Engine prompt assembly MUST begin with an adapter-owned invoke line
系统 MUST 由 adapter profile 声明 skill invoke line 模板，并保证最终 prompt 的第一行始终为该 invoke line。

#### Scenario: assemble skill prompt
- **WHEN** runtime 为某个 skill 构建最终 prompt
- **THEN** 第 1 行 MUST 来自 `prompt_builder.skill_invoke_line_template`
- **AND** 第 2 行起 MUST 来自 body prompt
- **AND** 若 body prompt 为空，最终 prompt MUST 仅包含 invoke line
