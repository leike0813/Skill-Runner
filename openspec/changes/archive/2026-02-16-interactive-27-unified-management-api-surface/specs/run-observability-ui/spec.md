## ADDED Requirements

### Requirement: Run 可观测能力 MUST 优先通过通用管理 API 暴露
系统 MUST 提供可被任意前端复用的 Run 可观测接口，UI 页面仅作为消费方。

#### Scenario: 通用 API 覆盖 Run 观测核心字段
- **WHEN** 客户端查询 Run 观测状态
- **THEN** 可通过通用管理 API 获取状态、交互态、日志流消费信息
- **AND** 不要求客户端依赖 `/ui/*` HTML 接口

#### Scenario: UI 页面复用通用 API 语义
- **WHEN** 内置 UI 展示 Run 详情与日志
- **THEN** 展示字段语义与通用管理 API 保持一致
- **AND** 不引入仅 UI 可见的私有状态定义
