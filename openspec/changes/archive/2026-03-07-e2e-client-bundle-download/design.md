## Context

后端已提供 run bundle 下载接口（`/v1/jobs/{request_id}/bundle`），管理 UI 可直接使用。  
E2E 客户端当前已有 bundle entries/file 预览链路，但没有完整 zip 下载动作，导致用户需要离开 E2E 页面进行额外操作。

## Goals / Non-Goals

**Goals:**
- 在 E2E Run Observation 页面内提供完整 bundle 下载能力。  
- 复用现有后端 bundle 下载接口，不新增后端业务 API。  
- 保持 E2E 代理错误模型一致（`BackendApiError` 与 `backend_unreachable`）。

**Non-Goals:**
- 不修改 run bundle 生成逻辑。  
- 不新增 run artifact 打包格式。  
- 不改管理 UI 下载能力与交互。

## Decisions

### 1) 通过 E2E 代理转发下载

- 新增 E2E 代理接口：`GET /api/runs/{request_id}/bundle/download`。  
- 由该接口调用 `backend.get_run_bundle(...)` 获取 bytes，并以 `application/zip` + attachment 返回。

**Rationale:**  
保持 E2E 前端只调用本地 `/api/*`，不直接跨域访问后端。

### 2) Run Observation 使用直接下载链接

- 在 `run_observe.html` 文件区操作栏增加下载按钮。  
- 按钮点击采用浏览器原生下载（`window.location` 或 `<a href>`）而非 fetch blob。

**Rationale:**  
实现简单稳定，避免额外 blob 生命周期管理。

### 3) 错误处理与文案

- 后端返回非 2xx 时，E2E 代理维持统一错误转换逻辑。  
- 页面层在下载失败后显示现有风格的错误提示文案（i18n）。

**Rationale:**  
与现有 E2E 客户端错误体验保持一致，减少新分支。

## Risks / Trade-offs

- [Risk] 大 bundle 下载时响应耗时高  
  → Mitigation: 首版保持现状，后续可评估 StreamingResponse 直通。

- [Risk] run source/参数不一致导致拿错 run  
  → Mitigation: 复用当前页面已确定的 request_id（及必要 run source 传参路径）。

- [Risk] 下载失败提示不明显  
  → Mitigation: 补充显式 i18n 错误文案并复用现有错误展示组件。

## Migration Plan

1. 新增 E2E 代理下载路由与 backend client 方法（如缺失则补齐）。  
2. 在 Run Observation 文件区加入下载入口并接入 i18n。  
3. 补充/更新单测与 API 集成测试。  
4. 运行 OpenSpec validate，进入 apply 实施。

## Open Questions

- None.
