# management-api-surface Specification

## ADDED Requirements

### Requirement: 管理 API MUST 提供受保护的全量数据重置接口
系统 MUST 暴露一个管理域高危操作接口，用于执行与 `scripts/reset_project_data.py` 等价的数据清理流程，并返回结构化执行结果。

#### Scenario: 确认通过后执行重置
- **WHEN** 客户端调用数据重置接口并提供合法确认文本
- **THEN** 系统执行与脚本一致的目标路径清理与目录重建流程
- **AND** 响应包含 `deleted_count`、`missing_count`、`recreated_count` 与目标路径摘要

### Requirement: 数据重置接口 MUST 强制手动确认文本
系统 MUST 在服务端校验确认文本；未通过确认时不得执行任何删除操作。

#### Scenario: 确认文本错误
- **WHEN** 客户端调用数据重置接口但确认文本缺失或不匹配
- **THEN** 系统返回客户端错误响应（4xx）
- **AND** 不发生任何文件删除或目录重建副作用

### Requirement: 数据重置接口 MUST 支持与脚本对齐的可选清理开关
系统 MUST 提供与 `reset_project_data.py` 可选项对齐的开关参数，确保 API 触发行为与脚本语义一致。

#### Scenario: 仅启用部分可选项
- **WHEN** 客户端仅启用部分可选清理开关（如日志、引擎鉴权会话、引擎目录缓存）
- **THEN** 系统只清理对应可选目标
- **AND** 必选核心数据目标仍按既定策略处理

### Requirement: 数据重置接口 MUST 支持 dry-run 预览
系统 MUST 支持 dry-run 模式，在不执行删除的情况下返回将被处理的目标集合。

#### Scenario: dry-run 请求
- **WHEN** 客户端调用接口并设置 `dry_run=true`
- **THEN** 系统返回待处理目标清单
- **AND** 不发生实际删除与重建副作用
