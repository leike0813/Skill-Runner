## ADDED Requirements

### Requirement: iFlow 鉴权成功判定 MUST 以 CLI 输出锚点为准
系统 MUST 仅依据 iFlow CLI 输出锚点判定委托编排鉴权会话成功，不以 auth 文件存在性作为成功条件。

#### Scenario: 提交授权码后主界面锚点出现
- **WHEN** iFlow 会话已提交 authorization code
- **AND** 输出出现主界面锚点 `输入消息或@文件路径`
- **THEN** 会话状态转为 `succeeded`

#### Scenario: auth-status 保持解耦
- **WHEN** iFlow 委托编排会话进入任意状态
- **THEN** 既有 `GET /v1/engines/auth-status` 判定逻辑保持不变
- **AND** 不要求与该会话状态实时联动

### Requirement: iFlow 委托编排 MUST 具备菜单选中项可观测与纠偏能力
系统 MUST 识别鉴权菜单当前选中项（`● n.`），并在非第一项时自动调整至第一项。

#### Scenario: 菜单默认选中非第一项
- **WHEN** 检测到菜单选中项为 `n > 1`
- **THEN** 系统自动注入方向键将选中项移动到第 1 项
- **AND** 再注入回车进入 OAuth 流程

### Requirement: iFlow 委托编排 MUST 暴露可访问的 OAuth URL
系统 MUST 从 iFlow OAuth 页提取 URL，并在会话快照中返回供 UI 展示。

#### Scenario: URL 被换行折断
- **WHEN** OAuth URL 以多行输出
- **THEN** 系统进行拼接与清洗后返回有效 URL 字符串
