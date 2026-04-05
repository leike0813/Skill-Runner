## MODIFIED Requirements

### Requirement: 示例客户端 MUST 模拟真实前端提交链路
示例客户端 MUST 在提交前执行输入校验，并按真实前端流程打包并发送执行请求。

#### Scenario: run form uses provider model effort triplet
- **WHEN** 用户在 E2E 提交页选择引擎与模型
- **THEN** 页面 MUST 以 `provider_id + model + effort` 构造提交 payload
- **AND** MUST NOT 再主动把 `effort` 拼接回 `model` 字段

#### Scenario: effort selector stays visible for unsupported models
- **WHEN** 当前模型不支持 effort
- **THEN** E2E 提交页中的 `effort` 下拉 MUST 保持可见
- **AND** MUST 处于禁用状态
- **AND** 其固定显示值为 `default`

#### Scenario: effort selector reflects supported variants
- **WHEN** 当前模型支持 effort
- **THEN** E2E 提交页 MUST 启用 `effort` 下拉
- **AND** 选项 MUST 包含 `default`
- **AND** 其余选项来自模型目录返回的 `supported_effort`
