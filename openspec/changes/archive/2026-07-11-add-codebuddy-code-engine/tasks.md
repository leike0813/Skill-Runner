## 1. 规格与机器合同

- [x] CB-1.1 将 proposal、design、delta specs 与任务清单同步为当前修复范围，并通过 strict OpenSpec 验证。
- [x] CB-1.2 补齐 adapter managed-env、CodeBuddy 静态 manifest、引擎内 release gate、秘密脱敏与状态缓存机器合同，并确保全局 contracts 不含 CodeBuddy 专属 schema。

## 2. CodeBuddy 安全、目录与执行语义

- [x] CB-2.1 收敛 CodeBuddy 存储布局、权限、原子写、symlink 防护、provider 凭证轮换和删除隔离。
- [x] CB-2.2 在所有 CodeBuddy 输出 sink 前接入状态化 fail-closed 秘密脱敏，按完整物理记录低延迟释放，并保证 post-auth redactor 可用且采集失败不会被 missing-terminal 覆盖。
- [x] CB-2.3 恢复 provider-qualified 静态模型 manifest 与固定快照，删除 CodeBuddy 动态 catalog、probe、LKG 和认证后刷新链路。
- [x] CB-2.4 完成结构化 provider/env/model 校验、可选 provider session handle、精确 resume、物理行 framer 重同步与逐记录 live semantic 发布。
- [x] CB-2.5 将 CodeBuddy missing/expired/运行期 401 接入既有 waiting-auth，浏览器鉴权成功后自动且仅恢复一次，并保持 provider、handle、vault 与配置目录一致。

## 3. Kilo、预装策略与状态缓存

- [x] CB-3.1 让 Kilo 复用 OpenCode 的 governed `mcp` 渲染和配置合成合同。
- [x] CB-3.2 将默认 bootstrap 集合统一为 `opencode,codex`，同步本地与容器入口、文档和合同测试；Claude、Qwen、Kilo、CodeBuddy 保持按需安装，Gemini 遵循 `gemini-engine-deprecation` 保持 sealed 且不可安装。
- [x] CB-3.3 增加确认安装门禁，禁止未安装或状态未知的 Kilo 后台模型探测，并在成功安装后仅刷新一次。
- [x] CB-3.4 增量升级 engine status cache，持久化 `last_error` 并提供 confirmed-present 判定。

## 4. UI、测试与发布门禁

- [x] CB-4.1 在 `e2e_client` 实现 CodeBuddy provider-first 表单和服务端 fail-closed 校验；管理 UI 不新增 Job 入口。
- [x] CB-4.2 启用 provider-aware CodeBuddy inline TUI：显式已登录 provider、引擎内受管环境、session-local enforced settings 与空 strict MCP。
- [x] CB-4.3 完成 Kilo MCP/bootstrap/catalog、CodeBuddy 静态模型、安全、run-local skill 物化、framer、golden 与 e2e_client 回归测试。
- [x] CB-4.4 新增秘密扫描、自动验收脚本和位于 CodeBuddy 引擎目录内的机器可读双 provider release gate schema。
- [x] CB-4.5 运行完整自动门禁；国内与国际 provider 的会话自动鉴权恢复和 TUI 启动已由操作者手工确认，两个 provider 的 release gate 均记录为 `passed`。
- [x] CB-4.6 增加会话鉴权与 TUI 集成回归，覆盖 preflight 不启动 CLI、post-auth 低延迟输出脱敏、逐记录 live FCMP/RASP/chat、stdout/stderr 401、单次自动恢复、精确 resume、provider 隔离、waiting-auth 状态轮询审计路径、challenge-active 幂等方式确认、picker 门禁及现有 UI-shell 生命周期不回归。
