## ADDED Requirements

### Requirement: management run-detail chat MUST render assistant_process with collapsible thinking groups
管理 UI run detail 对话区 MUST 支持 `assistant_process` 思考气泡分组渲染，且默认折叠。

#### Scenario: management collapsible process group
- **GIVEN** chat history 包含连续 `assistant_process`
- **WHEN** 页面渲染对话区
- **THEN** UI MUST 将其聚合为单个思考气泡
- **AND** 点击后 MUST 展开显示全部过程条目

### Requirement: management and E2E MUST share core state transition while keeping independent adapters
管理 UI 与 E2E MUST 共享同一思考气泡状态机逻辑，并保留各自渲染适配器。

#### Scenario: same event sequence produces same grouping boundaries
- **GIVEN** 两端输入同一 chat replay 事件序列
- **WHEN** 运行共享状态机
- **THEN** 过程分组边界与 final 去重结果 MUST 一致
- **AND** 两端可采用不同 DOM/CSS 呈现细节
