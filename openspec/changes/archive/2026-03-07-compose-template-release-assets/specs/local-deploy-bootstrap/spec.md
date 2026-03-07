## ADDED Requirements

### Requirement: Release compose asset MUST be rendered from template without mutating repository compose
系统 MUST 从发布模板渲染 `docker-compose.release.yml` 作为 release 资产，且不得在发布流程中改写仓库内 `docker-compose.yml`。

#### Scenario: Tag release renders compose asset
- **WHEN** 仓库触发 `v*` tag 发布流程
- **THEN** CI 生成 `docker-compose.release.yml`
- **AND** 仓库内 `docker-compose.yml` 不被修改

#### Scenario: Release asset uses fixed image tag
- **WHEN** 生成 release compose 资产
- **THEN** `api` 服务使用发布 tag 对应镜像
- **AND** 可选 `e2e_client` 服务使用相同镜像 tag

### Requirement: Non-tag workflow MUST NOT publish release compose asset
系统 MUST 仅在 tag 发布时产出并上传 compose release 资产，避免非正式构建对外分发。

#### Scenario: Manual non-tag run
- **WHEN** 工作流以非 tag 方式触发
- **THEN** 不生成 `docker-compose.release.yml` release asset
