## Overview

本 change 将 engine 管理页的“状态视图”从现场探测改为缓存驱动。实现上引入单一的 `EngineStatusCacheService`，统一负责版本探测、缓存写入、缓存读取和每日后台刷新；management API 和 UI 只从该服务读取缓存结果，不再自行触发 CLI 检测。

## Goals

- 移除 engine 管理域的 auth probe 与 sandbox 摘要，避免继续暴露误导性状态。
- 保持 sandbox 观测仅存在于内置 shell/TUI banner。
- 将版本探测触发点限制在 startup、升级成功后、每日后台刷新三类受控场景。
- 保持缓存损坏或缺失时的页面/API 稳定输出，不在读路径补做现场探测。

## Non-Goals

- 不修改 auth session start/get/input/cancel API 与状态机。
- 不重做 `ui_shell_manager` 的 sandbox 探测逻辑。
- 不改变模型 manifest、opencode model catalog 的业务语义。

## Architecture

### EngineStatusCacheService

新增 `server/services/engine_management/engine_status_cache_service.py`，职责包括：

- 读取并解析 `data/agent_status.json`
- 以原子写入方式刷新缓存
- 全量版本探测 `refresh_all()`
- 单引擎版本探测 `refresh_engine(engine)`
- 提供缓存查询 `get_snapshot()` / `get_engine_status(engine)`
- 管理每日一次的 APScheduler 后台刷新任务

缓存文件继续沿用现有结构：

```json
{
  "codex": { "present": true, "version": "codex-cli 0.105.0" },
  "gemini": { "present": true, "version": "0.30.0" },
  "iflow": { "present": true, "version": "0.5.14" },
  "opencode": { "present": true, "version": "1.2.15" }
}
```

### AgentCliManager 复用

`AgentCliManager` 继续作为底层 CLI 探测能力提供者，但新增单引擎探测入口，例如 `collect_engine_status(engine)`，并让 `collect_status()` 复用同一底层逻辑。这样脚本 `scripts/agent_manager.py` 和服务内缓存刷新使用同一套探测逻辑。

### Startup / Daily Refresh

- 在 `server/main.py` 的 lifespan 中新增一次非阻断的 `refresh_all()`。
- startup refresh 失败只记录 warning，不阻断服务启动。
- `EngineStatusCacheService` 自带每日一次刷新任务，跟随应用生命周期启动/停止。

### Upgrade Hook

在 `server/services/engine_management/engine_upgrade_manager.py` 中：

- `mode=single` 且升级成功后，仅刷新该 engine 缓存。
- `mode=all` 时，对每个成功升级的 engine 分别刷新缓存。
- 升级失败的 engine 不刷新缓存，保留旧值。

### Management / UI Read Path

- `server/routers/management.py`
  - `GET /v1/management/engines` 只读版本缓存和模型数量。
  - `GET /v1/management/engines/{engine}` 只读缓存版本和模型详情。
  - 删除 `_derive_sandbox_status(...)` 与 `collect_auth_status()` 依赖。
- `server/routers/engines.py`
  - 删除 `GET /v1/engines/auth-status`。
- `server/routers/ui.py`
  - `/ui/engines` 直接 SSR 渲染 engine 表格。
  - `/ui/management/engines/table` 与 `/ui/engines/table` 保留为兼容 partial，但仅仅读缓存。

### ModelRegistry Version Source

`ModelRegistry` 不再在读路径直接调用 `_detect_cli_version()`。版本来源改为 `EngineStatusCacheService`：

- `list_engines()` 返回缓存版本
- `get_models()` / `get_manifest_view()` / `add_snapshot_for_detected_version()` 从缓存读取 `cli_version_detected`
- 若缓存缺失，返回 `None` 并按既有 snapshot fallback 逻辑处理，不触发 CLI probe

## Risks and Mitigations

### 风险：startup 刷新失败导致 UI/version 空值

对策：
- 缓存读取层对缺失/损坏场景返回 `None`
- 页面用 `-` 展示缺失版本
- API 保持稳定结构，不改为现场探测

### 风险：测试仍 monkeypatch 旧 auth probe 或 UI 延迟加载路径

对策：
- 全量替换 management/UI 相关测试断言
- 删除 `/v1/engines/auth-status` 相关测试
- 更新 `/ui/engines` 的 HTML 断言为 SSR 输出

### 风险：升级流程刷新缓存引入竞态

对策：
- 缓存服务内部使用锁和原子写入
- 每次单引擎刷新只更新对应 key，再整体落盘

## Validation

- `pytest tests/unit/test_engine_status_cache_service.py tests/unit/test_management_routes.py tests/unit/test_ui_routes.py tests/unit/test_v1_routes.py tests/api_integration/test_management_api.py tests/api_integration/test_ui_management_pages.py`
- 如升级链路受影响，补跑 `tests/unit/test_engine_upgrade_manager.py tests/unit/test_agent_cli_manager.py`
- `mypy --follow-imports=skip server/services/engine_management/engine_status_cache_service.py server/services/engine_management/agent_cli_manager.py server/services/engine_management/engine_upgrade_manager.py server/services/engine_management/model_registry.py server/routers/management.py server/routers/engines.py server/routers/ui.py server/models/management.py`
