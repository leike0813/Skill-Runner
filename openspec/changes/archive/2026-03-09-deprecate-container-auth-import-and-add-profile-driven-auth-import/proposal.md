## Why

容器启动阶段通过 `/opt/config` 自动导入鉴权文件，会把部署细节和鉴权生命周期耦合在一起：
- 需要额外挂载目录与脚本参数，维护成本高。
- 导入行为不可控，重启时容易重复覆盖当前有效鉴权状态。
- 无法与会话内鉴权流程统一。

同时，当前管理 UI 与 `waiting_auth` 都缺少“文件导入鉴权”这一正式能力，用户只能走回调/授权码/API key 提交。

## What Changes

- 硬下线容器 `/opt/config` 导入链路（compose 挂载、entrypoint 导入、`agent_manager --import-credentials`）。
- 基于 Adapter Profile 声明式配置新增鉴权导入服务（文件需求、目标写盘路径、结构校验）。
- 管理端新增导入接口：
  - `GET /v1/management/engines/{engine}/auth/import/spec`
  - `POST /v1/management/engines/{engine}/auth/import`
- 会话中鉴权新增导入接口：
  - `POST /v1/jobs/{request_id}/interaction/auth/import`
- 扩展会话方法 `auth_method=import`，导入成功后直接 `auth.completed` 并恢复运行。
- OpenCode provider 维度特判：
  - 仅 `openai/google`（oauth）开放导入
  - `openai` 支持 OpenCode/Codex `auth.json` 自动识别与转换
  - `google` 可选 `antigravity-accounts.json` 并展示高风险提示

## Scope

- Affected code:
  - `docker-compose.yml`
  - `docker-compose.release.tmpl.yml`
  - `scripts/entrypoint.sh`
  - `scripts/agent_manager.py`
  - `server/contracts/schemas/adapter_profile_schema.json`
  - `server/runtime/adapter/common/profile_loader.py`
  - `server/engines/*/adapter/adapter_profile.json`
  - `server/contracts/schemas/engine_auth_strategy.schema.json`
  - `server/engines/*/config/auth_strategy.yaml`
  - `server/models/interaction.py`
  - `server/contracts/schemas/runtime_contract.schema.json`
  - `server/services/engine_management/auth_import_service.py` (new)
  - `server/services/engine_management/auth_import_validator_registry.py` (new)
  - `server/routers/management.py`
  - `server/routers/jobs.py`
  - `server/services/orchestration/run_auth_orchestration_service.py`
  - `server/assets/templates/ui/engines.html`
  - `e2e_client/templates/run_observe.html`
  - `server/locales/{en,zh,ja,fr}.json`
  - `docs/api_reference.md`
  - `docs/containerization.md`
  - `README*.md`
- API impact:
  - 新增 3 个接口（2 管理端 + 1 会话导入）
- Runtime protocol impact:
  - `auth_method` 与相关 schema 增量扩展 `import`
