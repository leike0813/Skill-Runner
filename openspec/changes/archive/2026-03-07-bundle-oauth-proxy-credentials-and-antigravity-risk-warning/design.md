## Context

需要同时解决两个问题：

1. OAuth proxy 凭据不可分发导致功能默认不可用。  
2. `opencode+antigravity` 高风险链路缺少显式风险提示。

本次保持业务协议与 API 不变，只调整配置来源和 UI/交互提示文案。

## Decisions

### 1) Shared credentials as startup default

- 新增两个 engine-specific 凭据文件作为仓库内默认凭据源：  
  - `server/engines/gemini/auth/protocol/shared_oauth_credentials.env`
  - `server/engines/opencode/auth/protocol/shared_google_antigravity_oauth_credentials.env`
- `server/main.py` 启动时加载这两个文件并写入 `os.environ`（`setdefault` 语义，保持进程环境变量优先）。  
- 不再读取 `.env.engine_auth.local`。

### 1.1) Secret scanning scoped exemption

- 新增 `.github/secret_scanning.yml`，仅对白名单路径做 `paths-ignore`，避免全仓关闭 push protection。

### 2) Risk metadata from strategy SSOT

- 在 `engine_auth_strategy` schema 的 transport policy 增加可选字段 `high_risk_methods`。  
- `opencode/providers/google/transports/{oauth_proxy,cli_delegate}` 声明高风险方法。  
- 风险判定统一走 `EngineAuthStrategyService`，避免多处硬编码。

### 3) UI and in-conversation warning behavior

- 管理 UI 引擎鉴权菜单：高风险方法标签追加 `(<High risk!>)`。  
- 会话内鉴权：
  - 方法选择按钮标签追加 `(<High risk!>)`
  - challenge prompt 追加高风险说明
- README 鉴权章节增加醒目风险说明。

## Non-Goals

- 不改 auth state machine / FCMP / RASP / SSE 协议。  
- 不新增 auth route。  
- 不改变会话内 transport 选择模型。

## Risks / Trade-offs

- 仓库内分发 OAuth client credentials 会增加滥用与泄漏风险。  
- 通过 UI 与 README 的显式高危提示降低误用风险，但不消除外部平台封号风险。
