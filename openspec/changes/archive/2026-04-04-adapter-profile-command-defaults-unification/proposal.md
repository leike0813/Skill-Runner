## Why

当前 engine 命令默认参数同时分散在 `adapter_profile.json` 之外的 `command_profile.json` 和部分 builder 硬编码中，Claude 还与其他引擎职责分配不一致。这让 adapter profile 不是完整主合同，也让 UI shell / start / resume 的命令来源出现旁路漂移。

## What Changes

- **BREAKING** 将所有 engine 的 `start / resume / ui_shell` 默认命令参数从独立 `command_profile.json` 收口到 `adapter_profile.json.command_defaults`
- 删除独立 `engine_command_profile.py` 加载链与各引擎 `config/command_profile.json`
- 让所有 adapter 与 UI shell capability provider 统一从 `AdapterProfile.command_defaults` 读取默认参数
- 对齐 Claude 的 builder 职责边界，移除其对默认 `stream-json` 参数的硬编码

## Capabilities

### New Capabilities
- None

### Modified Capabilities
- `engine-command-profile-defaults`: 默认命令参数的合同改为由 adapter profile 承载，不再使用独立 command profile 文件
- `engine-adapter-runtime-contract`: adapter profile 新增 `command_defaults`，adapter/UI shell 必须从该字段读取 start、resume 与 ui shell 默认参数

## Impact

- Affected code:
  - `server/runtime/adapter/common/profile_loader.py`
  - `server/runtime/adapter/common/command_defaults.py`
  - `server/engines/*/adapter/*`
  - `server/services/ui/engine_shell_capability_provider.py`
  - `server/config_registry/*`
- Removed files:
  - `server/services/engine_management/engine_command_profile.py`
  - `server/engines/*/config/command_profile.json`
- Tests and docs covering adapter contracts and command defaults need to be updated to the new single-source contract.
