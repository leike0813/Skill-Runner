# Design: unify-installed-and-temp-skill-run-chain

## 1. 总体设计

统一 request 生命周期为单模型：

- request 创建统一写入 `run_store.requests`；
- request 启动统一走 `/v1/jobs/{request_id}/upload` 与 `job_orchestrator.run_job`；
- request 不再持久化目录，仅 run 持久化目录；
- 观测、交互、鉴权统一走 `/v1/jobs/{request_id}/*`。

## 2. 数据模型

`run_store.requests` 新增字段：

- `skill_source`: `installed | temp_upload`（默认 `installed`）
- `request_upload_mode`: `none | pending_upload | uploaded`
- `temp_skill_manifest_id`: 可空
- `temp_skill_manifest_json`: 可空
- `temp_skill_package_sha256`: 可空

cache 保持双命名空间：

- installed -> `cache_entries`
- temp_upload -> `temp_cache_entries`

新增统一缓存查询接口：

- `get_cached_run(cache_key, source)`

## 3. API 设计

### 3.1 创建

`POST /v1/jobs`

- installed: `skill_source=installed`，必须提供 `skill_id`
- temp_upload: `skill_source=temp_upload`，不要求 `skill_id`

### 3.2 上传并调度

`POST /v1/jobs/{request_id}/upload`

- installed: 上传输入 zip（按 schema key 命名）
- temp_upload: 上传 `skill_package`（必需）+ 输入 zip（可选）
- run 创建必须使用上传阶段已解析的 `SkillManifest`，不能在该路径回退到 installed registry 二次查找。

### 3.3 观测/交互

统一保留：

- `/interaction/pending`
- `/interaction/reply`
- `/auth/session`
- `/events` `/events/history`
- `/chat` `/chat/history`

删除 `/v1/temp-skill-runs/*`。

## 4. 上传 staging

上传流程使用请求内临时目录（`TemporaryDirectory`）：

1. 解压输入 zip 到临时目录；
2. 构建 input manifest 与 hash；
3. 计算 cache key；
4. cache 命中：直接绑定 run；
5. cache 未命中：创建 run 目录，再将临时目录复制到 `run/uploads`。

## 5. temp 生命周期残留清理

删除以下残留路径：

- `temp_skill_cleanup_manager` 调度；
- `temp_skill_run_manager.on_terminal` 回调链路；
- orchestration 中 `temp_request_id` 语义传播。

## 6. 兼容与迁移

本 change 采用一次性切换：

- 移除旧 temp API，不保留别名；
- 启动迁移旧 `temp_skill_runs` 中非终态记录到 `requests`（尽力迁移）；
- 迁移失败时 fail-fast，避免半迁移运行。

## 7. 风险控制

1. cache 命中漂移：通过 source 命名空间显式分离规避；
2. 上传 staging 丢失：请求内同步流程，不跨请求保存 staging；
3. 前端分叉残留：移除 `run_source` 与双基路径；
4. source 误分支：upload 阶段统一以已解析 manifest 创建 run，避免 `temp_upload` 被误走 installed skill 校验。
