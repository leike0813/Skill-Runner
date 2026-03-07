## Why

当前同一文件在管理 UI 能正确渲染、在 E2E 客户端却退化为纯文本，根因是两端预览链路分叉：管理 UI 使用后端渲染，E2E 本地解析 bundle 并本地渲染。  
这种双轨实现导致依赖、格式识别和安全清洗行为不一致，已经造成实际观测偏差。

## What Changes

- 为 `/v1/jobs/{request_id}` 增加统一的 run 文件树与文件预览读取接口，返回后端 canonical 预览载荷。
- E2E Run Observation 文件树/预览改为消费上述后端接口，不再在 E2E 侧解压 bundle 并本地渲染。
- 保持 bundle 下载能力不变，仅将“预览渲染真相源”收敛到后端。
- 保持预览 payload 向后兼容（`mode/content/meta/size`）并沿用扩展字段（`detected_format/rendered_html/json_pretty`）。
- 同步更新 `docs/api_reference.md`，补充新增 jobs 文件树/预览接口说明与示例。

## Capabilities

### New Capabilities

- 无

### Modified Capabilities

- `interactive-job-api`: 增加面向 jobs 主链路的 run 文件树/预览读取接口约束，并要求预览载荷由后端 canonical 渲染生成。
- `builtin-e2e-example-client`: 要求 E2E 文件预览使用后端 canonical 预览结果，不再本地构建预览。

## Impact

- Affected code:
  - `server/routers/jobs.py`
  - `server/models.py`（或 `server/models/*` 中 jobs API 对应响应模型）
  - `e2e_client/backend.py`
  - `e2e_client/routes.py`
  - `e2e_client/templates/run_observe.html`
- API impact:
  - 新增只读 jobs 文件接口（不影响现有写入/执行语义）。
- Dependencies:
  - 不新增依赖。
- Risk:
  - 需要确保新接口只允许 `run_dir` 内安全路径访问，避免路径穿越。
- Docs:
  - `docs/api_reference.md` 需新增两条 jobs 文件读取接口文档。
