## ADDED Requirements

### Requirement: Terminal output normalization MUST attempt artifact path autofix before failing missing required artifacts
当终态校验发现 `required artifacts` 缺失时，orchestrator MUST 先尝试基于 `output_data` 的 artifact 路径字段执行路径纠偏，再决定是否失败。

#### Scenario: missing required artifact is repaired from run-local source path
- **GIVEN** output schema 定义了 artifact 字段
- **AND** final `output_data` 中该字段给出的路径位于 `run_dir` 内
- **AND** canonical `run_dir/artifacts/...` 目标文件缺失
- **WHEN** 终态归一化执行 artifact 校验
- **THEN** orchestrator MUST 将源文件搬运到 canonical artifacts 路径
- **AND** MUST 改写 `output_data` 中对应字段为 canonical 路径
- **AND** MUST 在修复后重新执行 artifact + schema 校验

#### Scenario: out-of-run path is rejected and run keeps failed semantics
- **GIVEN** final `output_data` artifact 路径指向 `run_dir` 外部
- **WHEN** orchestrator 执行 artifact path autofix
- **THEN** orchestrator MUST 拒绝该路径修复尝试
- **AND** MUST 记录对应 warning
- **AND** 若 required artifacts 仍缺失，run MUST 维持 failed

#### Scenario: canonical target exists and source is not overwritten
- **GIVEN** canonical artifacts 目标路径已存在文件
- **WHEN** orchestrator 尝试执行 artifact path autofix
- **THEN** orchestrator MUST NOT 覆盖已存在目标文件
- **AND** MUST 记录目标冲突 warning

