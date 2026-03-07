## Context

容器部署存在两个真实场景：

1. 本地开发：希望 `docker compose up --build` 直接可用，便于调试。  
2. 版本分发：希望用户拿到 release 后即可拉取固定镜像运行，且不依赖本地构建。

当前缺少第二类场景的标准产物。

## Goals / Non-Goals

**Goals:**
- 保留仓库 compose 的本地开发友好性（build-first）。
- 生成发布专用 compose 资产（image-first，锁定版本 tag）。
- 资产生成过程可追溯、可校验，不改写仓库主 compose 文件。

**Non-Goals:**
- 不新增业务 API、协议、运行时语义变更。
- 不引入额外 compose 拓扑分叉（仍保持 api + 可选 e2e_client）。

## Decisions

### 1) 双形态 compose（源文件 + 产物文件）

- 仓库保留 `docker-compose.yml` 作为本地构建入口。  
- 新增 `docker-compose.release.tmpl.yml` 作为 release 渲染模板。  
- release 资产由模板渲染生成 `docker-compose.release.yml`。

### 2) 渲染行为固定

- 渲染脚本只替换镜像仓库与 tag，不修改服务拓扑、端口、卷、环境变量结构。  
- 输出后必须通过 `docker compose config` 语法校验。  
- 同步生成 `sha256` 文件作为完整性校验。

### 3) 仅 tag 发布资产

- 只有在 release tag（`v*`）上下文才生成并上传 compose 资产。  
- 非 tag 手动触发不生成资产，避免“非正式版本”外溢。

## Migration Plan

1. 新增 release compose 模板与渲染脚本。  
2. 在 Docker 发布工作流中接入渲染、校验与上传 release asset。  
3. 更新容器文档，明确本地 compose 与 release compose 的使用差异。  
4. 对 tag 发布进行一次端到端验证（镜像 + compose 资产）。

## Risks / Trade-offs

- [Risk] 模板与主 compose 漂移  
  - Mitigation: 在 CI 中增加结构对齐检查（关键服务名与端口段必须一致）。

- [Risk] 用户误用仓库 compose 做生产部署  
  - Mitigation: 文档明确区分“local compose”与“release asset compose”。
