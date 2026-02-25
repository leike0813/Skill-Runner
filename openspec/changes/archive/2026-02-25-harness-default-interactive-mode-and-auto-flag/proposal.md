## Why

当前 Harness 路线没有显式 execution mode 开关，且默认按 `auto` 模式补丁与执行，这与交互续跑主流程不一致，也不利于在调试/对话式场景下直接进入 `interactive`。  
需要将默认行为切换为 `interactive`，同时保留一个显式入口让用户按需回到 `auto`。

## What Changes

- **BREAKING**：Harness `start` 与直接引擎语法的默认 execution mode 从 `auto` 切换为 `interactive`。
- 新增 Harness 控制参数 `--auto`（位于 engine 参数之前），用于显式指定 `execution_mode=auto`。
- `--auto` 仅作为 Harness 控制参数，MUST NOT 透传至引擎命令参数。
- Harness 执行链路增加 execution mode 传递：CLI -> runtime -> skill 注入补丁/配置注入元数据。
- `resume` 路径复用 handle 中记录的 execution mode；若历史 handle 缺失该字段，回退为 `interactive`。
- 更新 Harness 相关规范与文档，消除“默认 auto”假设。

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `external-runtime-harness-cli`: 修正 start/直接语法的参数合同与默认模式行为。
- `harness-shared-adapter-execution`: 修正 Harness 在共享 Adapter 执行链路中的 execution mode 传递与 resume 继承语义。

## Impact

- Affected code:
  - `agent_harness/cli.py`
  - `agent_harness/runtime.py`
  - `agent_harness/skill_injection.py`
  - `agent_harness/storage.py`（handle metadata 扩展）
  - Harness 相关单测（CLI/runtime）
- Affected behavior:
  - 未显式传 `--auto` 的 Harness start 将按 `interactive` 路径补丁与执行。
  - 已依赖默认 `auto` 的脚本需补充 `--auto`。
- Compatibility:
  - 旧 handle 在缺失 execution mode 元数据时回退 `interactive`，避免 resume 失败。
