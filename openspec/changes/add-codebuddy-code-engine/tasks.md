## 1. 规格、合同与计划工件

- [x] CB-1.1 创建 umbrella change、delta specs 与详细代码级计划；验收：工件职责、规范优先级、路由/数据流/接口/失败/测试矩阵完整。详见 [CB-1.1](../../../artifacts/codebuddy_engine_integration_plan_2026-07-10.md#cb-11-umbrella-change-与详细计划)。
- [x] CB-1.2 更新 profile、skill、MCP、parser capability 机器合同与根 AGENTS.md 导航；验收：schema/profile 合同测试和 strict OpenSpec 验证通过。详见 [CB-1.2](../../../artifacts/codebuddy_engine_integration_plan_2026-07-10.md#cb-12-机器合同与导航)。

## 2. 双 Provider 鉴权、Secret Vault 与模型目录

- [x] CB-2.1 实现 canonical provider registry 与 provider-keyed Secret Vault；验收：双 provider 隔离、权限、原子写、删除、状态投影和账号轮换测试通过。详见 [CB-2.1](../../../artifacts/codebuddy_engine_integration_plan_2026-07-10.md#cb-21-provider-与-secret-vault)。
- [x] CB-2.2 实现隔离 SDK auth worker、auth flow 与 runtime handler；验收：URL、成功、失败、超时、取消、临时目录清理和脱敏测试通过。详见 [CB-2.2](../../../artifacts/codebuddy_engine_integration_plan_2026-07-10.md#cb-22-隔离-sdk-auth-worker)。
- [x] CB-2.3 实现 provider 分区 runtime model catalog 与 LKG；验收：同名模型不冲突、单 provider 失败隔离、raw probe 无 secret。详见 [CB-2.3](../../../artifacts/codebuddy_engine_integration_plan_2026-07-10.md#cb-23-provider-分区模型目录)。

## 3. 执行适配器、Workspace、MCP 与 Stream Parser

- [x] CB-3.1 实现 profile、request policy、workspace/config、subprocess env 与 start/resume command adapter；验收：provider、argv、cwd、reserved env、CODEBUDDY.md 与 skills 测试通过。详见 [CB-3.1](../../../artifacts/codebuddy_engine_integration_plan_2026-07-10.md#cb-31-request-policyworkspace-与-command-adapter)。
- [x] CB-3.2 实现受管 strict MCP 与 structured-output 接入；验收：STDIO/HTTP/SSE、empty config、secret redaction 和 structured result 测试通过。详见 [CB-3.2](../../../artifacts/codebuddy_engine_integration_plan_2026-07-10.md#cb-32-受管-mcp-与-structured-output)。
- [x] CB-3.3 实现 stateful framer、CodeBuddy parser、终态/auth 映射与 Claude content-block mapper 抽取；验收：exit-zero error、missing terminal、malformed resync、repeated init 和 Claude 回归通过。详见 [CB-3.3](../../../artifacts/codebuddy_engine_integration_plan_2026-07-10.md#cb-33-stateful-framerparser-与协议映射)。

## 4. 全局登记、管理 UI、Golden 与发布验收

- [ ] CB-4.1 完成 active engine、adapter/auth/model/install/status/upgrade 中央登记、管理 API/UI、locales 与 harness；验收：所有登记点一致、双 provider UX 可用、credential 不回显且 inline TUI 不可见。详见 [CB-4.1](../../../artifacts/codebuddy_engine_integration_plan_2026-07-10.md#cb-41-中央登记管理面与-harness)。
- [ ] CB-4.2 完成脱敏 golden、focused/runtime SSOT/integration 验证、README/开发文档和人工发布 gate；验收：自动 gate 全绿，人工国内/国际状态如实记录。详见 [CB-4.2](../../../artifacts/codebuddy_engine_integration_plan_2026-07-10.md#cb-42-golden测试文档与发布-gate)。
