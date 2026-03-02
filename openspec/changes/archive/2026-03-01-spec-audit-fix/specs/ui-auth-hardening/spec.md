# ui-auth-hardening Specification

## Purpose
定义 UI 鉴权状态可观测性和受保护路由的 401 返回约束。

## MODIFIED Requirements

### Requirement: UI 鉴权状态 MUST 可观测
系统 MUST 在启动时输出 UI 鉴权是否启用及受保护路由范围。

#### Scenario: 启动日志可见
- **WHEN** 服务启动完成
- **THEN** 日志包含 `UI basic auth enabled` 状态
- **AND** 日志包含受保护路径范围说明
