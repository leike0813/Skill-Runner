## MODIFIED Requirements

### Requirement: Harness CLI MUST 提供独立入口并保持与主服务解耦
系统 MUST 保持 `agent-harness` 为本地执行 CLI，同时在容器部署场景提供独立的宿主机 wrapper，将调用显式转发到容器内 harness。

#### Scenario: local harness remains local
- **WHEN** 用户在本地环境执行 `agent-harness ...`
- **THEN** CLI 继续在当前环境直接执行
- **AND** 不自动转发到 docker 容器

#### Scenario: container wrapper forwards to api service harness
- **WHEN** 用户在容器部署场景执行项目提供的 harness container wrapper
- **THEN** wrapper 使用 `docker compose exec api agent-harness ...` 转发调用
- **AND** 原样透传参数、stdin/stdout/stderr 与退出码

#### Scenario: wrapper fails clearly when compose api is unavailable
- **WHEN** docker 或 `api` 服务不可用
- **THEN** wrapper 返回明确错误
- **AND** 不静默回退到宿主机本地 `agent-harness`
