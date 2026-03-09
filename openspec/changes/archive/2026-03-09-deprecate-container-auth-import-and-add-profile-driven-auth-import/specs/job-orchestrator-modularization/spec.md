## ADDED Requirements

### Requirement: container startup MUST NOT perform implicit credential import
容器启动编排 MUST 不再从 `/opt/config` 做隐式鉴权文件导入。

#### Scenario: bootstrap runs without /opt/config import phase
- **GIVEN** 服务以容器模式启动
- **WHEN** entrypoint 执行 bootstrap 流程
- **THEN** bootstrap MUST 不再尝试 `/opt/config` 导入
- **AND** 导入行为 MUST 仅通过显式管理 API 或会话导入 API 触发
