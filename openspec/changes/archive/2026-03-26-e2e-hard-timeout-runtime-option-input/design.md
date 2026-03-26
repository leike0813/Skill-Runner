## Context

后端作业创建链路已经支持 `runtime_options.hard_timeout_seconds`，并且 skill manifest 中也已经支持 `runtime.default_options`。问题并不在执行内核，而在两个上游缺口：

1. management skill detail 没有把 runtime 默认值暴露给前端；
2. E2E 客户端没有服务级默认值接口，也没有 UI 输入控件和校验逻辑。

因此，这次变更聚焦在 management API 和 E2E client 两层，不触碰主运行时行为，也不修改主 specs。

## Goals / Non-Goals

**Goals:**
- 让 E2E Run Form 能稳定展示并提交 `hard_timeout_seconds`
- 让前端默认值来源可解释：优先 skill default，回退 service default
- 保证 fixture skill 与 installed skill 两条路径行为一致
- 严格遵守 OpenSpec：先新开 change，再写 delta specs，再实现，再勾 tasks

**Non-Goals:**
- 不修改 `/v1/jobs` 对 `hard_timeout_seconds` 的运行时语义
- 不修改主 specs；本轮只新增 change 工件
- 不扩展其他 runtime option UI

## Decisions

### 1. management skill detail 直接暴露 `runtime.default_options`

`SkillManifest` 已包含 `runtime.default_options`，因此 management detail 直接透传该视图即可。这里不重新设计独立 runtime schema，只提供当前前端需要的稳定 JSON 结构。

### 2. 服务级默认值通过独立 management 端点提供

E2E 客户端不应硬编码服务默认 `hard_timeout_seconds`。新增 `GET /v1/management/runtime-options`，返回：

- `service_defaults.hard_timeout_seconds`

其值来源于 `config.SYSTEM.ENGINE_HARD_TIMEOUT_SECONDS`。

### 3. E2E Run Form 始终显示 `hard_timeout_seconds`

该字段不依赖 execution mode，也不依赖 skill 是否显式声明默认值。UI 一律显示：

- `type="number"`
- `min="0"`
- `step="60"`

并允许用户自由输入。初始预填值按：

1. `skill.runtime.default_options.hard_timeout_seconds`
2. `service_defaults.hard_timeout_seconds`

的优先级解析。

### 4. 提交时显式写入 runtime option

Run Form 提交时，无论值来自预填还是用户修改，都会显式提交 `runtime_options.hard_timeout_seconds`。这样可以让 E2E 客户端更接近真实前端的可见配置行为，避免“表单有值但后端最终依赖隐式默认”的歧义。

### 5. Fixture 路径与 installed 路径对齐

fixture skill 目前本地构造 detail 时丢失了 `runtime`。本次会让 `_load_fixture_skill_bundle_from_dir()` 同样返回 `runtime.default_options`，确保本地 fixture run form 的默认值计算逻辑与 installed skill 完全一致。

## Risks / Trade-offs

- [Risk] management detail 直接暴露 runtime default options 可能让未来字段增加时影响前端假设。
  -> Mitigation: 前端只依赖 `runtime.default_options.hard_timeout_seconds`，测试也只锁定该稳定字段。

- [Risk] 新增 `runtime-options` 端点会让 FakeBackend/测试桩接口需要同步更新。
  -> Mitigation: 一并补齐 `BackendClient` 抽象与集成测试桩，避免接口漂移。

- [Risk] number input 仍允许浏览器提交字符串或小数文本。
  -> Mitigation: 服务端 E2E 路由继续做严格解析，只接受 `> 0` 的整数。
