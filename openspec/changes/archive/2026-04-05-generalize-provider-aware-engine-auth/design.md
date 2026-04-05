## Context

当前实现里，provider-aware 能力已经不再只属于 `opencode`：

- `opencode` 与 `qwen` 都通过 provider registry 暴露 provider 元数据；
- 鉴权能力矩阵、UI provider 菜单、导入规格、driver 注册和运行时 auth 恢复都已改为共享逻辑；
- `provider_id` 已经成为 run/auth 主链路中的规范选择器；
- 旧的 `opencode` `provider/model` 仅作为兼容回退保留。

如果继续把这些变化只写在 qwen change 里，会让后续维护无法区分“共享层契约”与“qwen 引擎特性”。

## Design Decisions

1. **共享层独立归档**  
   以独立 change 记录 provider-aware 公共层，不让 qwen change 成为共享能力的 SSOT。

2. **`provider_id` 作为规范输入**  
   文档和规格统一把 `provider_id` 定义为 provider-aware engine 的规范选择器；`opencode` 的 `provider/model` 旧格式只保留兼容说明。

3. **provider-aware 能力由后端声明驱动**  
   provider 列表、方法矩阵、导入可见性和模型 provider 元数据都以后端声明结果为准，不再由 UI 或 docs 推导默认规则。

4. **不引入新 API**  
   本 change 仅同步既有实现的公共契约，不新增公开路由或新 payload family。

## Architecture

### 1) Shared Strategy And Auth Surface

- `engine-auth-strategy-policy` 记录 provider-aware engine 的 provider-scoped 能力矩阵；
- `management-api-surface` 记录 provider-aware model metadata、auth start/import 的 `provider_id` 语义；
- `ui-engine-management` 记录 provider-aware provider 选择、import 可见性和菜单来源。

### 2) Run/Auth Canonical Provider Resolution

- `job-orchestrator-modularization` 记录 provider-aware engine 优先使用显式 `provider_id`；
- `opencode` 的 `provider/model` 解析仅作为 legacy fallback。

### 3) Runtime Config And Model Catalog Semantics

- `engine-runtime-config-layering` 统一记录 `qwen` 已并入统一分层；
- provider-aware 静态模型也可以在 manifest 模式下通过 `provider/provider_id/model` 元数据暴露区分信息。

## Compatibility

- 不改变公开路由路径；
- 不移除旧 `opencode` `provider/model` 提交方式；
- 新文档口径以推荐写法优先，但保留兼容事实说明。
