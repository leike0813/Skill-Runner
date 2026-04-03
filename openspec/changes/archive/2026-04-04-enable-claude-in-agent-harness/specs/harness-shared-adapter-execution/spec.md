## MODIFIED Requirements

### Requirement: Harness MUST 通过共享 Adapter 路径执行 Claude
系统 MUST 使 harness 对 `claude` 的 start / resume 与其他已接入引擎一样，继续复用共享 adapter 命令构建与恢复接口。

#### Scenario: Claude start uses adapter build_start_command
- **WHEN** harness 执行 `claude` start
- **THEN** 系统通过 Claude adapter 的 start 接口生成命令数组
- **AND** 不在 harness 内维护 Claude 专属命令拼接逻辑

#### Scenario: Claude resume uses adapter build_resume_command
- **WHEN** harness 对 `claude` 执行 resume
- **THEN** 系统通过 Claude adapter 的 resume 接口生成命令数组
- **AND** 不因 harness 白名单而提前拒绝
