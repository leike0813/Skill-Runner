# management-api-surface Specification

## Purpose
定义统一管理 API 面（Skill/Engine/Run 三域）的路由和操作语义。

## MODIFIED Requirements

### Requirement: 系统 MUST 提供统一管理 API 面
系统 MUST 提供前端无关的管理 API，覆盖 Skill 管理、Engine 管理、Run 管理三类资源。

#### Scenario: 管理 API 资源分组
- **WHEN** 客户端查询管理能力
- **THEN** 可在统一命名空间访问 Skill / Engine / Run 管理资源
- **AND** 返回稳定 JSON 字段，不依赖 HTML 结构
