## ADDED Requirements

### Requirement: UI behavior MUST remain compatible after hard cutover
phase2 删除兼容导入层后，`/ui` 路由与交互语义 MUST 保持兼容。

#### Scenario: Existing UI flows after hard cutover
- **WHEN** 用户执行既有 UI 交互流程
- **THEN** 页面行为与后端响应语义不回归
