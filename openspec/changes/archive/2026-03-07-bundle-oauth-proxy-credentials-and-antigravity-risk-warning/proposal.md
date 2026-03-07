## Why

`gemini` 与 `opencode(provider=google/antigravity)` 的 `oauth_proxy` 依赖 OAuth client credentials。  
当前凭据只放在 `.env.engine_auth.local`（不可提交），导致其他用户克隆仓库后默认不可用。  

同时，`opencode+antigravity` 属于高风险第三方登录路径，当前在管理 UI、会话内鉴权提示、README 都缺少明确警示。

## What Changes

- 引入仓库内可提交的 engine-specific 共享凭据文件，并在服务启动时自动加载。  
- 移除对 `.env.engine_auth.local` 的启动加载依赖。  
- 在 engine auth strategy 中声明高风险方法集合（`high_risk_methods`）。  
- 管理 UI 鉴权方法按钮对高风险方法显示短标签 `(<High risk!>)`。  
- 会话内鉴权提示（method selection / challenge prompt）增加高风险提示。  
- 在 README 鉴权章节增加醒目风险警示。

## Scope

- Affected code:
  - `server/main.py`
  - `server/engines/gemini/auth/protocol/shared_oauth_credentials.env` (new)
  - `server/engines/opencode/auth/protocol/shared_google_antigravity_oauth_credentials.env` (new)
  - `.github/secret_scanning.yml` (new)
  - `server/contracts/schemas/engine_auth_strategy.schema.json`
  - `server/engines/opencode/config/auth_strategy.yaml`
  - `server/services/engine_management/engine_auth_strategy_service.py`
  - `server/services/orchestration/run_auth_orchestration_service.py`
  - `server/routers/ui.py`
  - `server/assets/templates/ui/engines.html`
  - `server/locales/{en,zh,ja,fr}.json`
  - `README.md`
- API impact: None.
- Runtime protocol impact: None.
