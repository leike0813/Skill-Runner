# engine-adapter-runtime-contract Specification Delta

## ADDED Requirements
### Requirement: First-attempt task submission MUST prepend a global prompt prefix
系统 MUST 在任务提交链路的首个 attempt 上，将全局优先注入 Prompt 插入到最终生效 prompt 的开头。

#### Scenario: first attempt prepends the global prefix after final prompt resolution
- **GIVEN** runtime 已完成原始 prompt 渲染
- **AND** 已处理 `__prompt_override` 等最终 prompt 覆盖逻辑
- **WHEN** 当前执行为任务提交的首个 attempt
- **THEN** 系统 MUST 将全局优先注入 Prompt prepend 到最终 prompt 开头
- **AND** prepend 结果 MUST 成为命令构建与首 attempt 审计写入的 prompt 真相源

#### Scenario: later attempts do not prepend the global prefix
- **GIVEN** 当前执行 attempt number 大于 `1`
- **WHEN** runtime 构建 prompt
- **THEN** 系统 MUST NOT 再次注入全局前缀

#### Scenario: global prefix template can read engine-relative workspace and skills dirs
- **GIVEN** runtime 正在为某个引擎构建首 attempt prompt
- **WHEN** 渲染全局前缀模板
- **THEN** 模板上下文 MUST 包含 `engine_id`
- **AND** MUST 包含 `engine_workspace_dir`
- **AND** MUST 包含 `engine_skills_dir`

#### Scenario: ui shell flow is out of scope for first-attempt prompt prefix injection
- **GIVEN** 执行链路属于 ui shell session 启动
- **WHEN** 系统准备 ui shell 相关配置或命令
- **THEN** 该链路 MUST NOT 依赖本次全局首 attempt prompt 前缀能力
