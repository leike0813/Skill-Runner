## ADDED Requirements

### Requirement: Engine 管理页面字段 MUST 对齐 management API
系统 MUST 保证内建 Engine 管理页面使用 management API 稳定字段，不依赖 UI 私有拼装。

#### Scenario: 引擎概览渲染
- **WHEN** 页面渲染引擎概览
- **THEN** 版本、认证状态、沙箱状态来源于 management API 标准字段

#### Scenario: 升级状态渲染
- **WHEN** 页面渲染升级状态与结果
- **THEN** 数据来源与外部前端可消费的管理接口语义一致
