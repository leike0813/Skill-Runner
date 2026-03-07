## ADDED Requirements

### Requirement: Release compose MUST preserve optional E2E client topology
系统 MUST 在 release compose 资产中保留与本地 compose 一致的可选 `e2e_client` 服务块（默认注释），并继续采用同镜像双入口模式。

#### Scenario: Optional e2e_client remains commented
- **WHEN** 用户下载 release compose 资产
- **THEN** `api` 为默认启用服务
- **AND** `e2e_client` 服务保持默认注释并附带启用提示

#### Scenario: Enabling e2e_client uses same image
- **WHEN** 用户按注释提示启用 `e2e_client`
- **THEN** `e2e_client` 与 `api` 使用同一镜像 tag
- **AND** 仅通过入口命令区分服务角色
