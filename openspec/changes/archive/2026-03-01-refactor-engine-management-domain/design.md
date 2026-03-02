## Context

`services/orchestration` 在历史演进中承载了 run 编排与 engine 管理两类职责。  
在当前代码形态下，engine 管理模块（auth/upgrade/model/policy/profile/adapter registry）被 routers、engines adapters、skill 服务、UI 服务和测试广泛引用，导致“编排域”目录语义被稀释。

本次重构将 engine-domain 模块迁移到 `services/engine_management`，以目录边界显式表达责任归属，并一次性切换引用路径。

## Goals / Non-Goals

**Goals**
- 建立 `server/services/engine_management` 作为 engine 管理域唯一实现位置。
- 迁移 11 个既有模块并保持行为等价。
- 一次性完成全仓 import 切换，不保留兼容壳。
- 同步文档和测试，确保路径与职责描述一致。

**Non-Goals**
- 不新增 engine 管理功能。
- 不修改 HTTP API、runtime schema/invariants、状态机定义。
- 不改变 auth/upgrade/model/policy/runtime-profile 的业务语义。

## Decisions

### 1) Package split by responsibility boundary
- 新增包：`server/services/engine_management/`
- 迁移模块：
  - `agent_cli_manager.py`
  - `engine_adapter_registry.py`
  - `engine_auth_bootstrap.py`
  - `engine_auth_flow_manager.py`
  - `engine_command_profile.py`
  - `engine_interaction_gate.py`
  - `engine_policy.py`
  - `engine_upgrade_manager.py`
  - `engine_upgrade_store.py`
  - `model_registry.py`
  - `runtime_profile.py`

### 2) One-shot import cutover (no compatibility layer)
- 所有业务代码、路由、引擎适配器、测试 import 一次性改新路径。
- 删除 orchestration 对应旧模块文件，不提供 alias/re-export 壳。

### 3) Keep symbols stable
- 保持 public class/function/singleton 名称不变（例如 `model_registry`、`engine_auth_flow_manager`）。
- 调用方只需改 import path，不改调用语义。

### 4) Keep dependency direction explicit
- `services/orchestration` 可依赖 `services/engine_management`。
- engine/domain 逻辑不再反向挤入 orchestration 目录。

## Risks / Trade-offs

- [Risk] monkeypatch 路径大面积变更导致测试失败。  
  -> Mitigation: 统一替换字符串路径并优先执行 engine 管理相关测试组。

- [Risk] 文本断言测试依赖旧文件路径。  
  -> Mitigation: 同步更新路径断言用例（例如 import-boundary/path invocation tests）。

- [Risk] 模块级单例导入时序变化导致行为偏差。  
  -> Mitigation: 迁移时保持文件内容与初始化位置等价，不改构造流程。

## Migration Plan

1. 创建 OpenSpec artifacts（proposal/spec/design/tasks）。
2. 新建 `server/services/engine_management/__init__.py`。
3. 将 11 个模块迁移到 `engine_management`。
4. 全仓替换业务代码导入路径（orchestration/router/engines/skill/ui）。
5. 全仓替换测试 import、monkeypatch、文件路径断言。
6. 删除 orchestration 中迁移出的旧模块文件。
7. 更新文档。
8. 执行残留扫描 + 单测回归 + mypy。
