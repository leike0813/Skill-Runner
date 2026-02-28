## Why

phase1 已经完成目录骨架与基础迁移，但仍存在两类问题：
1. engine 相关代码在文件组织上已迁移，仍缺少“phase2 完成态”的规范化声明与实施收口。
2. 新抽象（auth driver / adapter components）缺少开发者导向文档，新增引擎与维护成本仍高。

本 change 用于确认 phase2 完成态：删除旧桥接实现路径、固化 engine 垂直目录与 runtime 内核职责边界，并补齐开发者文档。

## What Changes

1. 将 engine-specific auth 与 adapter 统一收敛到 `server/engines/<engine>/...`。
2. 将 auth runtime 核心统一收敛到 `server/runtime/auth/...`，并删除 `server/services/auth_runtime/*` 旧路径。
3. 将四引擎 adapter 实现迁移到 `server/engines/*/adapter/adapter.py`，删除 `server/adapters/{codex,gemini,iflow,opencode}_adapter.py`。
4. 保持 `/v1` 与 `/ui` 公开鉴权接口兼容，内部由 runtime/orchestrator + engine driver 组合承载。
5. 新增开发者文档：
   - `docs/developer/auth_runtime_driver_guide.md`
   - `docs/developer/adapter_component_guide.md`
   - `docs/developer/engine_onboarding_example.md`

## Scope

### In Scope

1. auth runtime / engine auth / engine adapter 的目录与导入重组。
2. 旧桥接实现文件移除（非 API 层）。
3. 回归测试、mypy、OpenSpec 校验。
4. 开发者文档（接口 + 流程 + 示例）交付。

### Out of Scope

1. 不新增 provider 或新引擎能力。
2. 不改变对外 HTTP 路径与请求语义。
3. 不修改业务协议（FCMP/RASP）定义。

## Success Criteria

1. engine-specific 代码可在 `server/engines/<engine>/adapter|auth` 完整定位。
2. `server/services/auth_runtime/*` 与旧 adapter 文件不再作为运行实现存在。
3. 鉴权与 adapter 相关回归测试通过，且 mypy 通过。
4. 开发者可基于新文档完成“新增引擎最小接入”。
