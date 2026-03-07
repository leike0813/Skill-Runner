## 1. Jobs File APIs

- [x] 1.1 在 `server/routers/jobs.py` 新增 `GET /v1/jobs/{request_id}/files`，复用 run 文件树读取能力
- [x] 1.2 在 `server/routers/jobs.py` 新增 `GET /v1/jobs/{request_id}/file`，复用 canonical 文件预览构建能力
- [x] 1.3 补充/更新 jobs 文件接口响应模型与路径校验（禁止绝对路径与 `..`）

## 2. E2E Preview Source Convergence

- [x] 2.1 更新 `e2e_client/backend.py`，增加对 jobs 文件树/文件预览接口的调用方法
- [x] 2.2 更新 `e2e_client/routes.py`，将 bundle file preview 路径改为后端透传，不再本地 `ZipFile + build_preview_payload_from_bytes`
- [x] 2.3 清理 E2E 本地 bundle 预览构建残留逻辑（保留 bundle 下载能力）

## 3. UI & Regression Tests

- [x] 3.1 更新 E2E observation 页面相关测试，断言预览来自后端 payload 并支持 markdown/json 分支
- [x] 3.2 新增 jobs 文件接口路由单测（正常读取、非法路径、文件不存在）
- [x] 3.3 运行回归：`tests/unit/test_ui_routes.py`、`tests/unit/test_e2e_run_observe_semantics.py`、`tests/api_integration/test_e2e_example_client.py`

## 4. Change Validation

- [x] 4.1 更新 `docs/api_reference.md`，补充 `/v1/jobs/{request_id}/files` 与 `/v1/jobs/{request_id}/file`
- [x] 4.2 执行 `openspec validate e2e-file-preview-backend-rendering --type change`
- [x] 4.3 将 change 状态推进到 apply-ready（proposal/design/specs/tasks 全部就绪）
