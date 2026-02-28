## Why

adapter 侧已完成结构迁移，但仍残留旧单体 `adapter.py` 与 `server/adapters/base.py` 依赖，导致新旧双轨并存，扩展和维护成本高。

同时，`prompt_builder`、`session_codec`、`workspace_provisioner` 在四引擎中重复度高，尚未形成 runtime 侧公共复用层。

## What Changes

1. 删除四个引擎旧单体 `adapter.py`，移除 `build_adapter()` 入口。
2. `engine_adapter_registry` 直接实例化各引擎 `execution_adapter.py` 中的类（不再经 entry 工厂）。
3. 将 `server/adapters/base.py` 的通用类型与执行辅助能力迁移至 `server/runtime/adapter/*`，并删除 `base.py`。
4. 新增 `server/runtime/adapter/common/*`，抽取高重复组件逻辑：
   - prompt 构建公共步骤
   - session handle 提取公共步骤
   - workspace 技能安装与 patch 公共步骤
   - profile loader + schema 校验（fail-fast）
5. 保持 `/v1` 与 `/ui` 对外接口语义不变。

## Scope

### In Scope

1. adapter 运行链路收敛到 execution adapter。
2. runtime/common 通用组件抽象与引擎组件薄化。
3. 相关测试与开发者文档更新。

### Out of Scope

1. 不新增引擎能力。
2. 不调整 auth 协议语义。
3. 不变更任何公共 HTTP API 契约。

## Success Criteria

1. 全仓不存在 `server/engines/*/adapter/adapter.py`。
2. 全仓不存在 `server/adapters/base.py` 引用与文件本体。
3. registry 与 orchestrator 仅通过 execution adapter 工作。
4. 四引擎运行与 session 续跑行为无回归。
