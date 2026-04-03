## Context

当前命令默认参数有三条来源：各引擎 `config/command_profile.json`、`engine_command_profile.py` 的集中加载，以及 Claude builder 内部的硬编码默认参数。这导致 adapter profile 虽然已经是执行合同主入口，但命令默认值仍然是旁路配置，且不同引擎的职责分配不一致。

## Goals / Non-Goals

**Goals:**
- 让 `adapter_profile.json` 成为命令默认参数的唯一来源
- 删除旧的 command profile 读取旁路，不保留双轨兼容
- 让 Claude 与其他引擎在 builder 职责上完全对齐
- 保持现有 CLI 运行行为等价

**Non-Goals:**
- 不修改任何 engine 的默认 flag 语义
- 不新增外部 HTTP API
- 不改变 harness passthrough / API profile defaults 的既有语义

## Decisions

### 决策 1：把 `command_defaults` 并入 `adapter_profile.json`
- 方案：在 `adapter_profile_schema.json` 中新增必填 `command_defaults.start/resume/ui_shell`
- 原因：adapter profile 已是执行合同的主入口，把命令默认参数并入这里才能形成单一合同
- 备选方案：保留独立 `command_profile.json`
  - 放弃原因：仍然会保留旁路配置，Claude 的 builder 差异也无法真正收口

### 决策 2：硬切删除旧 loader 与旧配置文件
- 方案：删除 `engine_command_profile.py`、registry 中相关路径常量、以及各引擎 `config/command_profile.json`
- 原因：双轨兼容会继续制造歧义，也会让治理测试和文档继续漂移
- 备选方案：过渡期兼容读取
  - 放弃原因：没有技术必要，且会延长不一致窗口

### 决策 3：保留参数合并算法，但迁到 runtime common
- 方案：保留 `merge_cli_args` 语义，迁到 `server/runtime/adapter/common/command_defaults.py`
- 原因：builders 仍需要稳定的“显式参数覆盖默认参数”算法，但不应再依赖已删除的 command profile service
- 备选方案：在每个 builder 内复制实现
  - 放弃原因：会重新引入跨引擎重复逻辑

### 决策 4：UI shell 直接读 adapter profile
- 方案：`EngineShellCapabilityProvider` 通过 engine 的 `adapter_profile.json` 读取 `command_defaults.ui_shell`
- 原因：UI shell 默认参数与 start/resume 属于同一命令默认参数域，必须共用同一合同
- 备选方案：保留 provider 内部手写 default map
  - 放弃原因：会形成新的隐式旁路

## Risks / Trade-offs

- [Risk] 现有测试中大量 monkeypatch 旧 loader 路径 -> Mitigation：统一改为 monkeypatch `adapter.profile.resolve_command_defaults`
- [Risk] 某些文档/治理守卫仍引用旧文件名 -> Mitigation：同步更新文档与守卫测试，防止后续回归
- [Risk] Claude builder 去硬编码后如果 profile 缺字段会直接 fail-fast -> Mitigation：`command_defaults` 设为 schema 必填并在所有 engine profile 中补齐
