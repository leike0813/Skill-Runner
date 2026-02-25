## MODIFIED Requirements

### Requirement: UI MUST 提供 Engine 状态总览页面
系统 MUST 在 UI 提供 Engine 管理页面，显示引擎可用性与版本号。

#### Scenario: 打开 Engine 管理页
- **WHEN** 用户访问 `/ui/engines`
- **THEN** 页面显示 `codex/gemini/iflow/opencode` 状态
- **AND** 显示每个引擎的版本号（若可检测）

## ADDED Requirements

### Requirement: 执行表单模型选择 MUST 支持 provider/model 双下拉
系统 MUST 在执行表单中提供统一的 provider + model 选择交互，兼容现有单 `model` 字段提交。

#### Scenario: 非 opencode 引擎使用固定 provider
- **WHEN** 用户在执行表单选择 `codex`、`gemini` 或 `iflow`
- **THEN** provider 下拉仅显示一个固定值（`openai/google/iflowcn`）
- **AND** 提交给后端的 `model` 语义与现有行为一致

#### Scenario: opencode 引擎按 provider 过滤模型
- **WHEN** 用户在执行表单选择 `opencode`
- **THEN** provider 选项来自后端模型返回
- **AND** model 下拉按所选 provider 过滤
- **AND** 最终提交 `model` 为 `provider/model` 形式
