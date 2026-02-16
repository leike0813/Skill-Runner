## ADDED Requirements

### Requirement: Engine 管理 UI MUST 基于通用管理 API 字段渲染
系统 MUST 让 Engine 管理相关核心信息可通过通用管理 API 获取，UI 不应依赖私有拼装字段。

#### Scenario: 获取 Engine 概览信息
- **WHEN** 客户端请求 Engine 管理概览
- **THEN** 响应包含版本、认证状态、沙箱状态等稳定字段

#### Scenario: 获取 Engine 详情信息
- **WHEN** 客户端请求 Engine 管理详情
- **THEN** 响应包含模型列表与升级状态信息
- **AND** 字段可被非内置 UI 前端直接消费
