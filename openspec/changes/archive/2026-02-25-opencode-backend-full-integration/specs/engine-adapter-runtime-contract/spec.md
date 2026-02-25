## MODIFIED Requirements

### Requirement: 系统 MUST 提供 opencode 正式 Adapter 执行能力
系统 MUST 提供 `opencode` 的正式 Adapter，覆盖 start/resume 命令构建、执行生命周期与 runtime 流解析，并在 interactive 场景支持 `session` 续跑。

#### Scenario: opencode start 命令构建
- **WHEN** 调用方请求构建 opencode start 命令
- **THEN** Adapter MUST 生成 `opencode run --format json --model <provider/model> <prompt>` 形态命令
- **AND** 允许在该基线上合并 profile/runtime 参数

#### Scenario: opencode resume 命令构建
- **WHEN** 调用方请求基于 session handle 构建 opencode resume 命令
- **THEN** Adapter MUST 生成 `opencode run --session=<session_id> --format json --model <provider/model> <message>` 形态命令

#### Scenario: opencode 模型格式校验
- **WHEN** 调用方向 opencode 传入模型字符串
- **THEN** 模型 MUST 满足 `<provider>/<model>` 格式
- **AND** 包含 `@effort` 后缀的模型字符串 MUST 被拒绝

#### Scenario: session handle 提取失败
- **WHEN** opencode runtime 输出中缺失可解析的 `session_id`（或 JSON 行不可解析）
- **THEN** 系统返回 `SESSION_RESUME_FAILED` 类错误
- **AND** MUST NOT 隐式创建新会话继续执行
