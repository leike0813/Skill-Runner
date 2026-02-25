## MODIFIED Requirements

### Requirement: 系统 MUST 提供 opencode 正式 Adapter 执行能力
系统 MUST 提供 `opencode` 的正式 Adapter，覆盖 start/resume 命令构建、执行生命周期与 runtime 流解析，并在 interactive 场景支持 `session` 续跑。

#### Scenario: opencode 配置组装包含 enforce 层
- **WHEN** Adapter 构建 opencode 运行时项目级配置
- **THEN** MUST 按统一优先级合并 `engine_default -> skill defaults -> runtime overrides -> enforced`
- **AND** `server/assets/configs/opencode/enforced.json` MUST 作为强制覆盖层生效

#### Scenario: opencode auto 模式权限策略
- **WHEN** `execution_mode=auto`
- **THEN** Adapter 写入的项目级配置 MUST 包含 `"permission.question":"deny"`

#### Scenario: opencode interactive 模式权限策略
- **WHEN** `execution_mode=interactive`
- **THEN** Adapter 写入的项目级配置 MUST 包含 `"permission.question":"allow"`
