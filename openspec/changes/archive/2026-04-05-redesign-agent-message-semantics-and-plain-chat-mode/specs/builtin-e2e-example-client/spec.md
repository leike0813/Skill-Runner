## MODIFIED Requirements

### Requirement: E2E chat renderer MUST group assistant_process events into collapsible thinking bubbles
E2E 对话区 MUST 支持 `plain` 与 `bubble` 两种展示模式。`bubble` 模式下，连续的 `assistant_process` 条目以及非终态 `assistant_message` 条目 MUST 聚合为单个可折叠思考气泡；`plain` 模式下，只有真正过程语义进入思考区。

#### Scenario: bubble mode groups process and intermediate assistant message
- **GIVEN** 当前展示模式为 `bubble`
- **AND** 连续收到多条 `assistant_process` 与非终态 `assistant_message`
- **WHEN** UI 渲染思考区
- **THEN** 这些条目 MUST 被聚合到同一个可折叠思考气泡
- **AND** 折叠状态下 UI MUST 仅显示最后一条过程相关内容

#### Scenario: plain mode renders intermediate assistant message as chat content
- **GIVEN** 当前展示模式为 `plain`
- **AND** 连续收到 `assistant_process` 与非终态 `assistant_message`
- **WHEN** UI 渲染对话区
- **THEN** `assistant_process` MUST 继续显示在过程视图中
- **AND** `assistant_message` MUST 直接显示为对话内容

### Requirement: E2E renderer MUST dedupe promoted/final content
E2E 对话区 MUST 在 `assistant_final` 到达时移除对应的非终态 `assistant_message` 可见副本，避免在 plain 与 bubble 两种模式下重复渲染。

#### Scenario: final dedupe by message_id then normalized text
- **GIVEN** 已渲染非终态 `assistant_message`
- **AND** 后续收到 `assistant_final`
- **WHEN** `message_id` 可用
- **THEN** UI MUST 优先按 `message_id` 删除对应中间消息副本
- **AND** 若 `message_id` 缺失，MUST 在同 attempt 按规范化文本精确匹配删除

## ADDED Requirements

### Requirement: E2E observation MUST default to plain chat mode and expose a mode toggle
E2E Observation 页面 MUST 默认使用 `plain` 展示模式，并提供切换到传统 `bubble` 模式的用户开关。

#### Scenario: observation opens in plain mode
- **WHEN** 用户首次打开 Observation 页面
- **THEN** 页面默认以 `plain` 模式渲染对话
- **AND** 非终态 `assistant_message` 默认作为对话内容显示

#### Scenario: user toggles back to bubble mode
- **WHEN** 用户切换到 `bubble` 模式
- **THEN** 页面 MUST 立即将非终态 `assistant_message` 收纳回过程气泡
- **AND** 不改变 canonical chat replay 源数据与消息身份
