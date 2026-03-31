## ADDED Requirements

### Requirement: run 工作目录结果文件 MUST 可作为终态输出恢复来源

当 run 已成功执行但主路径结构化输出缺失或非法时，系统 MUST 能从 run 工作目录内恢复结果文件，而不依赖 `result/result.json` 或审计目录。

#### Scenario: default result filename is discovered under run workspace
- **GIVEN** skill 未声明自定义结果文件名
- **AND** `run_dir` 子树中存在 `<skill-id>.result.json`
- **WHEN** 主路径结构化输出失败且 lifecycle 进入结果恢复
- **THEN** 系统必须将该文件视为候选结果文件

#### Scenario: declared result filename overrides default
- **GIVEN** `runner.json.entrypoint.result_json_filename` 声明了非空字符串
- **WHEN** lifecycle 扫描 run 工作目录
- **THEN** 系统必须只按该文件名匹配候选结果文件
- **AND** 不再使用默认 `<skill-id>.result.json`

#### Scenario: multiple candidate result files choose latest mtime
- **GIVEN** `run_dir` 内存在多个同名候选结果文件
- **WHEN** lifecycle 选择最终恢复来源
- **THEN** 系统必须优先选择 `mtime` 最新的文件
- **AND** 若 `mtime` 相同，则按浅层路径优先
- **AND** 结果必须记录 `OUTPUT_RESULT_FILE_MULTIPLE_CANDIDATES`

#### Scenario: audit and terminal result directories are excluded
- **GIVEN** `.audit/` 或 `result/` 下存在同名 JSON 文件
- **WHEN** lifecycle 扫描候选结果文件
- **THEN** 这些文件不得参与候选选择
