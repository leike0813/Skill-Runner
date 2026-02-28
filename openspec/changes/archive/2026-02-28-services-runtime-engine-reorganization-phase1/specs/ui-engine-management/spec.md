## ADDED Requirements

### Requirement: UI behavior MUST remain compatible during internal module migration
系统 MUST 在 services/runtime/engines 重组期间保持管理 UI 与运行 UI 的交互语义兼容。

#### Scenario: Existing UI flows
- **WHEN** 用户执行既有 UI 流程（引擎管理、鉴权、run 观测）
- **THEN** 页面行为与接口交互语义不因内部路径调整而改变
