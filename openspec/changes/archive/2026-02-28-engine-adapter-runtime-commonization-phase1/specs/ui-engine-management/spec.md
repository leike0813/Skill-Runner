## MODIFIED Requirements

### Requirement: UI Behavior Is Stable During Adapter Refactor
adapter 侧重构 MUST NOT 改变管理 UI 的既有交互语义。

#### Scenario: Engine management page interactions
- **GIVEN** 用户在 `/ui/engines` 操作引擎
- **WHEN** 使用执行、鉴权、模型管理功能
- **THEN** UI 的交互流程与字段契约保持不变
