# OAuth 代理方案论证（基于证据）

## 1. 问题定义
当前鉴权主路径依赖 `cli_delegate`（PTY/TUI 编排），可用但存在结构性问题：
- 非实时：输出解析与状态迁移依赖终端渲染时序。
- 脆弱：上游 TUI 文案/布局变动会导致编排失效。
- 运维复杂：远程部署下 localhost 回调、终端环境与重连行为耦合。

目标是引入“真 OAuth 代理”路径（`oauth_proxy`），并与现有 `cli_delegate` 并行，不回归已稳定链路。

证据主链见 `oauth_proxy_evidence.md`，本文结论均可回链至证据 ID。

---

## 2. 设计目标与非目标

## 2.1 目标
- 为可行链路提供“零 CLI 子进程”的 OAuth 代理实现。
- 保留 `cli_delegate` 作为并行路径，支持渐进迁移与回退。
- 统一会话接口语义（`start/status/input/cancel`），按 transport 分发。
- 保证安全基线：PKCE、state、TTL、一次性消费、防重放。

## 2.2 非目标
- 本阶段不追求一次性覆盖所有 provider。
- 不要求替换现有 auth-status 采集逻辑。
- 不在本阶段处理全部容器/远程网络拓扑细节（通过回调基址配置与手工兜底先落地）。

---

## 3. 方案集对比

## A. 全量协议代理（所有引擎一次到位）
- 优点：最终形态统一，彻底降低 PTY 依赖。
- 缺点：风险过高，尤其是 AntiGravity 多级账户流与上游策略不稳定。
- 结论：不推荐首发。

## B. 双通道并行（`oauth_proxy` + `cli_delegate`）
- 优点：可控迁移；复杂链路保留回退；不阻断现网能力。
- 缺点：短期内存在双实现维护成本。
- 结论：推荐作为总策略。

## C. 分阶段迁移（先 OpenAI 零 CLI，再扩展）
- 优点：OpenAI 两链路同源参数高，可快速验证“真代理”闭环。
- 缺点：短期内功能体验分层。
- 结论：推荐作为 B 的实施顺序。

最终选择：`B + C`（并行双通道 + 分阶段迁移）。

---

## 4. 逐引擎论证与最可能路径

## 4.1 Codex
- 证据：COD-01/02/03/04/05。
- 结论：
  - 可实现 `oauth_proxy`（browser OAuth，零 CLI）。
  - 必须严格复现 authorize 参数与 state/PKCE 校验。
  - `waiting_orchestrator` 不应出现在该链路。
- 风险：
  - `originator`/`redirect` 约束可能存在服务端隐式校验（GAP-01）。
- 推荐：
  - Phase 1 即纳入 `oauth_proxy` 主链路；
  - `device-auth` 可作为并行选项保留（协议代理与 CLI 委托均可实现）。

## 4.2 OpenCode（provider=openai）
- 证据：OPC-01/02/03/04/05/06。
- 结论：
  - 技术可行性最高；本身已有 provider oauth 抽象。
  - 应做“真代理”，禁止借道 `OpencodeAuthCliFlow`（适用于 browser-oauth 与 device-auth）。
- 风险：
  - 需与 OpenCode auth.json 结构兼容（已可控）。
  - `device-auth` 协议请求可能受上游网关策略影响（见 OPC-06 的“其他状态即失败”语义）。
- 推荐：
  - 与 Codex 同批次进入 Phase 1。

## 4.3 Gemini CLI
- 证据：GEM-01/02/03。
- 结论：
  - 存在可实现的协议链路（web callback + user code）。
  - 但当前系统已构建稳定 CLI 委托，贸然替换收益有限。
- 风险：
  - 上游认证策略与客户端参数演进快，维护成本较高。
- 推荐：
  - 维持 `cli_delegate` 为默认；
  - 后续在独立 change 做“协议代理 PoC”，再决定切换。

## 4.4 iFlow
- 证据：IFL-01/02/03。
- 结论：
  - 协议代理可行且实现路径清晰（已有 web 管理端范式）。
- 风险：
  - 外网权威文档不足（IFL-EXT-01），主要依赖源码与实测。
- 推荐：
  - 先保留 `cli_delegate`；
  - 待 OpenAI 代理稳定后可作为下一优先级推进协议代理。

## 4.5 OpenCode Google（AntiGravity 插件）
- 证据：ANT-01/02/03/04。
- 结论：
  - 协议层可做，但流程复杂度与状态治理成本最高。
- 风险：
  - 回调 URI / projectId / 多账号文件治理风险耦合。
  - 账号清理时机若前置，会有“未完成授权即丢失原账号”风险。
- 推荐：
  - Phase 1 不纳入真代理主路径；
  - 继续 `cli_delegate`，并将清理动作后置到“用户提交输入后、写入 PTY 前”。

---

## 5. OpenCode Provider 差异策略（Phase 1 提案）

## 5.1 API Key 类（DeepSeek/iFlowCN/MiniMax/Moonshot/OpenCode/OpenRouter/Z.ai）
- 方案：`/input(kind=api_key)` 直写 auth store。
- 约束：敏感值不入日志；原子写盘；provider 覆盖更新不影响其他项。

## 5.2 OAuth 类
- `openai`：纳入 `oauth_proxy`（零 CLI）。
- `google(antigravity)`：保留 `cli_delegate`（复杂菜单 + 账号治理）。

## 5.3 Device-auth 专项论证（OpenAI）
- 已证实事实：
  - Codex 源码提供完整 device-auth 链路（COD-05）。
  - OpenCode openai 插件提供完整 device-auth 链路，且明确轮询状态机（OPC-05/06）。
- 推断：
  - 对 `codex` / `opencode(openai)`，`oauth_proxy + device-auth` 在协议上是可行路线，不依赖 PTY。
- 风险边界：
  - 上游网关/风控导致的非 403/404 错误（例如 429/5xx）属于协议失败，应直接失败并让用户重试或切换 transport，而不是隐式切换链路。
- 实施建议：
  - device-auth 保持与源码一致的状态机：403/404 继续轮询，其他状态失败。
  - 管理 UI 同时暴露 browser/device + oauth_proxy/cli_delegate，便于按部署环境选路。

---

## 6. 公共接口语义提案（仅论证，不生效）

- `start` 请求：
  - `transport?: "oauth_proxy" | "cli_delegate"`，默认 `oauth_proxy`。
- `snapshot` 响应：
  - `transport`
  - `execution_mode: "protocol_proxy" | "cli_delegate"`
  - `manual_fallback_used`
  - `oauth_callback_received`
- 状态分层：
  - `waiting_orchestrator`：仅 CLI 委托自动输入阶段。
  - `waiting_user`：OAuth 代理已提供授权 URL，等待用户外部操作。
  - `code_submitted_waiting_result`：仅在输入兜底后出现。
- 回调端点：
  - 免 Basic Auth；
  - 必须 `state + session + TTL + 一次性消费`。

---

## 7. 风险矩阵

| 风险 | 影响 | 触发条件 | 缓解策略 |
|---|---|---|---|
| OAuth 参数漂移 | 授权失败 | 上游修改参数/校验 | 参数集中配置 + 联调回归用例 |
| 回调不可达 | 会话卡死 | 容器/远程网络 | callback base URL 配置 + `/input` 手工兜底 |
| state 重放 | 安全风险 | 重放旧回调 | 一次性 state + TTL + consumed 标记 |
| 多通道认知混乱 | UX 降级 | 用户不理解 transport | UI 显示链路类型 + 状态解释 |
| AntiGravity 账号污染 | 错误账号被选中 | 多账号残留 | 清理后置 + 审计记录 + 可取消 |

---

## 8. 推荐实施路线（Phase 0/1/2）

## Phase 0（当前）
- 仅文档化与证据固化。
- 产出：本文件 + `oauth_proxy_evidence.md`。

## Phase 1（优先）
- 实现“OpenAI 零 CLI 代理”：
  - `codex + oauth_proxy`
  - `opencode(provider=openai) + oauth_proxy`
- 严格禁止上述链路调用 CLI/PTY。
- 运行形态补充：
  - 同机部署：通过本地 `localhost:1455/auth/callback` 按需监听（会话期间启动）实现自动回调收口。
  - 异机部署：保留 `/input` 手工粘贴回调 URL 或授权码兜底，不阻塞流程。
- 验收关键点：
  - start 后直接 `waiting_user`；
  - 返回授权 URL 为上游授权域名，不是 localhost 根 URL；
  - callback 成功后正确写盘 auth。

## Phase 2（扩展）
- 继续保留并稳定 `cli_delegate`：
  - gemini
  - iflow
  - opencode/google-antigravity
- 以独立 change 评估 gemini/iflow 协议代理化。

---

## 9. Go / No-Go 条件

## Go（可进入实现）
- OpenAI 两链路的协议参数集已由 High 证据闭环覆盖。
- 回调安全约束（state/TTL/一次性）设计无缺口。
- 与现有 `cli_delegate` 的冲突矩阵清晰（transport 分发无歧义）。

## No-Go（需继续补证）
- 关键参数依赖仅有 Medium/Low 证据。
- 回调安全模型不完整（未覆盖重放/过期/并发）。
- 无法提供手工输入兜底路径。

---

## 10. 最小验证计划（文档级）
- 每个推荐结论至少对应 1 条 High 证据。
- 每个被拒方案都给出可审计拒绝理由。
- 每个阶段都有明确验收条件与回退策略。
- 明确区分：
  - 已证实事实（可定位）
  - 推断（基于证据）
  - 待验证假设（GAP）
