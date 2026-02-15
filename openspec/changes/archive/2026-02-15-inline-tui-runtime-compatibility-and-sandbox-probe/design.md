## Context

上一版将 UI 内嵌终端设计为 fail-closed：只要 sandbox 不可确认就拒绝启动。  
该策略在安全上保守，但当前对 Gemini/iFlow 的能力判定过严，实际导致功能不可用（503）。同时，Codex 存在“启动成功但用户看不到任何输出”的可观测性缺口。

本次目标是：先恢复三引擎可用性，再把沙箱能力“探测并展示”，而不是“硬拒绝”。

## Goals

1. Codex/Gemini/iFlow 都可从 `/ui/engines` 启动 TUI。
2. 启动后终端必须立即出现可见反馈，不再出现“空白假死”。
3. 保留白名单命令、单会话、隔离目录等现有边界。
4. 沙箱能力从“阻断条件”改为“状态可观测”。

## Non-Goals

1. 不在本次引入多会话。
2. 不在本次开放任意命令执行。
3. 不在本次完成各引擎 sandbox 的最终强制策略（后续再收敛）。

## Design

### 1) 启动策略

- 将 `_check_sandbox_available` 从“raise -> 拒绝启动”改为返回结构化探测结果：
  - `supported`
  - `unsupported`
  - `unknown`
- `start_session(engine)` 不再因探测结果失败返回 503；仅在 CLI 不存在、会话冲突等硬错误时失败。

### 2) 探测机制（无 token）

- probe 仅做本地能力判断，不调用模型推理接口。
- 示例：
  - codex：读取 Landlock / 启动参数可用性线索。
  - gemini / iflow：检测已知 sandbox 配置键是否存在并可注入（best-effort）。
- probe 结果写入：
  - 会话快照字段（返回给 UI）
  - 服务日志（便于排障）

### 3) 输出握手与可观测

- WebSocket accept 后立即发送 state 帧（含当前会话状态）。
- 启动成功后由后端写入一条握手输出到 ring buffer（例如 `[session xxx] engine=gemini started`）。
- 前端终端收到握手帧后即时渲染，避免“无输出”误判。

### 4) UI 展示

- 在终端卡片增加 sandbox 状态 badge：
  - `sandbox: supported/unsupported/unknown`
- 当 `unsupported/unknown` 时显示非阻断 warning，而不是阻断错误。

## Risks & Mitigations

1. **风险：放宽 fail-closed 可能增加越权风险**
   - 缓解：保持白名单命令 + 单会话 + 会话目录隔离 + agent_home 隔离。
2. **风险：probe 判断不准确**
   - 缓解：结果定义为 best-effort，可观测优先，不作为拒绝条件。

## Test Strategy

1. 服务层：
   - 三引擎在 probe=`unsupported` 时仍可启动。
   - 会话快照包含 `sandbox_status` 字段。
2. 路由层：
   - 启动接口不再返回 503（sandbox 场景）。
   - WS 建连后立刻收到 state 帧。
3. UI 层：
   - 启动后可见握手输出。
   - 展示 sandbox 状态 warning。

