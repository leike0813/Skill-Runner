## Why

当前仓库在三个点上存在明显收口需求。

一是 `runtime_options.debug` 已经失去存在必要，但前端表单、运行参数策略、文档与部分 spec 仍保留该开关，形成无意义的用户心智负担。当前 debug bundle 已经是独立下载能力，不应再和运行期开关耦合。

二是 `agent_harness` 目前是“本地在哪执行就消费哪套 RuntimeProfile”的纯本地 CLI。对于容器化部署，用户无法在宿主机上直接通过正式入口调起容器内 harness，只能手工写 `docker compose exec api ...`，缺少项目级受支持入口。

三是 `scripts/` 目录已经混入了正式部署脚本、历史兼容包装器、排障脚本和一次性实验脚本。继续把它们都放在主目录下，会误导用户把非正式脚本当成支持面，并提高文档和维护成本。

## What Changes

- 硬切下线 `runtime_options.debug`，移除前后端表单、策略与文档中的该选项。
- 保留普通 bundle 和 debug bundle 两个独立下载入口；明确它们与 runtime option 无关。
- 新增宿主机侧容器 wrapper，使用户可以通过项目正式脚本转发到容器内 `agent-harness`，而不改变现有本地 `agent-harness` CLI 语义。
- 对 `scripts/` 做分类清退：正式功能保留在 `scripts/`，历史/排障脚本迁移到 `deprecated/scripts/` 或 `artifacts/scripts/`。
- 更新 README、多语言 README、containerization 文档、API reference 和相关 OpenSpec specs，使脚本入口、bundle 语义和 harness 用法一致。

## Capabilities

### Modified Capabilities

- `builtin-e2e-example-client`: E2E run form 不再暴露 `debug` runtime option。
- `job-orchestrator-modularization`: run bundle 继续支持普通/debug 双产物，但不再依赖 `runtime_options.debug`。
- `external-runtime-harness-cli`: 容器部署场景新增正式宿主机 wrapper 入口，明确与本地 CLI 语义边界。
- `local-deploy-bootstrap`: 脚本支持面与发布/部署文档中的正式入口保持一致，历史和排障脚本不再占据主目录。

## Impact

- Affected code:
  - `e2e_client/routes.py`
  - `e2e_client/templates/run_form.html`
  - `server/config/policy/options_policy.json`
  - `scripts/*`
  - `docs/api_reference.md`
  - `docs/containerization.md`
  - `README*.md`
- API impact:
  - 无新增/删除 HTTP 路由。
  - `runtime_options.debug` 不再是合法运行参数。
  - `GET /v1/jobs/{request_id}/bundle` 与 `GET /v1/jobs/{request_id}/bundle/debug` 保持不变。
