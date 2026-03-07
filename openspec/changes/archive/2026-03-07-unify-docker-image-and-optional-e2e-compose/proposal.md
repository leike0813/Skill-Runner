## Why

当前容器部署只覆盖主服务，E2E 示例客户端仍需要额外本地启动路径，部署体验分裂。  
同时 `docker-compose.yml` 只有单服务定义，缺少“同镜像可选启用客户端”的标准组织方式。

## What Changes

- 将 `e2e_client` 代码纳入同一个 Docker 镜像构建产物。  
- 为同一镜像提供“主服务入口”和“E2E 客户端入口”两种启动路径。  
- 重组 `docker-compose.yml`：默认仅启用主服务，追加可选的 E2E 客户端服务模板。  
- 将 compose 中客户端服务默认注释，并补充启用提示。  
- 同步更新容器文档，明确双入口和可选客户端服务的使用方式。

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `local-deploy-bootstrap`: 增加 compose 组织约束（主服务默认启用、客户端可选注释块）。  
- `builtin-e2e-example-client`: 增加“与主服务共用镜像、通过不同入口启动”的容器部署约束。

## Impact

- Affected code:
  - `Dockerfile`
  - `docker-compose.yml`
  - `scripts/entrypoint*.sh`（若新增 E2E 入口脚本）
  - `docs/containerization.md`
- API impact: None.
- Runtime protocol impact: None.
- Dependency impact: None（同镜像打包，不新增运行时依赖）。
