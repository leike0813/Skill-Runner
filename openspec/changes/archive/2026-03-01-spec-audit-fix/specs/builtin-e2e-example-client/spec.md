# builtin-e2e-example-client Specification

## Purpose
定义内建 E2E 示例客户端的独立端口部署、低耦合边界和自测能力约束。

## MODIFIED Requirements

### Requirement: 系统 MUST 提供独立端口运行的内建 E2E 示例客户端服务
系统 MUST 提供一套与主服务分离的示例客户端服务，用于 E2E 测试和演示，且该服务 MUST 以独立端口启动。

#### Scenario: 示例客户端独立启动
- **WHEN** 启动示例客户端服务
- **THEN** 服务在独立端口提供页面访问能力
- **AND** 不影响主服务已有端口与路由

#### Scenario: 端口配置默认与环境变量回退
- **WHEN** 未设置 `SKILL_RUNNER_E2E_CLIENT_PORT`
- **THEN** 示例客户端使用默认端口 `8011`
- **AND** 当设置了有效环境变量值时，服务使用该值覆盖默认端口
