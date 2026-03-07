## Why

当前 `docker-compose.yml` 同时承担“本地开发”和“发布分发”两种角色，发布侧缺少可复现的版本化 compose 资产。  
直接在发布流程里改写仓库 compose 文件会引入漂移风险，也不利于回溯每个 release 对应的部署配置。

## What Changes

- 新增 release compose 模板与渲染脚本，生成 `docker-compose.release.yml` 资产。  
- 仓库内 `docker-compose.yml` 继续作为本地开发入口，不在 CI 中被改写。  
- GitHub Actions 在 release/tag 流程中渲染并上传 compose 资产与校验和。  
- 版本策略采用“仅 release tag 允许产出资产”，无 tag 不产出。

## Capabilities

### New Capabilities

- `local-deploy-bootstrap`: 支持从 release 资产直接拉取固定版本镜像启动。

### Modified Capabilities

- `builtin-e2e-example-client`: 保持可选客户端服务块语义，并在 release 资产中沿用同镜像双入口结构。  
- `local-deploy-bootstrap`: 明确本地 compose 与 release compose 的职责分离与单向生成关系。

## Impact

- Affected code:
  - `docker-compose.yml`（只保留本地开发语义）
  - 新增 `docker-compose.release.tmpl.yml`（发布模板）
  - 新增 `scripts/render_release_compose.py`
  - `.github/workflows/docker-publish.yml`
  - `docs/containerization.md`
- API impact: None.
- Runtime protocol impact: None.
