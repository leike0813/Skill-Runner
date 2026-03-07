## Context

当前文件预览能力已在后端形成 canonical 渲染链路（格式识别、markdown 安全清洗、代码高亮、too_large/binary 回退）。  
但 E2E Run Observation 仍在客户端代理层通过 bundle bytes 本地构建预览，导致与管理 UI 存在渲染分叉。  
该分叉使“同一文件跨页面结果不一致”成为常态风险，并放大环境依赖差异（例如 markdown/bleach 在不同进程环境可用性不同）。

## Goals / Non-Goals

**Goals:**
- 将 E2E 文件预览真相源收敛为后端 canonical 渲染结果。
- 保持 E2E 文件树/预览交互体验不变（默认折叠、点击预览、格式化展示）。
- 在 jobs 主 API 下提供稳定、可复用的 run 文件读取接口，避免 E2E 依赖 management 专用接口。
- 保持 bundle 下载功能与现有协议语义不变。

**Non-Goals:**
- 不修改 FCMP/RASP/chat 协议。
- 不调整管理 UI 现有文件预览实现。
- 不扩展新的文件渲染格式能力（仅复用现有能力）。

## Decisions

### 1) 预览真相源统一到后端 jobs 接口

- 决策：新增 `/v1/jobs/{request_id}/files` 与 `/v1/jobs/{request_id}/file?path=...` 两个只读接口。
- 原因：
  - E2E 本应走 jobs 主链路；
  - 避免耦合 management API 鉴权/语义；
  - 让所有前端消费同一后端预览载荷。
- 备选方案：
  - 直接复用 management 文件接口；拒绝，原因是跨域职责不清且未来权限策略可能分叉。

### 2) E2E 不再本地解析 bundle 做预览

- 决策：E2E `/api/runs/{request_id}/bundle/file` 和 `/runs/{request_id}/bundle/view` 改为后端透传（调用 jobs 文件接口），不再 `ZipFile + build_preview_payload_from_bytes`。
- 原因：
  - 消除渲染分叉；
  - 彻底规避 E2E 进程依赖漂移带来的不一致。
- 备选方案：
  - 仅给 E2E 补依赖；拒绝，原因是仍保留双轨实现，长期继续漂移。

### 3) 路径安全边界保持 run_dir 内

- 决策：新 jobs 文件接口沿用 run 文件读取安全边界：仅允许相对路径、禁止 `..`、禁止绝对路径。
- 原因：
  - 文件预览是只读能力，但仍涉及敏感目录访问风险。

## Risks / Trade-offs

- [Risk] 新增 jobs 文件接口后，若与现有 management 接口行为不一致，会再次出现双真相。  
  → Mitigation：两者都调用同一 `run_observability_service` 文件枚举/预览函数。

- [Risk] E2E 仍保留 bundle tree 旧逻辑残留导致行为混用。  
  → Mitigation：删除/弃用本地 bundle 预览构建函数，测试添加“E2E 不再本地构建 preview”的守卫断言。

- [Risk] 文件较多时接口调用频率上升。  
  → Mitigation：保持当前按需点击预览，不引入批量预取。

## Migration Plan

1. 后端先增加 jobs 文件树/预览接口与响应模型。  
2. E2E 后端客户端与路由改为调用 jobs 文件接口。  
3. 移除 E2E 本地 bundle 预览构建路径（仅保留 bundle 下载）。  
4. 更新 `docs/api_reference.md`，补充两个新增接口的参数、响应与错误码。  
5. 更新单测与集成测试。  
6. `openspec validate --change e2e-file-preview-backend-rendering` 通过后进入实现。

回滚策略：
- 若出现异常，可临时回退到旧 E2E 本地 bundle 预览路径（代码层面保留一版可回滚提交），不影响主服务运行。

## Open Questions

- 无。当前方案的接口归属、渲染真相源、路径安全策略已确定。
