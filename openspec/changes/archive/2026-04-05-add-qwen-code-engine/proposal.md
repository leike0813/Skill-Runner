## Why

当前系统已经支持 `codex`、`gemini`、`iflow`、`opencode`、`claude`，但在本轮之前缺少 `qwen` 这一等公民 engine。  
缺少 Qwen Code 支持会带来三个直接问题：

1. 无法在 Skill Runner 中执行 Qwen Code 生态的 skills；
2. 管理 UI、bootstrap/install 与模型管理在引擎枚举上不一致；
3. 运行时与鉴权链路无法复用 Qwen 官方的 OAuth / Coding Plan 能力。

本 change 只记录 qwen engine 自身接入与对齐内容。共享的 provider-aware 公共层抽象由独立 change `2026-04-04-generalize-provider-aware-engine-auth` 记录。

## What Changes

1. 新增 `qwen` 作为一等公民 engine，完整接入执行、鉴权、管理、模型目录与安装管理；
2. 新增 `server/engines/qwen/**` 引擎包（adapter / auth / config / models / schemas）；
3. 托管安装 `@qwen-code/qwen-code`，并将 `qwen` 纳入默认 bootstrap / upgrade 路径；
4. Qwen 执行链路对齐官方 CLI：顶层 `qwen` 命令、`--output-format stream-json`、`--resume`；
5. 模型目录采用静态 snapshot manifest，provider-aware 暴露 `qwen-oauth` 与 Coding Plan 模型元数据；
6. Qwen 鉴权接入共享 provider-aware 基础设施，支持 `qwen-oauth` 与 `coding-plan-{china,global}`。

## Scope

### In Scope

- `qwen` engine 的 adapter / auth / models / config / install / UI / management 接入；
- `.qwen` workspace 与技能注入；
- Qwen OAuth 与 Coding Plan 的现有鉴权入口；
- 与当前实现一致的 OpenSpec、后端、测试和文档同步。

### Out of Scope

- Qwen live streaming parser；
- `stream_event` / `tool_call` / MCP 细粒度解析；
- 基于浏览器回调的 Qwen OAuth 新协议形态；
- 对 Coding Plan 暴露导入式鉴权 UI。

## Impact

主要改动面：

- `server/engines/qwen/**`
- managed CLI 安装 / bootstrap / upgrade / engine status / management UI
- `docs/api_reference.md`
- qwen 相关 OpenSpec delta specs
