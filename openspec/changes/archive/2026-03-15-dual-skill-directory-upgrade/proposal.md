## Why

当前仓库将内建 skill 与用户可写 skill 混用在同一目录语义下，导致容器部署时难以同时满足“内建可用”和“用户可插拔”。  
双目录策略（`skills_builtin/` + `skills/`）需要以规范形式固化，避免后续实现和文档再次漂移。

## What Changes

- 固化双目录策略：内建目录固定为 `skills_builtin/`，用户目录固定为 `skills/`。
- 固化覆盖优先级：同 `skill_id` 冲突时，用户目录条目覆盖内建目录条目（用户优先）。
- 固化安装/更新边界：包管理安装链路仅写入用户目录，不修改内建目录。
- 在管理 API 增加来源标识字段 `is_builtin`，用于前端判定当前生效 skill 是否来自内建目录。
- 管理 UI 首页 Skill 表格基于 `is_builtin` 显示“内建”标识；若被同 ID 用户 skill 覆盖则标识消失。
- 明确容器部署推荐挂载用户目录 `skills/`，保留镜像内 `skills_builtin/` 作为内建来源。

## Capabilities

### New Capabilities

- `<none>`: 无新增独立 capability，均为现有 capability 的行为升级

### Modified Capabilities

- `skill-package-install`: 规范 skill 扫描与安装的双目录语义，以及用户优先覆盖规则。
- `management-api-surface`: 规范 Skill 管理摘要/详情返回 `is_builtin` 字段。
- `ui-skill-browser`: 规范管理 UI Skill 表格的“内建”标识显示/消失条件。

## Impact

- Affected code:
  - `server/` 下 skill registry / package manager / management API / management UI 相关实现
  - `Dockerfile`、`docker-compose*.yml` 模板与部署脚本
- Affected API:
  - `GET /v1/management/skills` 及复用 skill 摘要的详情响应新增 `is_builtin`（向后兼容扩展）
- Docs:
  - `README*`、`docs/containerization.md`、插件对接契约文档需要同步目录语义与覆盖规则
