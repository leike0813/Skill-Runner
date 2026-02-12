## 背景

已有能力：
- `GET /v1/engines` 可返回 `engine` 与 `cli_version_detected`；
- `scripts/agent_manager.sh --upgrade` 可升级全部引擎；
- `/ui` 已有 Basic Auth 保护体系。

缺失能力：
- 无升级任务 API；
- 无 Engine 管理 UI；
- 无升级状态可视化与 per-engine stdout/stderr 展示。
- 无 Model Manifest 管理入口（查看当前解析结果、补录新版本快照）。

## 目标

1. 在 UI 中可查看当前 Engine 状态（可用/版本）。
2. 支持单引擎升级与全部升级。
3. 升级结果以任务形式可追踪，并返回 per-engine stdout/stderr。
4. 同一时刻只允许一个升级任务执行。
5. 支持按 Engine 管理模型快照（查看 + 新增当前版本快照）。

## API 设计

### 1) 创建升级任务
- `POST /v1/engines/upgrades`
- Request:
  - `mode`: `single` | `all`
  - `engine`: `codex|gemini|iflow`（`mode=single` 时必填）
- Response:
  - `request_id`
  - `status=queued`

### 2) 查询升级任务状态
- `GET /v1/engines/upgrades/{request_id}`
- Response:
  - `status`: queued/running/succeeded/failed
  - `results`: per-engine 结构，包含：
    - `status`（succeeded/failed/skipped）
    - `stdout`
    - `stderr`
    - `error`（可选）

### 3) 查询 Engine 的 Model Manifest 视图
- `GET /v1/engines/{engine}/models/manifest`
- Response:
  - `engine`
  - `cli_version_detected`
  - `manifest`（原始 `manifest.json`）
  - `resolved_snapshot_version`（根据当前版本解析出的快照版本）
  - `resolved_snapshot_file`
  - `models`（快照中的模型数组）

### 4) 为当前版本新增模型快照（add-only）
- `POST /v1/engines/{engine}/models/snapshots`
- Request:
  - `models`（数组）
    - `id`（必填）
    - `display_name`（选填）
    - `deprecated`（选填，bool）
    - `notes`（选填）
    - `supported_effort`（选填，数组）
- 行为约束：
  - 版本号由服务端基于 `cli_version_detected` 决定，不接受请求方覆盖版本；
  - 若无法检测当前 CLI 版本，拒绝请求（冲突类错误）；
  - 若 `models_<detected_version>.json` 已存在，拒绝请求（不覆盖）；
  - 创建快照后更新该引擎 `manifest.json`，并立即刷新内存 Model Registry。

## UI 设计

### 页面
- `GET /ui/engines`
  - 展示 engine 列表与版本信息（复用 `/v1/engines` 数据）
  - 提供“升级全部”按钮
  - 每个 engine 提供“升级该引擎”按钮
  - 每个 engine 提供“模型管理”入口按钮，跳转 `/ui/engines/{engine}/models`

- `GET /ui/engines/{engine}/models`
  - 展示当前 `cli_version_detected`
  - 展示 manifest 解析结果（resolved snapshot）
  - 表格展示当前模型列表
  - 表单新增当前版本快照（add-only）
  - 提交成功后立即刷新列表与解析状态

### 轮询
- `GET /ui/engines/upgrades/{request_id}/status`
  - 返回 HTML partial，持续轮询直到终态
  - 显示 per-engine stdout/stderr

## 升级执行与并发控制

### Manager
- 新增 `engine_upgrade_manager`：
  - 负责任务创建、状态流转、后台执行；
  - 使用进程内锁确保同一时刻只有一个任务进入 running；
  - 其余任务可保持 queued，当前版本可先实现“有 running 则拒绝新任务（409）”。

### 执行策略
- `mode=all`：
  - 依次执行 `codex`、`gemini`、`iflow` 升级。
- `mode=single`：
  - 仅执行目标 engine 升级。

### 脚本入口
- 扩展 `scripts/agent_manager.sh`：
  - 新增 `--upgrade-engine <engine>`。
- 本地权限不足或 npm 失败时：
  - 按 per-engine 记录失败并返回 stderr。

## Model Manifest 数据一致性策略

1. **Add-only**：仅允许新增 `models_<version>.json`，不支持编辑/删除；
2. **No-overwrite**：目标版本快照文件已存在即拒绝；
3. **版本来源唯一**：以 `cli_version_detected` 作为新增版本，不提供 operator override；
4. **立即生效**：写入快照与 manifest 后，立即刷新 registry，后续 `/v1/engines` 查询可见新模型。

## 数据存储

新增 `engine_upgrades.db`（SQLite）：
- `request_id`
- `status`
- `mode`
- `requested_engine`（可空）
- `results_json`（per-engine stdout/stderr）
- `created_at`
- `updated_at`

## 安全与鉴权

- `/v1/engines/upgrades*` 与 `/ui/engines*` 纳入 UI Basic Auth 保护域（与 `/v1/skill-packages/*` 同级别保护策略）。

## 测试策略

1. Unit
- manager：任务创建、状态流转、互斥限制、per-engine 聚合结果。
- router：参数校验、409 并发拒绝、状态查询。
- ui：页面渲染、按钮触发、状态轮询与输出展示。

2. Integration（可后续补）
- 在具备 npm 环境时执行真实升级链路 smoke case。

3. Model Manifest
- GET manifest 视图：版本可解析与不可解析路径；
- POST 新增快照：成功、版本不可检测、快照已存在（拒绝）；
- 新增后立即刷新验证：`/v1/engines` 返回值反映新快照。
