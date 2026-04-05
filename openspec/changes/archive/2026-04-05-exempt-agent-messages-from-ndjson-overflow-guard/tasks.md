## 1. Spec And Contract Updates

- [x] 1.1 新增 `exempt-agent-messages-from-ndjson-overflow-guard` 的 proposal、design、tasks artifacts
- [x] 1.2 为 `engine-adapter-runtime-contract` 添加 delta spec，定义 `agent.reasoning` / `agent.message` 的 NDJSON overflow 豁免语义

## 2. Shared Runtime Implementation

- [x] 2.1 在 shared NDJSON 基础设施中为 `NdjsonLineBuffer` 增加 semantic exemption probe
- [x] 2.2 在 shared NDJSON 基础设施中为 `NdjsonIngressSanitizer` 增加相同的 semantic exemption probe
- [x] 2.3 确保豁免只跳过 `4096` 字节截断，不跳过 JSON 合法性检查、repair 和既有诊断语义

## 3. Engine Parser Integration

- [x] 3.1 为 `codex`、`claude`、`opencode`、`qwen` 的 NDJSON parser 提供轻量预分类能力
- [x] 3.2 对齐预分类规则：reasoning/thinking 豁免、assistant text 豁免、tool/result/command 不豁免
- [x] 3.3 保持未识别 NDJSON 形态默认不豁免

## 4. Validation

- [x] 4.1 增加 shared runtime 测试，覆盖 reasoning / assistant message 的长行豁免与非豁免 tool_result 的既有截断行为
- [x] 4.2 增加至少两个 NDJSON-based engine 的集成测试，验证长 reasoning / assistant text 能完整穿过 live 与 audit
- [x] 4.3 运行 runtime mandatory regression
- [x] 4.4 运行 `openspec validate --changes --json`
