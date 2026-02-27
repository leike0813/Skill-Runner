# OAuth 代理可行性证据矩阵（官方源）

## 1. 证据准入规则
- 仅采信两类来源：
  - 官方源码仓库（本地 `references/*` 克隆副本，对应上游官方仓库）。
  - 官方文档域名（例如 `openai.com`、`help.openai.com`、`opencode.ai`、官方 GitHub 仓库页面）。
- 每条结论必须可定位到具体文件与行号（本地源码优先）。
- 外网信息仅作为交叉验证，不替代源码事实。
- 置信等级定义：
  - `High`：核心行为由源码直接定义。
  - `Medium`：官方文档/官方 issue 说明，或源码存在推断链。
  - `Low`：仅补充背景，不用于关键决策。

---

## 2. Codex（`references/codex`）

### COD-01
- 结论点：Codex browser OAuth 默认使用本地回调 `http://localhost:{port}/auth/callback`。
- 证据来源：本地源码（官方仓库克隆）。
- 证据定位：`references/codex/codex-rs/login/src/server.rs:31-33,116-124`
- 关键摘录：定义 `DEFAULT_ISSUER=https://auth.openai.com`、`DEFAULT_PORT=1455`，并拼接 `redirect_uri=http://localhost:{actual_port}/auth/callback`，随后构建 authorize URL。
- 推导含义：若要做“真 OAuth 代理”，必须处理本地回调与远端部署可达性问题。
- 置信等级：High
- 冲突/歧义：无。

### COD-02
- 结论点：Codex browser OAuth 使用 PKCE + state，并校验回调 state。
- 证据来源：本地源码（官方仓库克隆）。
- 证据定位：`references/codex/codex-rs/login/src/server.rs:101-103,242-247,256-257`
- 关键摘录：启动时生成 PKCE 与 state；回调时若 `state` 不匹配返回 400；之后执行 code->token exchange。
- 推导含义：后端代理链路必须实现一次性 state 绑定与校验，且不能省略 PKCE。
- 置信等级：High
- 冲突/歧义：无。

### COD-03
- 结论点：Codex authorize URL 参数含 `originator` 和 `codex_cli_simplified_flow=true`。
- 证据来源：本地源码（官方仓库克隆）。
- 证据定位：`references/codex/codex-rs/login/src/server.rs`（`build_authorize_url` 逻辑，包含 `originator` 与 simplified flow 参数）
- 关键摘录：authorize URL 包含 `scope=openid profile email offline_access`，并携带 Codex 约定参数。
- 推导含义：协议代理如果缺参，可能触发服务端 `unknown_error` 或行为差异。
- 置信等级：High
- 冲突/歧义：`originator` 最终允许值范围需以上游行为为准（见 COD-04）。

### COD-04
- 结论点：Codex 默认 `originator` 为 `codex_cli_rs`，可由环境变量覆盖。
- 证据来源：本地源码（官方仓库克隆）。
- 证据定位：`references/codex/codex-rs/core/src/default_client.rs:25-27,41-46,77-96`
- 关键摘录：`DEFAULT_ORIGINATOR=codex_cli_rs`，支持 `CODEX_INTERNAL_ORIGINATOR_OVERRIDE`。
- 推导含义：协议代理需明确 originator 策略并与上游约定对齐。
- 置信等级：High
- 冲突/歧义：无公开文档列出完整 originator 合法值集合。

### COD-05
- 结论点：Codex 同时支持 device-auth，验证 URL 为 `/codex/device`。
- 证据来源：本地源码（官方仓库克隆）。
- 证据定位：`references/codex/codex-rs/login/src/device_code_auth.rs:63-69,107,163-168,227-229`
- 关键摘录：请求 usercode/token 端点；展示 `https://auth.openai.com/codex/device` 与 user code。
- 推导含义：`cli_delegate` 可继续承载 device flow；`oauth_proxy` 不应混入 CLI 分支。
- 置信等级：High
- 冲突/歧义：无。

### COD-EXT-01（外网交叉验证）
- 结论点：官方帮助文档确认 Codex CLI 有 ChatGPT 登录流程并本地存储凭据。
- 证据来源：官方帮助中心。
- 证据定位：`https://help.openai.com/en/articles/11381614-codex-cli-and-sign-in-withgpt`
- 关键摘录：文档说明运行登录命令后完成 Sign in with ChatGPT，凭据本地保存。
- 推导含义：与源码“本地 auth 存储 + OAuth/Device 登录”一致。
- 置信等级：Medium
- 冲突/歧义：文档未给出协议参数细节，不能替代源码。

---

## 3. OpenCode（`references/opencode`）

### OPC-01
- 结论点：OpenCode 后端已公开 provider OAuth `authorize/callback` 接口。
- 证据来源：本地源码（官方仓库克隆）。
- 证据定位：`references/opencode/packages/opencode/src/server/routes/provider.ts:84-122,124-163`
- 关键摘录：`POST /:providerID/oauth/authorize` 与 `POST /:providerID/oauth/callback`。
- 推导含义：OpenCode 生态天然支持“协议级 provider OAuth”，不必依赖 TUI 文本编排。
- 置信等级：High
- 冲突/歧义：无。

### OPC-02
- 结论点：OpenCode `ProviderAuth` 支持 OAuth `auto` 与 `code` 两种方法。
- 证据来源：本地源码（官方仓库克隆）。
- 证据定位：`references/opencode/packages/opencode/src/provider/auth.ts:43-48,54-72,74-117`
- 关键摘录：`Authorization.method` 为 `auto|code`；`callback` 分支按 method 调用。
- 推导含义：我们的统一 `/input` 语义可直接映射至 OpenCode 的 `code` 回填模式。
- 置信等级：High
- 冲突/歧义：无。

### OPC-03
- 结论点：OpenCode OAuth/API 凭据统一写入 `auth.json`，结构区分 `oauth/api/wellknown`。
- 证据来源：本地源码（官方仓库克隆）。
- 证据定位：`references/opencode/packages/opencode/src/auth/index.ts:9-17,20-33,35-39,58-67`
- 关键摘录：`Auth.Info` 判别联合；文件路径 `Global.Path.data/auth.json`；`set/remove` 持久化。
- 推导含义：前端 OAuth 代理成功后可直接写盘到 OpenCode 兼容结构。
- 置信等级：High
- 冲突/歧义：无。

### OPC-04
- 结论点：OpenCode 内置 openai(codex) provider 插件已完整实现 browser OAuth 参数与 callback 服务。
- 证据来源：本地源码（官方仓库克隆）。
- 证据定位：`references/opencode/packages/opencode/src/plugin/codex.ts:10-14,88-102,111-127,245-314`
- 关键摘录：`CLIENT_ID`、`ISSUER`、`OAUTH_PORT=1455`、`originator=opencode`、`/oauth/token`、本地 callback server。
- 推导含义：`opencode+openai` 真协议代理可直接复用同等参数模型，不应走 CLI 解析。
- 置信等级：High
- 冲突/歧义：无。

### OPC-05
- 结论点：OpenCode openai provider 的 `ChatGPT Pro/Plus (headless)` 是完整 device-auth 协议实现（非 TUI 文本拼接）。
- 证据来源：本地源码（官方仓库克隆）。
- 证据定位：`references/opencode/packages/opencode/src/plugin/codex.ts:529-606`
- 关键摘录：先请求 `/api/accounts/deviceauth/usercode`，展示 `${ISSUER}/codex/device` 与 `user_code`；轮询 `/api/accounts/deviceauth/token`；成功后用 `authorization_code + code_verifier` 调 `/oauth/token`，`redirect_uri=${ISSUER}/deviceauth/callback`。
- 推导含义：`oauth_proxy + device-auth` 在协议层可直接落地，且能与 browser OAuth 共用 token 持久化结构。
- 置信等级：High
- 冲突/歧义：无。

### OPC-06
- 结论点：OpenCode 在 device-auth 请求里显式设置 `User-Agent`，并将 403/404 视为“继续轮询”，其他状态视为失败。
- 证据来源：本地源码（官方仓库克隆）。
- 证据定位：`references/opencode/packages/opencode/src/plugin/codex.ts:534-537,558-561,601-606`
- 关键摘录：`headers.User-Agent = opencode/<version>`；轮询分支中仅 403/404 继续，其他状态直接失败。
- 推导含义：后端协议代理需保持同等状态机语义（403/404 pending，其它 hard fail），并注意请求特征差异可能影响上游网关行为。
- 置信等级：High
- 冲突/歧义：请求特征对上游风控命中的影响在源码层无法直接证明，需要运行态验证。

### OPC-EXT-01（外网交叉验证）
- 结论点：OpenCode 官方文档确认 provider 凭据存储在 `~/.local/share/opencode/auth.json`。
- 证据来源：官方文档站点。
- 证据定位：`https://opencode.ai/docs/providers/`
- 关键摘录：`Credentials ... stored in ~/.local/share/opencode/auth.json`。
- 推导含义：与 OPC-03 的本地源码结论一致。
- 置信等级：High
- 冲突/歧义：无。

---

## 4. OpenCode AntiGravity 插件（`references/opencode-antigravity-auth`）

### ANT-01
- 结论点：Google AntiGravity OAuth 使用标准 PKCE + state，authorize endpoint 为 Google OAuth2。
- 证据来源：本地源码（官方仓库克隆）。
- 证据定位：`references/opencode-antigravity-auth/src/antigravity/oauth.ts:92-107`
- 关键摘录：`https://accounts.google.com/o/oauth2/v2/auth` + `code_challenge` + `state` + `prompt=consent`。
- 推导含义：理论上可做协议代理；输入通常是 redirect URL 或 code。
- 置信等级：High
- 冲突/歧义：无。

### ANT-02
- 结论点：token exchange 在 `https://oauth2.googleapis.com/token`，并调用 userinfo。
- 证据来源：本地源码（官方仓库克隆）。
- 证据定位：`references/opencode-antigravity-auth/src/antigravity/oauth.ts:209-225,234-246,258-267`
- 关键摘录：授权码换 token，读取 email/project 信息并构造持久化字段。
- 推导含义：后端协议代理可在不启动 CLI 的前提下完成 token 交换与账号元数据获取。
- 置信等级：High
- 冲突/歧义：无。

### ANT-03
- 结论点：插件约定 redirect URI 为本地 `http://localhost:51121/oauth-callback`。
- 证据来源：本地源码（官方仓库克隆）。
- 证据定位：`references/opencode-antigravity-auth/src/constants.ts:25`
- 关键摘录：`ANTIGRAVITY_REDIRECT_URI = "http://localhost:51121/oauth-callback"`。
- 推导含义：若改为平台回调地址，需验证 Google OAuth 客户端的 redirect allowlist。
- 置信等级：High
- 冲突/歧义：是否允许自定义 redirect 由上游 OAuth 客户端配置决定。

### ANT-04
- 结论点：插件代码显式处理容器/WSL/远程环境绑定策略，但核心仍依赖 localhost callback 可达性。
- 证据来源：本地源码（官方仓库克隆）。
- 证据定位：`references/opencode-antigravity-auth/src/plugin/server.ts:106-134,137-143`
- 关键摘录：按环境选择 bind 地址（`127.0.0.1` 或 `0.0.0.0`），并启动本地 listener。
- 推导含义：纯平台代理回调可降低环境可达性复杂度。
- 置信等级：High
- 冲突/歧义：无。

### ANT-EXT-01（外网交叉验证）
- 结论点：官方插件文档明确账号文件位置与重置方式。
- 证据来源：官方 GitHub README/Troubleshooting。
- 证据定位：`https://github.com/NoeFabris/opencode-antigravity-auth`、`.../docs/TROUBLESHOOTING.md`
- 关键摘录：账号文件 `~/.config/opencode/antigravity-accounts.json`，通过 `opencode auth login` 重新登录。
- 推导含义：与我们现有“账号文件治理”策略直接相关。
- 置信等级：High
- 冲突/歧义：无。

---

## 5. Gemini CLI（`references/gemini-cli`）

### GEM-01
- 结论点：Gemini CLI OAuth（Web）为真实协议流，含本地回调 server + state 校验。
- 证据来源：本地源码（官方仓库克隆）。
- 证据定位：`references/gemini-cli/packages/core/src/code_assist/oauth2.ts:459-475,476-516,502-510,529-540`
- 关键摘录：构造 `redirectUri=http://localhost:{port}/oauth2callback`，校验 `state`，收到 code 后换 token。
- 推导含义：Gemini 不是只能 TUI 文本编排；协议代理在技术上可行。
- 置信等级：High
- 冲突/歧义：上游客户端 ID/secret 与政策变更风险需持续跟踪。

### GEM-02
- 结论点：Gemini CLI 同时支持用户手工 code 输入的 OAuth 兜底路径。
- 证据来源：本地源码（官方仓库克隆）。
- 证据定位：`references/gemini-cli/packages/core/src/code_assist/oauth2.ts:385-415,423-430`
- 关键摘录：打印授权 URL，提示 `Enter the authorization code`，再调用 `getToken`。
- 推导含义：统一 `/input(kind=code|text)` 设计有源码依据。
- 置信等级：High
- 冲突/歧义：无。

### GEM-03
- 结论点：认证菜单与 `/auth` 命令行为在 CLI UI 代码中明确。
- 证据来源：本地源码（官方仓库克隆）。
- 证据定位：`references/gemini-cli/packages/cli/src/ui/auth/AuthDialog.tsx:46-79,96-110,221-241`；`.../authCommand.ts:16-25,48-56`
- 关键摘录：菜单含 Login with Google / API Key / Vertex；`/auth` 默认打开登录对话框。
- 推导含义：CLI 委托链路与协议链路可并行，且状态锚点可持续维护。
- 置信等级：High
- 冲突/歧义：无。

### GEM-EXT-01（外网交叉验证）
- 结论点：官方仓库 README 和认证文档确认 Login with Google 是推荐路径。
- 证据来源：官方 GitHub 仓库。
- 证据定位：`https://github.com/google-gemini/gemini-cli`、`.../docs/get-started/authentication.md`
- 关键摘录：`gemini` 启动后选择 Login with Google。
- 推导含义：与 GEM-01/02 的源码实现一致。
- 置信等级：High
- 冲突/歧义：无。

---

## 6. iFlow2API（`references/iflow2api`）

### IFL-01
- 结论点：iFlow2API 明确实现 OAuth 协议参数与 token 接口，不依赖 TUI 解析。
- 证据来源：本地源码（项目源码）。
- 证据定位：`references/iflow2api/iflow2api/oauth.py:15-20,47-49,70-87,195-220`
- 关键摘录：`AUTH_URL=https://iflow.cn/oauth`、`TOKEN_URL=https://iflow.cn/oauth/token`，`get_auth_url` 生成 state。
- 推导含义：iFlow 的“真 OAuth 代理”可直接复用此协议实现思路。
- 置信等级：High
- 冲突/歧义：无。

### IFL-02
- 结论点：iFlow2API 管理端提供 OAuth URL 生成与 callback 接收（GET+POST）链路。
- 证据来源：本地源码（项目源码）。
- 证据定位：`references/iflow2api/iflow2api/admin/routes.py:414-432,435-507,510-558`
- 关键摘录：`/admin/oauth/url` 返回 `auth_url`；callback 回传 code 并换 token，最终写入配置。
- 推导含义：证明 iFlow 可通过纯 Web/API 路由完成 OAuth 闭环。
- 置信等级：High
- 冲突/歧义：无。

### IFL-03
- 结论点：独立登录模块实现了 state 校验与本地 callback server。
- 证据来源：本地源码（项目源码）。
- 证据定位：`references/iflow2api/iflow2api/oauth_login.py:57-75,89-99`；`.../web_server.py:265-299`
- 关键摘录：生成 `csrf_state`，回调后对比 `returned_state`，不通过则失败。
- 推导含义：iFlow 侧已有可复用的 CSRF 防护范式。
- 置信等级：High
- 冲突/歧义：无。

### IFL-EXT-01（外网交叉验证）
- 结论点：未检索到同等权威的官方站点文档（与源码同级别）可补充协议细节。
- 证据来源：外网检索结果。
- 证据定位：本轮搜索范围内未命中高质量官方文档。
- 关键摘录：N/A
- 推导含义：iFlow 结论应以本地源码为主证据。
- 置信等级：Medium
- 冲突/歧义：外网证据不足是事实，不影响源码证据本身。

---

## 7. 跨项目冲突与一致性对比

| 维度 | Codex | OpenCode(OpenAI) | Gemini CLI | iFlow2API | AntiGravity 插件 |
|---|---|---|---|---|---|
| Authorize 方式 | OAuth browser + device | provider oauth（auto/code，openai 含 device headless） | OAuth web + user code | OAuth web API | OAuth web |
| Redirect 约束 | localhost 回调（1455 默认） | localhost 回调（1455） | localhost 回调（动态端口） | localhost 回调（11451/管理端端口） | localhost 回调（51121） |
| PKCE | 是 | 是 | 是（web/user-code） | 未见 PKCE（基于其实现） | 是 |
| state 校验 | 是 | 插件/方法内部处理 | 是 | 是 | 是 |
| Token Endpoint | `auth.openai.com/oauth/token` | `auth.openai.com/oauth/token` | Google OAuth token | `iflow.cn/oauth/token` | `oauth2.googleapis.com/token` |
| 凭据落盘 | `~/.codex/auth.json` 语义 | `~/.local/share/opencode/auth.json` | Gemini 凭据缓存文件 | iFlow settings | `antigravity-accounts.json` + opencode auth |

结论：
- OpenAI 链路（Codex + OpenCode openai）参数同源度高，适合先做“零 CLI 协议代理”。
- Gemini/iFlow 技术上可做协议代理，但与现有 CLI 委托并行更稳妥。
- AntiGravity OAuth 具备协议能力，但账号文件/projectId/回调约束使流程复杂度最高。

---

## 8. 证据缺口清单（需后续 PoC/联调）
- GAP-01：OpenAI OAuth 服务端对 `originator`、`redirect_uri` allowlist 的运行态约束未见公开规格文档（需联调验证）。
- GAP-02：OpenCode AntiGravity 在“多账号管理菜单”下的最小稳定自动化策略缺少公开协议文档（目前以源码与行为观测为主）。
- GAP-03：iFlow 外网官方文档证据不足，需以源码与实测作为主依据。
- GAP-04：不同部署形态（本机/容器/远程）下浏览器回调可达性仍需运行态测试矩阵验证。
