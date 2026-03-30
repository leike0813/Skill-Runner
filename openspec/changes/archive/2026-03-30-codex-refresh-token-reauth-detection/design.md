## Context

run `9440bc11-f476-4e3d-a01f-05a3151bdcef` 的 stderr 明确包含以下稳定信号：

- `code: "refresh_token_reused"`
- `Please try signing in again`
- `Please log out and sign in again`
- `Provided authentication token is expired`

但当前 Codex profile 只有 `codex_missing_bearer_401` 一条高置信度规则，因此这次样本只能落入 common fallback，最终在 `.audit/meta.1.json` 中表现为 `auth_required/low`。按照现有 lifecycle 规则，low-confidence auth 只保留审计，不会驱动 `waiting_auth`。

## Goals / Non-Goals

**Goals:**
- 为 Codex refresh token 失效族建立高置信度 engine-specific 检测
- 让此类错误复用现有 `waiting_auth` / method-selection 流程
- 保持 generic fallback 不变，只把明确的 Codex reauth 文案从 low 提升到 high

**Non-Goals:**
- 不修改 Codex 鉴权会话状态机
- 不放宽为所有 Codex 401/Unauthorized 都进入高置信度 auth
- 不新增新的 auth subcategory 或新的 public API

## Decisions

### 1. 规则范围采用“refresh token 失效族”

规则不只匹配单一 `refresh_token_reused`，而是覆盖同一故障族中明确要求重新登录的 Codex 文案，包括：

- `refresh_token_reused`
- `refresh token ... used ... generate a new access token`
- `access token could not be refreshed ... log out and sign in again`
- `authentication token is expired ... sign in again`

这样可以减少 Codex 同一失效族不同表述之间的漏报。

### 2. 规则保持高置信度、subcat 为空

规则命中后沿用现有 engine-specific 高置信度语义：

- `required=true`
- `confidence=high`
- `matched_pattern_id=codex_refresh_token_reauth_required`
- `reason_code=CODEX_REFRESH_TOKEN_REAUTH_REQUIRED`
- `subcategory=null`

本次不额外引入 `oauth_reauth` 或其他新 subcategory，避免扩大契约面。

### 3. 只做检测提升，不改 lifecycle 分支

现有 lifecycle 已经能正确处理 Codex 高置信度 auth：

- nonzero exit 可归因为 `AUTH_REQUIRED`
- interactive run 可进入 `waiting_auth.method_selection`

因此本次只需要让 parser 能稳定产出 high-confidence auth signal，后续逻辑复用现有实现即可。

## Risks / Trade-offs

- [Risk] 如果规则写得过宽，可能把一般性的 Codex 401 错误误判成需要重新登录。  
  -> Mitigation: 规则必须同时包含 refresh token 失效 / sign in again 这类 reauth 语义，不接受孤立的 `401 Unauthorized`

- [Risk] 只覆盖单一字符串会在 Codex 文案微调后再次漏报。  
  -> Mitigation: 使用 refresh token 失效族匹配，而不是单个 literal

- [Risk] 样本只来自单个 run。  
  -> Mitigation: fixture 中保留 stdout+stderr+pty 的最小必要原始文本，后续可继续扩展同族样本而不改规则框架
