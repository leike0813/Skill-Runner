## Context

当前系统有“超时终止”能力，但没有“用户主动终止”能力：  
- API 层缺少 cancel 入口；  
- 编排层缺少统一取消通道；  
- 可观测层缺少取消终态事件约定。  

这会导致前端无法在运行中让用户明确“停止此任务”，与 Run 对话窗口形态不匹配。

## Goals

1. 提供前端可调用、可审计、幂等的 Job 终止 API。
2. 统一 `queued/running/waiting_user` 三种活跃状态的终止行为。
3. 终止后统一落库/落盘为 `canceled`，并提供稳定错误码与原因字段。
4. 让状态接口与 SSE 流都可实时体现取消结果。

## Non-Goals

1. 不在本 change 引入复杂权限体系（默认沿用现有 API 访问控制）。
2. 不改变已有成功/失败结果结构，只补充取消语义。
3. 不新增 UI 页面（由 interactive-28 消费本能力）。

## Prerequisite

- `interactive-25-api-sse-log-streaming`

## Design

### 1) API 契约

新增两个动作端点：
- `POST /v1/jobs/{request_id}/cancel`
- `POST /v1/temp-skill-runs/{request_id}/cancel`

返回统一 `CancelResponse`：
- `request_id`
- `run_id`
- `status`（当前状态快照）
- `accepted`（本次是否触发了新的取消动作）
- `message`

语义：
- 目标不存在：`404`
- 已终态（`succeeded/failed/canceled`）：`200` + `accepted=false`（幂等）
- 活跃态（`queued/running/waiting_user`）：`200` + `accepted=true`

### 2) 运行态取消通道

引入 Run 级取消控制（Run Control）：
- 为每个 run 保存 `cancel_requested` 标记；
- 对运行中子进程暴露统一终止入口（复用 adapter 现有进程树终止逻辑）。

处理策略：
- `queued`：标记取消，避免后续真正执行（或进入执行后立即短路退出）。
- `running`：立即触发进程终止。
- `waiting_user`：视为活跃态，立即终止并结束 run。

### 3) 状态与错误模型

取消成功后统一写入：
- `status = canceled`
- `error.code = CANCELED_BY_USER`
- `error.message = "Canceled by user request"`

说明：
- `RunStatus.CANCELED` 作为唯一取消终态，不新增 `canceling`。
- 若取消信号已发出但进程尚未完全退出，状态轮询应在短时间内收敛到 `canceled`。

### 4) 资源回收与并发槽位

取消路径必须与正常终态共享收尾逻辑：
- 释放并发槽位；
- 清理 run folder trust 注入；
- 写入 status.json 与 runs.db；
- temp-skill-run 同步更新对应 request 记录。

### 5) 可观测与事件流

SSE / 状态接口需要明确取消终态可见性：
- 推送终态事件（`status=canceled`）；
- 保留取消前已产生的 stdout/stderr；
- 客户端在收到取消终态后可停止轮询/断开 SSE。

## Risks & Mitigations

1. **风险：排队中的任务取消不及时**
   - 缓解：引入 `cancel_requested` 并在进入执行关键路径前二次检查。
2. **风险：进程已退出与取消请求并发导致状态抖动**
   - 缓解：终态写入采用幂等更新，优先保持已终态，不回退状态。
3. **风险：不同入口（jobs/temp-skill-runs）语义不一致**
   - 缓解：共享同一取消服务层，路由仅做对象定位与鉴权。
