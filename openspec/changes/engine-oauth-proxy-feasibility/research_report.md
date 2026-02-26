# Engine OAuth 代理可行性报告

## 1. 范围与方法

本报告评估 Skill Runner 能否以更低的运维复杂度向前端用户暴露引擎认证流程，以及何种实现策略在技术上是安全的。

方法：
- CLI 能力探测（`--help`、子命令）
- 检查 `references/` 下的源代码与文档
- 检查当前代码库中的运行时映射（`server/services/runtime_profile.py`、`server/services/agent_cli_manager.py`）

## 2. 按引擎汇总的证据

| Engine | 可脚本化登录入口 | 回调 / 挑战形态 | 初步可行性 |
|---|---|---|---|
| codex | `codex login --device-auth`、`codex login --with-api-key` | 设备认证 URL + 用户代码；chatgpt 登录路径在源码中包含本地回调服务器实现 | 有条件通过 |
| gemini | CLI 帮助中未暴露专门的 `login` 子命令；认证主要嵌入于应用启动和交互流程中 | 源码在 `oauth2.ts` 中包含浏览器与用户代码流程，但没有稳定的独立 CLI 认证 API 合同 | 有条件 / 高风险 |
| iflow | CLI 帮助中无专门的非交互式认证命令；文档指示交互式 `/auth` 与网页登录 | 强交互导向路径；可用源码中缺乏稳定的非交互式代理合同 | 第一阶段不建议 |
| opencode | `opencode auth login [url]`；SDK OpenAPI 暴露提供商 OAuth authorize/callback 端点 | 在 `references/opencode/packages/sdk/openapi.json` 中有清晰的提供商 OAuth API 表面 | 通过（第一阶段最佳候选） |

## 3. 凭证路径与运行时映射证据

当前运行时隔离与凭证导入已标准化：
- 运行时环境中的 XDG 映射：
  - `XDG_CONFIG_HOME=<agent_home>/.config`
  - `XDG_DATA_HOME=<agent_home>/.local/share`
  - `XDG_STATE_HOME=<agent_home>/.local/state`
  - `XDG_CACHE_HOME=<agent_home>/.cache`
- 来源：`server/services/runtime_profile.py`

凭证导入映射：
- codex: `auth.json -> .codex/auth.json`
- gemini: `google_accounts.json -> .gemini/google_accounts.json`、`oauth_creds.json -> .gemini/oauth_creds.json`
- iflow: `iflow_accounts.json -> .iflow/iflow_accounts.json`、`oauth_creds.json -> .iflow/oauth_creds.json`
- opencode: `auth.json -> .local/share/opencode/auth.json`、`antigravity-accounts.json -> .config/opencode/antigravity-accounts.json`
- 来源：`server/services/agent_cli_manager.py`（`CREDENTIAL_IMPORT_RULES`）

## 4. Headless / 远程约束

- codex:
  - `--device-auth` 可通过展示 URL + 代码避免本地浏览器依赖。
  - chatgpt 浏览器登录路径在源码中包含本地回调服务器模式；不太适合作为通用后端抽象。
- gemini:
  - 源码（`references/gemini-cli/packages/core/src/code_assist/oauth2.ts`）展示两种模式：
    - 浏览器流程（`authWithWeb`）
    - 抑制浏览器的流程（`authWithUserCode`），需要手动粘贴代码
  - 表明技术上可行的流程，但与应用初始化路径紧密耦合。
- iflow:
  - 文档指示交互式 `/auth` 与网页登录，但在 CLI 帮助中未找到稳定的 headless 命令合同。
- opencode:
  - SDK OpenAPI 中的提供商 OAuth 端点表明可形式化代理式的后端工作流。

## 5. 方案对比

### 方案 A：CLI 委托编排

后端启动按引擎的 CLI 认证命令/进程，并将挑战 + 状态转发给前端。

优点：
- 对具有可脚本化认证的引擎（codex/opencode）落地最快。
- 复用现有 CLI 凭证持久化路径。

缺点：
- 对 CLI UX / 日志输出变化脆弱。
- 对 gemini/iflow 等认证强交互的引擎难以统一。

### 方案 B：原生 OAuth 代理

后端直接实现提供商 authorize/callback/token 交换，并写入规范化认证产物。

优点：
- 前端 UX 干净，后端合同确定。
- 对 CLI 终端行为依赖较小。

缺点：
- 安全与维护成本最高。
- 需要提供商特定协议处理与长期兼容性投入。

### 方案 C：分层混合（推荐）

- 层级 A：上游 API 明确且稳定时，使用原生代理。
- 层级 B：可用非交互式或挑战模式时，使用 CLI 委托编排。
- 层级 C：回退到现有 TUI / 凭证导入。

优点：
- 快速交付增量价值。
- 按能力层级控制实现风险。

缺点：
- 早期阶段跨引擎行为有意保持不统一。

## 6. 推荐的通过 / 有条件 / 不通过

- opencode: **通过**（层级 A 优先候选）
  - 原因：SDK OpenAPI 中存在明确的提供商 OAuth API 表面。
- codex: **有条件通过**（优先层级 B，后续评估层级 A）
  - 原因：设备认证 CLI 路径强；完整代理对等性取决于上游认证内部实现。
- gemini: **有条件**（先研究再实现）
  - 原因：源码显示 OAuth 内部实现，但操作入口作为后端合同稳定性较低。
- iflow: **第一阶段不通过**
  - 原因：可用证据倾向于交互路径；缺乏稳定的独立代理合同。

## 7. 建议的实现变更范围

创建后续实现变更（示例 id）：
- `engine-oauth-ui-broker-phase1`

建议的第一阶段范围：
1. 添加后端认证流程管理器抽象与会话状态机。
2. 实现 opencode OAuth 后端流程（优先）。
3. 实现 codex 委托设备认证流程。
4. 将 gemini/iflow 保留在明确回退 UX（TUI 启动 + 导入指引）上。
5. 添加审计安全日志与硬安全控制（state/nonce、TTL、回调检查、密钥脱敏）。

第一阶段之外：
- 统一的 `/v1` 公共认证 API。
- 对全部四个引擎的完整原生代理对等性。
- 跨重启认证会话恢复。

## 8. 成功标准与退出条件

第一阶段成功：
- 前端无需使用终端菜单操作即可完成至少一个层级 A/B 引擎的认证。
- 现有认证路径保持可用与功能正常。
- 现有 `auth-status` 可观测语义无回归。

停止上线的退出条件：
- 上游 CLI / API 合同不稳定导致认证反复失败，且无法通过适配器防护措施缓解。

## 9. 验证记录

- 命令：`openspec validate engine-oauth-proxy-feasibility --type change`
- 预期：valid
- 状态：在实现阶段执行，任务完成后应保持绿色。
