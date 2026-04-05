## Context

Qwen Code 已经以 engine-specific 目录接入当前架构，但早期设计文案仍停留在原始骨架阶段，和实际实现已有明显偏差：

- CLI 已不再使用 `qwen exec --session`；
- 模型目录并非 `runtime_probe` 主路径，而是静态 manifest + snapshot；
- Qwen 鉴权不再是孤立实现，而是挂在共享 provider-aware 基础设施上；
- 配置分层已经对齐到统一的 `engine_default -> skill defaults -> runtime overrides -> enforced`。

本设计文档以当前已落地实现为准。

## Design Decisions

1. **Qwen 作为一等公民 engine**  
   `qwen` 拥有独立 adapter/auth/config/models 目录，并通过集中注册点接入系统。

2. **CLI 契约对齐官方实现**  
   非交互执行使用顶层 `qwen` 命令，默认参数为：
   - start: `qwen --output-format stream-json --approval-mode yolo -p "<prompt>"`
   - resume: `qwen --output-format stream-json --approval-mode yolo --resume <session_id> -p "<prompt>"`

3. **静态 snapshot 模型目录**  
   Qwen 走标准 manifest 模式，使用版本化 snapshot 文件记录 provider-aware 模型条目，而不是 runtime probe。

4. **统一配置分层**  
   运行时配置从 `default.json` 起算，再叠加 skill defaults、runtime overrides、request model overlay 与 `enforced.json`，最终写入 `run_dir/.qwen/settings.json`。

5. **共享 provider-aware 鉴权基础设施**  
   Qwen 的 provider 列表、能力矩阵、导入可见性和 runtime handler 均挂在共享 provider-aware 基础设施上，不再自行维护一套平行规则。

## Architecture

### 1) Execution Adapter

`QwenExecutionAdapter` 由以下组件构成：

- `QwenCommandBuilder`
- `QwenStreamParser`
- `QwenConfigComposer`
- `ProfiledSessionCodec`

运行目录使用 `.qwen/`，技能注入到 `.qwen/skills/`。

### 2) Model Catalog

Qwen 使用静态 manifest：

- `manifest.json` 声明 snapshot 文件
- snapshot 模型项可包含 `provider`、`provider_id`、`model`

当前 provider-aware 静态模型为：

- `qwen-oauth` -> `coder-model`
- `coding-plan-china` -> curated static entries
- `coding-plan-global` -> curated static entries

### 3) Auth

Qwen 暴露三个官方 provider：

- `qwen-oauth`
- `coding-plan-china`
- `coding-plan-global`

能力矩阵由 `auth_strategy.yaml` 驱动：

- `qwen-oauth`: `oauth_proxy|cli_delegate` + `auth_code_or_url`
- `coding-plan-*`: `oauth_proxy|cli_delegate` + `api_key`

导入能力在本轮仅对 `qwen-oauth` 开放，导入文件名为 `oauth_creds.json`。

### 4) Management And Bootstrap

- 托管安装包：`@qwen-code/qwen-code`
- `binary_candidates`: `qwen`, `qwen.cmd`, `qwen.exe`
- `qwen` 已纳入默认 bootstrap/ensure、upgrade manager、engine status cache 和管理 UI

## Failure Handling

1. CLI 未找到：显式报错，不静默降级。
2. Qwen 输出无法解析为结构化结果：走现有 deterministic repair / 失败回退。
3. session id 缺失：resume 明确失败，不伪造 session handle。
4. coding-plan import 未开放：通过 provider-aware import 能力显式隐藏或拒绝。

## Future Work

- live stream parser
- `stream_event` / `tool_call` 细粒度协议映射
- 更完整的 Qwen OAuth 浏览器回调形态
