## Why

当前鉴权导入交互仍在多处使用旧的专用数据形状（`required_files/optional_files`），并且 E2E 前端仍有本地硬编码规则，造成：
- 后端与前端交互模型不一致；
- 导入文件选择逻辑无法复用到其他交互；
- 未来扩展文件上传类交互时需要重复实现。

## What Changes

- 将 `upload_files` 提升为 `ask_user` 一等 `kind`（与 `open_text/choose_one/confirm` 并列）。
- 管理端鉴权导入规格接口硬切为统一 `ask_user` 形状。
- `waiting_auth` 导入 challenge 统一通过 `pending_auth.ask_user.kind=upload_files` 提供渲染提示。
- 管理 UI 与 E2E 前端统一按 `ask_user.files` 渲染上传表单，删除 E2E 本地硬编码规则。
- 同步更新 runtime 合同、ask_user 合同、API 文档与交互注入模板。

## Scope

- Affected code:
  - `server/models/interaction.py`
  - `server/models/management.py`
  - `server/contracts/schemas/runtime_contract.schema.json`
  - `server/contracts/schemas/ask_user.schema.yaml`
  - `server/services/engine_management/auth_import_service.py`
  - `server/services/orchestration/run_auth_orchestration_service.py`
  - `server/assets/templates/ui/engines.html`
  - `e2e_client/templates/run_observe.html`
  - `server/assets/templates/patch_mode_interactive.md`
  - `server/services/skill/skill_patcher.py`
  - `docs/api_reference.md`
  - `tests/unit/test_auth_import_service.py`
  - `tests/unit/test_management_routes.py`
  - `tests/unit/test_run_auth_orchestration_service.py`
  - `tests/unit/test_e2e_run_observe_semantics.py`
  - `tests/unit/test_jobs_interaction_routes.py`
- API impact:
  - `GET /v1/management/engines/{engine}/auth/import/spec` 响应形状为 `ask_user`（破坏性变更）。
