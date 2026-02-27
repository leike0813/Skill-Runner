## Why

当前鉴权会话已经有 `transport` 双链路，但测试阶段仍缺少完整矩阵能力：
1. `codex` 与 `opencode/openai` 还不能在同一 UI 中显式切换 `browser-oauth` 与 `device-auth`。
2. 历史字段 `method` 与“真实鉴权方式”存在语义混叠，导致路由分发、文案和状态展示不稳定。
3. OpenAI browser OAuth 在远端部署场景必须同时支持“本机自动回调”和“手工粘贴 URL/code fallback”。

因此本次 change 将 OpenAI 鉴权升级到测试期 2x2 矩阵（transport × auth_method），并通过新字段消除语义漂移。

## Locked Decisions

1. 测试期目标矩阵为：
   - `transport`: `oauth_proxy | cli_delegate`
   - `auth_method`: `browser-oauth | device-auth`
2. 覆盖范围仅：
   - `codex`
   - `opencode + provider_id=openai`
3. 管理 UI 保持人工选择，不做自动切换策略。
4. `oauth_proxy` 在 OpenAI 链路保持零 CLI（协议代理）；`cli_delegate` 走 CLI 编排。
5. browser OAuth 必须支持：
   - 本机回调自动收口
   - `/input` 粘贴 redirect URL/code 手工兜底
6. callback listener 必须动态启停，不后台常驻。

## What Changes

1. API/类型契约：
   - `EngineAuthSessionStartRequest` 新增 `auth_method?`。
   - `EngineAuthSessionSnapshot` 新增回显字段 `auth_method`。
   - 继续保留历史 `method` 字段（兼容旧请求）。
2. 分发契约：
   - 分发键升级为 `(engine, transport, method, provider_id, auth_method)`。
   - `codex` 与 `opencode/openai` 支持 4 组合。
3. 协议代理契约：
   - `oauth_proxy + browser-oauth`: 现有 PKCE/browser OAuth + callback + input fallback。
   - `oauth_proxy + device-auth`: 新增 OpenAI device-auth 协议轮询链路（零 CLI）。
4. CLI 委托契约：
   - `codex + cli_delegate + device-auth` => `codex login --device-auth`
   - `opencode/openai + cli_delegate + device-auth` => 登录菜单选 `ChatGPT Pro/Plus (headless)`。
5. UI 契约：
   - Codex/OpenCode(OpenAI) 显式展示 2x2 按钮矩阵。
   - 输入提示文案按 `auth_method` 差异化。

## Success Criteria

1. `codex` 与 `opencode/openai` 均可从 UI 触发 4 组合会话。
2. browser OAuth 链路可自动回调，也可通过 `/input` fallback 成功闭环。
3. device-auth 协议代理可返回 `verification_url + user_code`，并在后端轮询成功后自动 `succeeded`。
4. `cli_delegate` 与现有 gemini/iflow/opencode 非 openai provider 链路不回归。
5. 文档、测试与实现保持一致。

## Scope

### In Scope

1. OpenAI 鉴权 2x2 测试矩阵能力。
2. `auth_method` 契约引入及向后兼容。
3. UI 鉴权入口与提示文案重构。
4. OpenAI device-auth 协议代理（codex/opencode 写盘复用）。

### Out of Scope

1. 部署模式自动切换策略（后续 change）。
2. OpenCode 非 openai provider 新增鉴权方式扩展。
3. `auth-status` 判定口径变更。
