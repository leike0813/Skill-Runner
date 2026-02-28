## 1. OpenSpec

- [x] 1.1 新建 `engine-auth-adapter-verticalization-core-phase2` 四工件与 delta specs
- [x] 1.2 运行 `openspec validate engine-auth-adapter-verticalization-core-phase2 --type change`

## 2. Runtime/Auth Migration

- [x] 2.1 `server/runtime/auth` 下沉 `session_store` / `log_writer` / `callback_router`
- [x] 2.2 路由与 manager 接线到 `server/runtime/auth/*`
- [x] 2.3 删除 `server/services/auth_runtime/*` 旧路径实现

## 3. Engine Auth Verticalization

- [x] 3.1 codex auth 协议实现迁移到 `server/engines/codex/auth/protocol/*`
- [x] 3.2 gemini auth 实现迁移到 `server/engines/gemini/auth/{protocol,drivers,callbacks}/*`
- [x] 3.3 iflow auth 实现迁移到 `server/engines/iflow/auth/{protocol,drivers,callbacks}/*`
- [x] 3.4 opencode auth 实现迁移到 `server/engines/opencode/auth/{protocol,drivers,callbacks}/*`

## 4. Engine Adapter Verticalization

- [x] 4.1 删除 `server/adapters/{codex,gemini,iflow,opencode}_adapter.py`
- [x] 4.2 四引擎 adapter 主实现迁移到 `server/engines/*/adapter/adapter.py`
- [x] 4.3 新增四引擎 6 组件文件并通过 `entry.py` 装配
- [x] 4.4 `EngineAdapterRegistry` 使用 `server/engines/*/adapter` 入口装配

## 5. Verification

- [x] 5.1 回归测试：
  - `test_engine_auth_flow_manager.py`
  - `test_oauth_proxy_orchestrator.py`
  - `test_cli_delegate_orchestrator.py`
  - 四引擎 adapter 相关测试
  - `test_ui_routes.py`
- [x] 5.2 mypy 覆盖 `server/runtime/*`、`server/engines/*` 与接线入口

## 6. Developer Docs

- [x] 6.1 新增 `docs/developer/auth_runtime_driver_guide.md`
- [x] 6.2 新增 `docs/developer/adapter_component_guide.md`
- [x] 6.3 新增 `docs/developer/engine_onboarding_example.md`
