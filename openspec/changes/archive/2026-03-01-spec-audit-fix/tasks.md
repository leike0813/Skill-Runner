> **⚠️ 仅做 spec 对齐 — 不修改任何代码文件**

## 1. P0 — 关键修正

- [ ] 1.1 `run-log-streaming`：路径从 `logs/stdout.txt` 更新为 `.audit/stdout.<N>.log`，补写 Purpose
- [ ] 1.2 `interactive-session-timeout-unification`：`session_timeout_sec` → `interactive_reply_timeout_sec`，补写 Purpose

## 2. P1 — 状态标注

- [ ] 2.1 `engine-oauth-proxy-feasibility`：标记 DEPRECATED，补写 Purpose
- [ ] 2.2 `web-client-management-api-adapter`：标记 DEFERRED，补写 Purpose

## 3. P2 — 内容补充

- [ ] 3.1 `interactive-decision-policy`：补写 Purpose
- [ ] 3.2 `interactive-run-cancel-lifecycle`：补写 Purpose，新增信号升级策略和 session handle 清理 requirements

## 4. P2 — TBD Purpose 批量补写（35 个）

- [ ] 4.1 `builtin-e2e-example-client`
- [ ] 4.2 `engine-auth-observability`
- [ ] 4.3 `engine-command-profile-defaults`
- [ ] 4.4 `engine-execution-failfast`
- [ ] 4.5 `engine-hard-timeout-policy`
- [ ] 4.6 `engine-runtime-config-layering`
- [ ] 4.7 `ephemeral-skill-lifecycle`
- [ ] 4.8 `ephemeral-skill-upload-and-run`
- [ ] 4.9 `ephemeral-skill-validation`
- [ ] 4.10 `external-runtime-harness-audit-translation`
- [ ] 4.11 `external-runtime-harness-cli`
- [ ] 4.12 `external-runtime-harness-environment-paths`
- [ ] 4.13 `external-runtime-harness-test-adoption`
- [ ] 4.14 `harness-shared-adapter-execution`
- [ ] 4.15 `interactive-engine-turn-protocol`
- [ ] 4.16 `interactive-job-api`
- [ ] 4.17 `interactive-job-cancel-api`
- [ ] 4.18 `interactive-run-observability`
- [ ] 4.19 `local-deploy-bootstrap`
- [ ] 4.20 `management-api-surface`
- [ ] 4.21 `mixed-input-protocol`
- [ ] 4.22 `output-json-repair`
- [ ] 4.23 `run-folder-trust-lifecycle`
- [ ] 4.24 `run-observability-ui`
- [ ] 4.25 `runtime-environment-parity`
- [ ] 4.26 `skill-converter-agent`
- [ ] 4.27 `skill-converter-directory-first`
- [ ] 4.28 `skill-converter-dual-mode`
- [ ] 4.29 `skill-converter-prompt-first`
- [ ] 4.30 `skill-execution-mode-declaration`
- [ ] 4.31 `skill-package-archive`
- [ ] 4.32 `skill-package-install`
- [ ] 4.33 `skill-package-validation-schema`
- [ ] 4.34 `trust-config-bootstrap`
- [ ] 4.35 `ui-auth-hardening`

## 5. 验证

- [ ] 5.1 `openspec status` 确认 4/4 artifacts 完成
- [ ] 5.2 `openspec validate` 通过格式校验
- [ ] 5.3 `openspec archive` 合并 delta 到主 spec
- [ ] 5.4 验证 archive 后主 spec 无 TBD Purpose
