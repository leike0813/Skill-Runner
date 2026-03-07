## Context

当前镜像入口只针对后端主服务，E2E 客户端需要通过仓库脚本单独启动。  
这导致容器化部署时无法一套镜像覆盖“主服务 + 示例客户端”两条路径，也使 compose 示例无法直接表达“默认仅主服务、按需启用客户端”。

## Goals / Non-Goals

**Goals:**
- 用单一镜像同时承载 `server` 与 `e2e_client` 运行能力。  
- 为镜像提供两个明确入口：`api` 与 `e2e-client`。  
- 在 compose 中保留“主服务默认启用 + 客户端可选启用（默认注释）”的标准模板。  
- 保持现有 API、协议、数据库与运行态语义不变。

**Non-Goals:**
- 不引入新的业务路由或协议。  
- 不改变 E2E 客户端功能边界。  
- 不把 E2E 客户端默认纳入生产部署拓扑。  
- 不修改 run/auth/orchestration 运行时实现。

## Decisions

### 1) 单镜像双入口

- 镜像构建时同时复制 `server/` 与 `e2e_client/`。  
- 保留现有主服务入口作为默认入口。  
- 为 E2E 客户端新增独立启动入口（脚本或命令），由 compose 服务覆写 `command/entrypoint` 选择。

**Rationale:**  
单镜像可减少构建与发布复杂度；双入口可保持运行角色边界清晰。

### 2) Compose 组织规则

- `api` 服务保持激活状态，作为默认部署单元。  
- 在同一 compose 文件提供 `e2e_client` 服务模板，镜像与 `api` 相同，仅入口与端口不同。  
- 客户端服务块默认注释，块内附启用提示（取消注释即可启动）。

**Rationale:**  
满足“默认最小部署”与“按需启用演示客户端”两个场景，避免强绑定。

### 3) 文档与可操作性

- 更新容器文档，明确：
  - 同镜像双入口原则
  - compose 默认行为
  - 如何启用/关闭 E2E 客户端服务
  - 常见端口冲突处理方式

**Rationale:**  
compose 中有注释模板时，文档必须给出等价操作说明，防止误用。

## Risks / Trade-offs

- [Risk] 单镜像体积增大  
  → Mitigation: 仅打包必要目录，并复用现有 `.dockerignore` 控制上下文。

- [Risk] 用户误把 E2E 客户端当生产组件长期启用  
  → Mitigation: compose 默认注释 + 文档明确“演示/测试用途”。

- [Risk] 双入口脚本维护分叉  
  → Mitigation: 两个入口脚本共享环境初始化逻辑，差异仅在最终启动命令。

## Migration Plan

1. 更新 Dockerfile，加入 `e2e_client` 构建输入与可选入口支持。  
2. 新增/调整 E2E 客户端容器启动脚本。  
3. 修改 `docker-compose.yml`：保留 `api`，增加默认注释的 `e2e_client` 服务模板。  
4. 更新 `docs/containerization.md`。  
5. 通过 compose 最小回归验证：
   - 默认只启 `api` 可用
   - 取消注释后 `e2e_client` 可独立启动并访问后端

## Open Questions

- None.
