# engine-auth-observability Specification

## Purpose
定义引擎鉴权生命周期的统一状态接口、审计字段、日志分目录组织和 UI 可观测性约束。

## MODIFIED Requirements

### Requirement: 系统 MUST 提供统一 Engine 鉴权状态接口
系统 MUST 提供统一接口返回各 Engine 的鉴权可观测状态，且输出结构可被 UI 与脚本复用。

#### Scenario: 查询鉴权状态成功
- **WHEN** 客户端请求 `GET /v1/engines/auth-status`
- **THEN** 返回每个 engine 的 `managed_present`、`effective_cli_path`、`effective_path_source`
- **AND** 返回白名单凭证文件存在性明细
