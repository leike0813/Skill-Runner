## ADDED Requirements

### Requirement: Gemini 鉴权成功判定 MUST 以 CLI 输出锚点为准
系统 MUST 仅依据 Gemini CLI 输出锚点判定委托编排鉴权会话成功，不以 auth 文件存在性作为成功条件。

#### Scenario: 授权码提交后主界面锚点出现
- **WHEN** 会话已提交 authorization code
- **AND** 输出再次出现 `Type your message or @path/to/file`
- **THEN** 会话状态转为 `succeeded`

#### Scenario: auth-status 语义保持解耦
- **WHEN** Gemini 委托编排会话进入任意状态
- **THEN** 既有 `GET /v1/engines/auth-status` 判定逻辑保持不变
- **AND** 不要求与会话状态实时联动

### Requirement: Gemini 委托编排 MUST 具备 URL 可观测能力
系统 MUST 在解析到 Gemini OAuth URL 后将其暴露在会话快照中，支持 UI 可点击展示。

#### Scenario: URL 跨行折断
- **WHEN** Gemini CLI 将授权 URL 以多行输出
- **THEN** 系统拼接并清洗后返回有效 URL 字符串

