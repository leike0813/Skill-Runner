## Why

当前内建 E2E 示例客户端虽然已经支持通过 `runtime_options` 提交运行参数，但提交页并没有暴露 `hard_timeout_seconds` 的填写入口。这样一来，用户无法在前端明确控制单次 run 的硬超时，也看不到 skill 自带默认值与服务级默认值的实际生效来源。

此外，E2E 客户端当前也拿不到稳定的“服务默认 hard timeout”数据源，只能依赖前端硬编码或完全不展示，这与管理 API 面向动态表单的定位不一致。

## What Changes

- 新开 OpenSpec change，为 E2E Run Form 增加 `hard_timeout_seconds` 输入控件。
- 扩展 management API：
  - `GET /v1/management/skills/{skill_id}` 增加 `runtime.default_options`
  - 新增 `GET /v1/management/runtime-options`，暴露服务级默认 `hard_timeout_seconds`
- E2E 前端提交页使用 spinbox 展示 `hard_timeout_seconds`，默认值优先取 skill runtime default，其次回退到服务默认值。
- 提交前执行严格校验：值必须是非负整数；合法时显式写入 `runtime_options.hard_timeout_seconds`。

## Capabilities

### New Capabilities

- `management-api-surface`: 新增 runtime options 默认值读取接口，供前端动态表单使用。

### Modified Capabilities

- `builtin-e2e-example-client`: Run Form 新增 `hard_timeout_seconds` runtime option 输入与提交校验。
- `management-api-surface`: Skill detail 暴露 `runtime.default_options`，并提供服务级 runtime option 默认值接口。

## Impact

- Affected code:
  - `server/models/management.py`
  - `server/routers/management.py`
  - `e2e_client/backend.py`
  - `e2e_client/routes.py`
  - `e2e_client/templates/run_form.html`
  - locale files used by the E2E client
- Affected tests:
  - `tests/unit/test_management_routes.py`
  - `tests/api_integration/test_management_api.py`
  - `tests/api_integration/test_e2e_example_client.py`
- Public API changes:
  - New `GET /v1/management/runtime-options`
  - `GET /v1/management/skills/{skill_id}` adds `runtime.default_options`
