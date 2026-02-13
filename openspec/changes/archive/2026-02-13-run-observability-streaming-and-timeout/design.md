## Context

本变更聚焦执行观测层，不改变任务编排主流程。核心原则：

- request_id 继续作为对外主键；
- run_id 作为内部执行实体用于文件与日志观测；
- 页面只读，不引入在线编辑行为。

## Decisions

### 1) Run 观测模型

- 在 `RunStore` 增加 request/run 关联查询能力：
  - 单条：按 request_id 获取关联 run 记录；
  - 列表：按创建时间倒序获取 request/run 组合。
- 新增 `RunObservabilityService`，统一负责：
  - run 列表聚合；
  - run 详情构建（状态、文件状态、目录树）；
  - run 文件路径解析与只读预览；
  - stdout/stderr tail 读取。

### 2) 流式日志写盘

- `_capture_process_output` 改为边读边写：
  - 进程启动后立即清空旧日志文件；
  - 按块读取 stdout/stderr 并持续 append + flush；
  - 进程结束后直接拼接内存 chunk 返回，不再二次整写文件。
- 保持 hard-timeout 与 auth-pattern 分类逻辑不变。

### 3) UI 路由与模板

- 新增路由：
  - `GET /ui/runs`
  - `GET /ui/runs/table`
  - `GET /ui/runs/{request_id}`
  - `GET /ui/runs/{request_id}/view`
  - `GET /ui/runs/{request_id}/logs/tail`
- 页面行为：
  - 列表自动刷新；
  - 详情页展示文件树与文件状态；
  - 日志区域在运行态按固定间隔轮询 tail。

### 4) 超时配置基线

- `ENGINE_HARD_TIMEOUT_SECONDS` 默认值改为 1200。
- 允许运行时通过环境变量覆盖，避免容器与本地行为不一致。

## Trade-offs

- 流式写盘会增加 I/O 次数，但换来明显更高的可观测性和排障效率。
- 日志轮询采用稳妥实现（HTTP polling），暂不引入 WebSocket/SSE 复杂度。
