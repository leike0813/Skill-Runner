## 1. 数据模型与存储

- [x] 1.1 新增引擎升级任务模型（create/status/result）
- [x] 1.2 新增 `engine_upgrades.db` 存储（SQLite）
- [x] 1.3 支持持久化 per-engine stdout/stderr 结果

## 2. 升级执行管理

- [x] 2.1 新增 `engine_upgrade_manager`（异步任务执行）
- [x] 2.2 实现同一时刻仅允许一个升级任务运行（全局互斥）
- [x] 2.3 支持 `mode=single`（单引擎）
- [x] 2.4 支持 `mode=all`（全部引擎）
- [x] 2.5 失败时返回 per-engine 结果（含 stdout/stderr/error）

## 3. 脚本入口扩展

- [x] 3.1 扩展 `scripts/agent_manager.sh` 支持 `--upgrade-engine <engine>`
- [x] 3.2 保持现有 `--upgrade` 全量升级入口兼容

## 4. API 与路由

- [x] 4.1 新增 `POST /v1/engines/upgrades`
- [x] 4.2 新增 `GET /v1/engines/upgrades/{request_id}`
- [x] 4.3 请求校验：`mode` 与 `engine` 参数一致性
- [x] 4.4 鉴权：将升级接口纳入 Basic Auth 保护域

## 5. UI 页面

- [x] 5.1 新增 `/ui/engines` 页面（状态+版本）
- [x] 5.2 新增“升级全部”交互
- [x] 5.3 新增“单引擎升级”交互
- [x] 5.4 新增升级状态轮询 partial（展示 per-engine stdout/stderr）

## 6. 测试与文档

- [x] 6.1 单测覆盖 manager/store/router/ui
- [x] 6.2 更新 `docs/api_reference.md` 的 Engine 管理接口
- [x] 6.3 更新 README 的 UI Engine 管理说明

## 7. Model Manifest 管理（API）

- [x] 7.1 新增 `GET /v1/engines/{engine}/models/manifest`
- [x] 7.2 新增 `POST /v1/engines/{engine}/models/snapshots`
- [x] 7.3 校验新增模型字段（`id/display_name/deprecated/notes/supported_effort`）
- [x] 7.4 仅允许当前 `cli_version_detected` 版本写入（无 override）
- [x] 7.5 若 `models_<version>.json` 已存在则拒绝（add-only/no-overwrite）
- [x] 7.6 快照写入后立即刷新 model registry

## 8. Model Manifest 管理（UI）

- [x] 8.1 在 `/ui/engines` 增加“模型管理”入口
- [x] 8.2 新增 `/ui/engines/{engine}/models` 页面（manifest+模型列表）
- [x] 8.3 新增“新增当前版本快照”表单交互
- [x] 8.4 提交成功后立即刷新页面数据

## 9. Model Manifest 测试

- [x] 9.1 单测覆盖 manifest 查询接口（含版本不可检测）
- [x] 9.2 单测覆盖快照新增接口（成功/已存在拒绝/版本不可检测）
- [x] 9.3 UI 单测覆盖模型页面渲染与新增交互
