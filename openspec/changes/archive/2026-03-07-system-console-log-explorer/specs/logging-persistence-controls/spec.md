## ADDED Requirements

### Requirement: 日志查询 MUST 限制为白名单日志源
系统日志查询实现 MUST 仅允许读取受控日志源（system/bootstrap），禁止任意文件路径输入，以防止路径穿越与越权读取。

#### Scenario: reject unsupported source
- **WHEN** 客户端请求 `/v1/management/system/logs/query?source=unknown`
- **THEN** 服务返回 `400`
- **AND** 错误提示仅允许 `system|bootstrap`

#### Scenario: source file family is restricted
- **WHEN** 客户端请求 `source=system`
- **THEN** 查询实现仅扫描 `skill_runner.log*`
- **AND** 不会扫描其他非白名单文件
