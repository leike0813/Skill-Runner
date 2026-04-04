## MODIFIED Requirements

### Requirement: 执行表单模型选择 MUST 支持 provider/model 双下拉

系统 MUST 在执行表单中提供统一的 provider + model 选择交互，兼容现有单 `model` 字段提交。

#### Scenario: provider-aware engines use backend provider metadata

- **WHEN** 用户在执行表单选择 `opencode` 或 `qwen`
- **THEN** provider 选项 MUST 来自后端模型元数据
- **AND** model 选项 MUST 按当前 provider 过滤
- **AND** UI 请求 SHOULD 提交 `provider_id + model`

#### Scenario: legacy opencode model syntax remains compatible

- **WHEN** 旧客户端仍提交 `opencode` 的 `provider/model`
- **THEN** 系统保持兼容
- **AND** 新 UI 不再把该格式作为首选提交方式

### Requirement: 管理 UI 鉴权行为 MUST 对 provider-aware engine 透明

系统 MUST 在 `/ui/engines` 以共享框架渲染 provider-aware engine 的 provider 选择、方法选择和导入可见性。

#### Scenario: provider-aware auth menu is backend-driven

- **WHEN** 用户打开 `opencode` 或 `qwen` 的鉴权菜单
- **THEN** provider 列表与 method 列表 MUST 来自后端注入能力矩阵与 provider 元数据
- **AND** 前端 MUST NOT 通过 engine 名称硬编码 provider 规则

#### Scenario: import entry follows provider metadata

- **WHEN** provider 元数据声明 `supports_import=false`
- **THEN** UI MUST 隐藏该 provider 的导入入口

#### Scenario: qwen coding-plan hides import action

- **WHEN** 用户选择 `qwen` 的 `coding-plan-china` 或 `coding-plan-global`
- **THEN** UI MUST NOT 展示 import 入口
